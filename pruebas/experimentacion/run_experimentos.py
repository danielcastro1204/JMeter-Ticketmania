#!/usr/bin/env python3
"""
Ejecuta los escenarios de experimentación de Ticketmania en modo no-GUI.

Para cada escenario:
  1. Levanta una API nueva (memoria limpia) y espera a /api/salud.
  2. Inicia un monitor de recursos (psutil, 1 muestra/s): CPU y memoria del
     sistema, del proceso de la API (python) y del proceso de JMeter (java).
     Reemplaza a PerfMon/ServerAgent, cuya librería SIGAR falla en Windows 11.
  3. Genera escenarios/<ID>.jmx (copia de experimentacion.jmx con los valores
     concretos del escenario) y ejecuta:
     java -jar ApacheJMeter.jar -n -t escenarios/<ID>.jmx
     -l resultados/<ID>/resultados.jtl -e -o resultados/<ID>/reporte
  4. Detiene la API y guarda métricas en resultados/<ID>/metricas.json y en
     resultados/resumen.csv / resumen.md.

Uso (desde pruebas/experimentacion):
  python run_experimentos.py                 # todos los escenarios
  python run_experimentos.py E01a E04         # solo algunos
  python run_experimentos.py --generar       # solo genera escenarios/*.jmx
  python run_experimentos.py --listar

Variables de entorno:
  JMETER_HOME  carpeta de apache-jmeter-5.6.3 (obligatoria)
  JAVA         ejecutable de Java 17 (por defecto: java)
Requiere: Python 3.8+ y psutil (pip install psutil).
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import psutil

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
API = RAIZ / "api" / "ticketmania_simple.py"
PLAN = AQUI / "experimentacion.jmx"
RES = AQUI / "resultados"

# Valores base: cada escenario cambia SOLO lo que declara en "props".
BASE = {"hilos": 20, "rampup": 10, "duracion": 60, "bucles": -1,
        "pausa_min": 500, "pausa_rango": 1000, "sync": 1, "sync_timeout": 30000,
        "conexion": "keep-alive", "csv": "datos.csv",
        "utg1": 0, "utg2": 0, "utg3": 0, "utg4": 0, "utg_pausa_min": 500, "utg_pausa_rango": 1000,
        "host": "127.0.0.1", "puerto": 8080}
SIN_PAUSA = {"pausa_min": 0, "pausa_rango": 0}

# (id, pregunta, descripción, props cambiadas respecto de BASE)
ESCENARIOS = [
    # P1 Carga: 20 -> 500 usuarios (variable: hilos)
    ("E01a", "P1", "20 usuarios, ramp-up 10 s, 60 s, pausas 0,5-1,5 s", {}),
    ("E01b", "P1", "500 usuarios, ramp-up 10 s, 60 s, pausas 0,5-1,5 s", {"hilos": 500}),
    # P2 Carga: ramp-up 1 s vs 60 s (variable: rampup) con 200 usuarios durante 120 s
    ("E02a", "P2", "200 usuarios, ramp-up 1 s, 120 s", {"hilos": 200, "rampup": 1, "duracion": 120}),
    ("E02b", "P2", "200 usuarios, ramp-up 60 s, 120 s", {"hilos": 200, "rampup": 60, "duracion": 120}),
    # P3 Carga: sin temporizadores (variable: pausas); con temporizador = E01a
    ("E03", "P3", "20 usuarios SIN temporizador, ramp-up 10 s, 60 s", SIN_PAUSA),
    # P4 Estrés: Ultimate Thread Group 50 -> 100 -> 250 -> 500 (variable: hilos en escalones)
    ("E04", "P4", "Ultimate Thread Group: 50, 100, 250 y 500 hilos cada 30 s, pausas 0,5-1,5 s",
     {"hilos": 0, "utg1": 50, "utg2": 50, "utg3": 150, "utg4": 250}),
    # P5 Estrés: 1 min vs 10 min (variable: duración) con 50 usuarios
    ("E05a", "P5", "50 usuarios durante 60 s", {"hilos": 50, "duracion": 60}),
    ("E05b", "P5", "50 usuarios durante 600 s", {"hilos": 50, "duracion": 600}),
    # P6 Estrés: costo de /api/tarifas vs /api/seleccion con la misma carga (se comparan etiquetas)
    ("E06", "P6", "100 usuarios, 60 s: Tarifas y Selección reciben la misma carga", {"hilos": 100}),
    # P7 Concurrencia: 500 usuarios crean reservas al mismo tiempo (Temporizador sincronizado de 500)
    ("E07", "P7", "500 usuarios x1, Selección sincronizada de a 500", {"hilos": 500, "bucles": 1, "duracion": 600, "sync": 500}),
    # P8 Concurrencia: sincronizados (=E07) vs distribuidos (variable: sync)
    ("E08", "P8", "500 usuarios x1, distribuidos (sin sincronizar)", {"hilos": 500, "bucles": 1, "duracion": 600, "sync": 1}),
    # P9 Concurrencia: total cobrado = precio x cantidad bajo carga (JSON Assertion vs CSV)
    ("E09a", "P9", "200 usuarios, 60 s, total validado contra datos.csv", {"hilos": 200}),
    ("E09b", "P9", "Control: 5 usuarios, 10 s, CSV con un total mal calculado a propósito",
     {"hilos": 5, "rampup": 1, "duracion": 10, "csv": "datos_control_total_erroneo.csv"}),
    # P10 Recursos: 500 usuarios, CPU y memoria (subida lenta para ver cuándo se satura)
    ("E10", "P10", "500 usuarios, ramp-up 60 s, 180 s, con monitor de CPU/memoria", {"hilos": 500, "rampup": 60, "duracion": 180}),
]


def plan_concreto(eid, p):
    """Copia de experimentacion.jmx con los __P reemplazados por los valores del escenario.

    Es el archivo que se ejecuta y el que se abre en la GUI para las capturas.
    """
    import re
    xml = PLAN.read_text(encoding="utf-8")
    # El .jmx concreto vive en escenarios/: JMeter resuelve el CSV relativo a la carpeta del plan
    p = {**p, "csv": "../" + p["csv"]}
    xml = re.sub(r"\$\{__P\((\w+),([^)]*)\)\}", lambda m: str(p.get(m.group(1), m.group(2))), xml)
    if int(p["hilos"]) == 0:
        xml = xml.replace('testname="Carga (Grupo de Hilos estandar)" enabled="true"',
                          'testname="Carga (Grupo de Hilos estandar)" enabled="false"')
    if all(int(p[k]) == 0 for k in ("utg1", "utg2", "utg3", "utg4")):
        xml = xml.replace('testname="Estres (jp@gc Ultimate Thread Group)" enabled="true"',
                          'testname="Estres (jp@gc Ultimate Thread Group)" enabled="false"')
    xml = xml.replace('testname="Experimentacion Ticketmania"', f'testname="Experimentacion Ticketmania - {eid}"')
    destino = AQUI / "escenarios" / f"{eid}.jmx"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(xml, encoding="utf-8", newline="\n")
    return destino


def enfriar_puertos(limite=500, maximo_s=300):
    """Espera a que se liberen las conexiones en TIME_WAIT del escenario anterior.

    La API habla HTTP/1.0 (una conexión TCP por petición). En Windows hay 16 384 puertos
    dinámicos y cada conexión cerrada queda un tiempo en TIME_WAIT: si el escenario anterior
    dejó miles, el siguiente empieza con el pool agotado (java.net.BindException).
    """
    t0 = time.time()
    while True:
        n = sum(1 for c in psutil.net_connections("tcp") if c.status == psutil.CONN_TIME_WAIT)
        if n <= limite or time.time() - t0 > maximo_s:
            print(f"    TIME_WAIT al iniciar: {n} (espera {time.time() - t0:.0f} s)", flush=True)
            return n
        time.sleep(5)


def esperar_api(timeout=30):
    fin = time.time() + timeout
    while time.time() < fin:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8080/api/salud", timeout=1) as r:
                if r.status == 200:
                    return True
        except OSError:
            time.sleep(0.5)
    return False


class Monitor(threading.Thread):
    """Muestrea CPU/memoria cada segundo (equivalente a PerfMon)."""

    def __init__(self, api_pid, salida):
        super().__init__(daemon=True)
        self.api = psutil.Process(api_pid)
        self.salida = salida
        self.alto = threading.Event()
        self.filas = []

    def _jmeter(self):
        for p in psutil.process_iter(["name", "cmdline"]):
            try:
                if "java" in (p.info["name"] or "").lower() and any(
                        "ApacheJMeter.jar" in c for c in (p.info["cmdline"] or [])):
                    return p
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return None

    def run(self):
        jm = None
        ncpu = psutil.cpu_count()
        psutil.cpu_percent(None)
        self.api.cpu_percent(None)
        t0 = time.time()
        while not self.alto.wait(1.0):
            if jm is None:
                jm = self._jmeter()
                if jm:
                    jm.cpu_percent(None)
                    continue
            try:
                fila = {
                    "t": round(time.time() - t0, 1),
                    "cpu_sistema_pct": psutil.cpu_percent(None),
                    "mem_sistema_pct": psutil.virtual_memory().percent,
                    # % de la máquina completa (0-100), normalizado por núcleos
                    "cpu_api_pct": round(self.api.cpu_percent(None) / ncpu, 2),
                    "mem_api_mb": round(self.api.memory_info().rss / 2**20, 1),
                    "hilos_api": self.api.num_threads(),
                    "cpu_jmeter_pct": round(jm.cpu_percent(None) / ncpu, 2) if jm else 0,
                    "mem_jmeter_mb": round(jm.memory_info().rss / 2**20, 1) if jm else 0,
                }
            except psutil.NoSuchProcess:
                break
            self.filas.append(fila)
        if self.filas:
            with open(self.salida, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(self.filas[0]))
                w.writeheader()
                w.writerows(self.filas)


def percentil(valores, p):
    if not valores:
        return 0
    v = sorted(valores)
    k = max(0, min(len(v) - 1, int(round(p / 100 * len(v) + 0.5)) - 1))
    return v[k]


def analizar_jtl(jtl):
    filas = list(csv.DictReader(open(jtl, newline="", encoding="utf-8")))
    grupos = {}
    for r in filas:
        grupos.setdefault(r["label"], []).append(r)
    grupos["TOTAL"] = filas

    def stats(rs):
        el = [int(r["elapsed"]) for r in rs]
        ini = min(int(r["timeStamp"]) for r in rs)
        fin = max(int(r["timeStamp"]) + int(r["elapsed"]) for r in rs)
        err = sum(1 for r in rs if r["success"] != "true")
        dur = max((fin - ini) / 1000, 0.001)
        return {
            "muestras": len(rs),
            "media_ms": round(sum(el) / len(el), 2),
            "mediana_ms": percentil(el, 50),
            "p90_ms": percentil(el, 90),
            "p95_ms": percentil(el, 95),
            "p99_ms": percentil(el, 99),
            "max_ms": max(el),
            "errores": err,
            "error_pct": round(100 * err / len(rs), 2),
            "throughput_rps": round(len(rs) / dur, 2),
            "connect_media_ms": round(sum(int(r["Connect"]) for r in rs) / len(rs), 3),
            "duracion_s": round(dur, 1),
        }

    res = {k: stats(v) for k, v in grupos.items() if v}
    # Errores por código/mensaje
    errores = {}
    for r in filas:
        if r["success"] != "true":
            k = f'{r["label"]} | {r["responseCode"]} | {r["responseMessage"][:60]}'
            errores[k] = errores.get(k, 0) + 1
    # Serie por ventanas de 10 s (throughput, media, p95, errores, hilos activos)
    ini = min(int(r["timeStamp"]) for r in filas)
    ventanas = {}
    for r in filas:
        ventanas.setdefault((int(r["timeStamp"]) - ini) // 10000, []).append(r)
    serie = []
    for w in sorted(ventanas):
        rs = ventanas[w]
        el = [int(r["elapsed"]) for r in rs]
        serie.append({"seg": w * 10, "rps": round(len(rs) / 10, 1),
                      "media_ms": round(sum(el) / len(el), 1), "p95_ms": percentil(el, 95),
                      "error_pct": round(100 * sum(r["success"] != "true" for r in rs) / len(rs), 1),
                      "hilos": max(int(r["allThreads"]) for r in rs)})
    return res, errores, serie


def resumen_recursos(path):
    if not path.exists():
        return {}
    fs = list(csv.DictReader(open(path, encoding="utf-8")))
    if not fs:
        return {}
    out = {}
    for k in ("cpu_sistema_pct", "cpu_api_pct", "cpu_jmeter_pct", "mem_api_mb", "mem_jmeter_mb", "hilos_api"):
        vs = [float(f[k]) for f in fs]
        out[k + "_media"] = round(sum(vs) / len(vs), 1)
        out[k + "_max"] = round(max(vs), 1)
    out["mem_api_mb_inicio"] = float(fs[0]["mem_api_mb"])
    out["mem_api_mb_fin"] = float(fs[-1]["mem_api_mb"])
    return out


def ejecutar(eid, pregunta, desc, props):
    jmeter_home = Path(os.environ["JMETER_HOME"])
    java = os.environ.get("JAVA", "java")
    d = RES / eid
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    p = {**BASE, **props}
    print(f"\n=== {eid} ({pregunta}) {desc}\n    props: {props}", flush=True)

    time_wait_inicial = enfriar_puertos()
    api = subprocess.Popen([sys.executable, str(API)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not esperar_api():
            raise RuntimeError("La API no respondió en /api/salud")
        # En Windows el python de la Store lanza un proceso hijo: se monitorea el más profundo
        hijos = psutil.Process(api.pid).children(recursive=True)
        api_pid = hijos[-1].pid if hijos else api.pid
        mon = Monitor(api_pid, d / "recursos.csv")
        mon.start()
        plan = plan_concreto(eid, p)
        cmd = [java, "-Xms1g", "-Xmx2g", "-jar", str(jmeter_home / "bin" / "ApacheJMeter.jar"),
               "-n", "-t", str(plan),
               "-l", str(d / "resultados.jtl"), "-e", "-o", str(d / "reporte"),
               "-j", str(d / "jmeter.log"),
               # gráficas "Over Time" del reporte HTML con puntos cada 1 s (por defecto: 1 min)
               "-Jjmeter.reportgenerator.overall_granularity=1000"]
        t0 = time.time()
        subprocess.run(cmd, cwd=AQUI, check=True, stdout=subprocess.DEVNULL)
        mon.alto.set()
        mon.join()
    finally:
        try:
            for h in psutil.Process(api.pid).children(recursive=True):
                h.kill()
        except psutil.NoSuchProcess:
            pass
        api.kill()
        api.wait()

    stats, errores, serie = analizar_jtl(d / "resultados.jtl")
    recursos = resumen_recursos(d / "recursos.csv")
    out = {"id": eid, "pregunta": pregunta, "descripcion": desc, "props_cambiadas": props,
           "props_efectivas": p, "time_wait_inicial": time_wait_inicial, "duracion_real_s": round(time.time() - t0, 1),
           "estadisticas": stats, "errores": errores, "serie_10s": serie, "recursos": recursos}
    (d / "metricas.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    t = stats["TOTAL"]
    print(f"    muestras={t['muestras']} media={t['media_ms']}ms p95={t['p95_ms']}ms "
          f"max={t['max_ms']}ms err={t['error_pct']}% tput={t['throughput_rps']}/s", flush=True)
    # El .jtl crudo puede ser grande: se comprime para el repositorio
    shutil.make_archive(str(d / "resultados.jtl"), "zip", d, "resultados.jtl")
    (d / "resultados.jtl").unlink()
    return out


def consolidar():
    filas = []
    for m in sorted(RES.glob("*/metricas.json")):
        j = json.loads(m.read_text(encoding="utf-8"))
        for label, s in j["estadisticas"].items():
            filas.append({"id": j["id"], "pregunta": j["pregunta"], "descripcion": j["descripcion"],
                          "label": label, **s,
                          "cpu_api_max": j["recursos"].get("cpu_api_pct_max", ""),
                          "cpu_jmeter_max": j["recursos"].get("cpu_jmeter_pct_max", ""),
                          "cpu_sistema_max": j["recursos"].get("cpu_sistema_pct_max", ""),
                          "mem_api_mb_max": j["recursos"].get("mem_api_mb_max", "")})
    if not filas:
        return
    with open(RES / "resumen.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    cols = ["id", "pregunta", "label", "muestras", "media_ms", "p95_ms", "max_ms", "error_pct",
            "throughput_rps", "connect_media_ms", "cpu_api_max", "cpu_jmeter_max"]
    with open(RES / "resumen.md", "w", encoding="utf-8") as f:
        f.write("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n")
        for r in filas:
            f.write("| " + " | ".join(str(r[c]) for c in cols) + " |\n")


def main():
    args = sys.argv[1:]
    if "--listar" in args:
        for e in ESCENARIOS:
            print(e[0], e[1], e[2], e[3])
        return
    if "--generar" in args:
        for e in ESCENARIOS:
            print(plan_concreto(e[0], {**BASE, **e[3]}))
        return
    if "--consolidar" in args:
        consolidar()
        return
    sel = [e for e in ESCENARIOS if not args or e[0] in args]
    for e in sel:
        ejecutar(*e)
        time.sleep(3)  # enfriamiento entre escenarios
    consolidar()


if __name__ == "__main__":
    main()
