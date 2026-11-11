#!/usr/bin/env python3
"""Genera resultados/graficas/*.png a partir de los .jtl.zip, metricas.json y recursos.csv."""
import csv
import io
import json
import zipfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RES = Path(__file__).resolve().parent / "resultados"
OUT = RES / "graficas"
OUT.mkdir(exist_ok=True)
plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": 0.3,
                     "axes.spines.top": False, "axes.spines.right": False, "font.size": 9})
AZUL, NARANJA, GRIS, ROJO, VERDE = "#2a6fdb", "#e8833a", "#888888", "#d9534f", "#3a9d5d"


def met(eid):
    return json.loads((RES / eid / "metricas.json").read_text(encoding="utf-8"))


def filas(eid):
    z = zipfile.ZipFile(RES / eid / "resultados.jtl.zip")
    return list(csv.DictReader(io.TextIOWrapper(z.open("resultados.jtl"), encoding="utf-8")))


def recursos(eid):
    return list(csv.DictReader(open(RES / eid / "recursos.csv", encoding="utf-8")))


def p95(v):
    v = sorted(v)
    return v[max(0, int(round(0.95 * len(v) + 0.5)) - 1)] if v else 0


def ventanas(rows, seg):
    ini = min(int(r["timeStamp"]) for r in rows)
    b = {}
    for r in rows:
        b.setdefault((int(r["timeStamp"]) - ini) // (seg * 1000), []).append(r)
    return [(k * seg, b[k]) for k in sorted(b)]


def guardar(fig, nombre):
    fig.tight_layout()
    fig.savefig(OUT / nombre)
    plt.close(fig)


# P1 · 20 vs 500 usuarios
a, b = met("E01a")["estadisticas"]["TOTAL"], met("E01b")["estadisticas"]["TOTAL"]
fig, axs = plt.subplots(1, 3, figsize=(9, 3))
for ax, clave, tit in zip(axs, ["throughput_rps", "media_ms", "p95_ms"],
                          ["Throughput (pet/s)", "Media (ms)", "p95 (ms)"]):
    vals = [a[clave], b[clave]]
    ax.bar(["20 usuarios", "500 usuarios"], vals, color=[AZUL, NARANJA])
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:g}", ha="center", va="bottom")
    ax.set_title(tit)
fig.suptitle("P1 · Al pasar de 20 a 500 usuarios suben el throughput y el tiempo de respuesta")
guardar(fig, "p1_20_vs_500.png")

# P2 · pico inicial con ramp-up 1 s vs 60 s
fig, axs = plt.subplots(2, 1, figsize=(8, 5.5), sharex=True)
for eid, color, et in (("E02a", ROJO, "ramp-up 1 s"), ("E02b", AZUL, "ramp-up 60 s")):
    v = ventanas(filas(eid), 5)
    xs = [t for t, _ in v]
    axs[0].plot(xs, [max(int(r["elapsed"]) for r in rs) for _, rs in v], color=color, label=f"máximo · {et}")
    axs[0].plot(xs, [p95([int(r["elapsed"]) for r in rs]) for _, rs in v], "--", color=color, label=f"p95 · {et}")
    axs[1].plot(xs, [max(int(r["allThreads"]) for r in rs) for _, rs in v], color=color, label=et)
axs[0].set_ylabel("ms (ventanas de 5 s)")
axs[0].legend(fontsize=7, ncol=2)
axs[0].set_title("P2 · Tiempo de respuesta al inicio según el ramp-up (200 usuarios)")
axs[1].set_ylabel("Hilos activos")
axs[1].set_xlabel("Segundos desde el inicio")
axs[1].legend(fontsize=7)
guardar(fig, "p2_pico_inicial.png")

# P3 · con vs sin temporizador (20 usuarios)
fig, ax = plt.subplots(figsize=(6.5, 3.6))
eti = ["20 usuarios\ncon temporizador\n(E01a)", "20 usuarios\nsin temporizador\n(E03)"]
okr, err = [], []
for i in ["E01a", "E03"]:
    s = met(i)["estadisticas"]["TOTAL"]
    okr.append(s["throughput_rps"] * (1 - s["error_pct"] / 100))
    err.append(s["throughput_rps"] * s["error_pct"] / 100)
ax.bar(eti, okr, color=AZUL, label="exitosas/s")
ax.bar(eti, err, bottom=okr, color=ROJO, alpha=0.6, label="fallidas/s")
for i, (o, e) in enumerate(zip(okr, err)):
    ax.text(i, o + e + 20, f"total {o + e:.0f}/s\nok {o:.0f}/s · error {100 * e / (o + e):.0f} %", ha="center", fontsize=8)
ax.set_ylim(0, 1900)
ax.set_ylabel("Peticiones por segundo")
ax.set_title("P3 · Sin temporizador el throughput se dispara, pero casi todo es error")
ax.legend(fontsize=8, loc="upper left")
guardar(fig, "p3_temporizador.png")

# P4 · escalones UTG
v = ventanas(filas("E04"), 5)
xs = [t for t, _ in v]
fig, axs = plt.subplots(3, 1, figsize=(8, 7), sharex=True)
axs[0].step(xs, [max(int(r["allThreads"]) for r in rs) for _, rs in v], where="post", color=GRIS)
axs[0].set_ylabel("Hilos activos")
axs[0].set_title("P4 · Estrés por escalones 50 → 100 → 250 → 500 (Ultimate Thread Group)")
axs[1].plot(xs, [sum(r["success"] == "true" for r in rs) / 5 for _, rs in v], color=AZUL, label="exitosas/s")
axs[1].plot(xs, [sum(r["success"] != "true" for r in rs) / 5 for _, rs in v], color=ROJO, label="fallidas/s")
axs[1].set_ylabel("pet/s")
axs[1].legend(fontsize=8)
axs[2].plot(xs, [p95([int(r["elapsed"]) for r in rs if r["success"] == "true"]) for _, rs in v], color=NARANJA)
axs[2].set_ylabel("p95 exitosas (ms)")
axs[2].set_xlabel("Segundos desde el inicio")
guardar(fig, "p4_escalones.png")

# P5 · 10 minutos
v = ventanas(filas("E05b"), 30)
rec = recursos("E05b")
fig, axs = plt.subplots(2, 1, figsize=(8, 5), sharex=True)
xs = [t for t, _ in v]
axs[0].plot(xs, [sum(int(r["elapsed"]) for r in rs) / len(rs) for _, rs in v], "o-", color=AZUL, label="media")
axs[0].plot(xs, [p95([int(r["elapsed"]) for r in rs]) for _, rs in v], "s--", color=NARANJA, label="p95")
axs[0].set_ylim(0, 6)
axs[0].set_ylabel("ms (ventanas de 30 s)")
axs[0].legend(fontsize=8)
axs[0].set_title("P5 · 50 usuarios durante 10 minutos")
axs[1].plot([float(r["t"]) for r in rec], [float(r["mem_api_mb"]) for r in rec], color=AZUL, label="Memoria API (MB)")
axs[1].set_ylim(0, 40)
axs[1].set_ylabel("MB")
axs[1].set_xlabel("Segundos")
axs[1].legend(fontsize=8)
guardar(fig, "p5_10_minutos.png")

# P6 · costo por petición (E06)
st = met("E06")["estadisticas"]
labs = ["Tarifas", "SeleccionTarifaYCantidad", "Pago"]
fig, ax = plt.subplots(figsize=(7, 3.4))
x = range(len(labs))
ax.bar([i - 0.2 for i in x], [st[l]["media_ms"] for l in labs], 0.4, color=AZUL, label="Media (ms)")
ax.bar([i + 0.2 for i in x], [st[l]["p95_ms"] for l in labs], 0.4, color=NARANJA, label="p95 (ms)")
for i, l in enumerate(labs):
    ax.text(i - 0.2, st[l]["media_ms"], f'{st[l]["media_ms"]:.2f}', ha="center", va="bottom", fontsize=8)
ax.set_xticks(list(x))
ax.set_xticklabels(["/api/tarifas (GET)", "/api/seleccion (POST)", "/api/pago (POST)"])
ax.set_ylabel("ms")
ax.set_title("P6 · Costo por petición con la misma carga (100 usuarios)")
ax.legend(fontsize=8)
guardar(fig, "p6_costo.png")

# P10 · recursos con 500 usuarios
rows = filas("E10")
v = ventanas(rows, 5)
rec = recursos("E10")
fig, axs = plt.subplots(4, 1, figsize=(8.5, 9), sharex=True)
xs = [t for t, _ in v]
axs[0].plot(xs, [max(int(r["allThreads"]) for r in rs) for _, rs in v], color=GRIS)
axs[0].set_ylabel("Hilos")
axs[0].set_title("P10 · 500 usuarios: rendimiento vs CPU y memoria")
axs[1].plot(xs, [sum(r["success"] == "true" for r in rs) / 5 for _, rs in v], color=AZUL, label="exitosas/s")
axs[1].plot(xs, [sum("BindException" in r["responseCode"] for r in rs) / 5 for _, rs in v], color=ROJO,
            label="BindException/s (sin puertos)")
axs[1].plot(xs, [sum("HttpHostConnect" in r["responseCode"] for r in rs) / 5 for _, rs in v], color=NARANJA,
            label="conexión rechazada/s")
axs[1].set_ylabel("pet/s")
axs[1].legend(fontsize=7)
axs[2].plot(xs, [p95([int(r["elapsed"]) for r in rs if r["success"] == "true"]) for _, rs in v], color=NARANJA)
axs[2].set_ylabel("p95 exitosas (ms)")
tt = [float(r["t"]) for r in rec]
axs[3].plot(tt, [float(r["cpu_sistema_pct"]) for r in rec], color=GRIS, label="CPU equipo %")
axs[3].plot(tt, [float(r["cpu_jmeter_pct"]) for r in rec], color=NARANJA, label="CPU JMeter %")
axs[3].plot(tt, [float(r["cpu_api_pct"]) for r in rec], color=AZUL, label="CPU API %")
axs[3].plot(tt, [float(r["mem_sistema_pct"]) for r in rec], color=VERDE, label="Memoria equipo %")
axs[3].set_ylim(0, 100)
axs[3].set_ylabel("%")
axs[3].set_xlabel("Segundos desde el inicio")
axs[3].legend(fontsize=7, ncol=2)
guardar(fig, "p10_recursos.png")

fig, ax = plt.subplots(figsize=(8, 2.8))
ax.plot(tt, [float(r["mem_api_mb"]) for r in rec], color=AZUL, label="Memoria API (MB)")
ax.plot(tt, [float(r["mem_jmeter_mb"]) for r in rec], color=NARANJA, label="Memoria JMeter (MB)")
ax.set_ylabel("MB")
ax.set_xlabel("Segundos")
ax.set_title("P10 · Memoria por proceso (500 usuarios)")
ax.legend(fontsize=8)
guardar(fig, "p10_memoria.png")
print("Gráficas en", OUT)
