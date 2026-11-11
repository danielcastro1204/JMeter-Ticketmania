#!/usr/bin/env python3
"""Genera las gráficas de resultados/graficas/ a partir de metricas.json, .jtl.zip y recursos.csv."""
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
plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": 0.3, "axes.spines.top": False,
                     "axes.spines.right": False})
AZUL, NARANJA, GRIS = "#2a6fdb", "#e8833a", "#888888"


def met(eid):
    return json.loads((RES / eid / "metricas.json").read_text(encoding="utf-8"))


def filas(eid):
    z = zipfile.ZipFile(RES / eid / "resultados.jtl.zip")
    return list(csv.DictReader(io.TextIOWrapper(z.open("resultados.jtl"), encoding="utf-8")))


def p95(v):
    v = sorted(v)
    return v[max(0, int(round(0.95 * len(v) + 0.5)) - 1)] if v else 0


# P2: throughput y p95 vs usuarios
ids = ["E01", "E02a", "E02b", "E02c", "E02d"]
hil = [met(i)["props_efectivas"]["hilos"] for i in ids]
tp = [met(i)["estadisticas"]["TOTAL"]["throughput_rps"] for i in ids]
lat = [met(i)["estadisticas"]["TOTAL"]["p95_ms"] for i in ids]
fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(hil, tp, "o-", color=AZUL, label="Throughput (pet/s)")
for x, y in zip(hil, tp):
    ax.annotate(f"{y:.0f}", (x, y), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8)
ax.set_xlabel("Usuarios concurrentes (con pausas 0,5–1,5 s)")
ax.set_ylabel("Throughput (pet/s)", color=AZUL)
ax2 = ax.twinx()
ax2.plot(hil, lat, "s--", color=NARANJA, label="p95 (ms)")
ax2.set_ylim(0, 10)
ax2.set_ylabel("p95 (ms)", color=NARANJA)
ax.set_title("P2 · El throughput crece lineal y el p95 no cambia (10→200 usuarios)")
fig.tight_layout()
fig.savefig(OUT / "p2_throughput_vs_usuarios.png")
plt.close(fig)

# P5: estrés UTG por ventanas de 10 s
rows = filas("E05")
ini = min(int(r["timeStamp"]) for r in rows)
b = {}
for r in rows:
    b.setdefault((int(r["timeStamp"]) - ini) // 10000, []).append(r)
t = sorted(b)
hil = [max(int(r["allThreads"]) for r in b[k]) for k in t]
ok = [sum(r["success"] == "true" for r in b[k]) / 10 for k in t]
tot = [len(b[k]) / 10 for k in t]
p95ok = [p95([int(r["elapsed"]) for r in b[k] if r["success"] == "true"]) for k in t]
fig, axs = plt.subplots(3, 1, figsize=(8, 7.5), sharex=True)
x = [k * 10 for k in t]
axs[0].step(x, hil, where="post", color=GRIS)
axs[0].set_ylabel("Hilos activos")
axs[0].set_title("P5 · Estrés con Ultimate Thread Group (sin pausas)")
axs[1].plot(x, tot, color=GRIS, label="Peticiones totales/s (incluye rechazadas)")
axs[1].plot(x, ok, color=AZUL, label="Peticiones exitosas/s")
axs[1].set_ylabel("pet/s")
axs[1].legend(fontsize=8)
axs[2].plot(x, p95ok, color=NARANJA)
axs[2].set_ylabel("p95 exitosas (ms)")
axs[2].set_xlabel("Segundos desde el inicio")
fig.tight_layout()
fig.savefig(OUT / "p5_estres_utg.png")
plt.close(fig)

# P5: recursos (CPU) durante el estrés
rec = list(csv.DictReader(open(RES / "E05" / "recursos.csv", encoding="utf-8")))
fig, ax = plt.subplots(figsize=(8, 3.5))
tt = [float(r["t"]) for r in rec]
ax.plot(tt, [float(r["cpu_sistema_pct"]) for r in rec], color=GRIS, label="CPU total del equipo")
ax.plot(tt, [float(r["cpu_jmeter_pct"]) for r in rec], color=NARANJA, label="CPU JMeter (java)")
ax.plot(tt, [float(r["cpu_api_pct"]) for r in rec], color=AZUL, label="CPU API (python)")
ax.set_ylim(0, 100)
ax.set_ylabel("% del equipo (16 núcleos)")
ax.set_xlabel("Segundos")
ax.set_title("P5 · Durante el estrés el generador (JMeter) consume casi toda la CPU")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "p5_recursos_cpu.png")
plt.close(fig)

# P8: estabilidad 300 s (p95 por minuto) y memoria de la API
rows = filas("E08")
ini = min(int(r["timeStamp"]) for r in rows)
b = {}
for r in rows:
    b.setdefault((int(r["timeStamp"]) - ini) // 30000, []).append(int(r["elapsed"]))
rec = list(csv.DictReader(open(RES / "E08" / "recursos.csv", encoding="utf-8")))
fig, axs = plt.subplots(2, 1, figsize=(8, 5.5), sharex=True)
axs[0].plot([k * 30 for k in sorted(b)], [sum(b[k]) / len(b[k]) for k in sorted(b)], "o-", color=AZUL, label="media")
axs[0].plot([k * 30 for k in sorted(b)], [p95(b[k]) for k in sorted(b)], "s--", color=NARANJA, label="p95")
axs[0].set_ylim(0, 6)
axs[0].set_ylabel("ms (ventanas de 30 s)")
axs[0].legend(fontsize=8)
axs[0].set_title("P8 · 50 usuarios durante 300 s: tiempo de respuesta y memoria")
axs[1].plot([float(r["t"]) for r in rec], [float(r["mem_api_mb"]) for r in rec], color=AZUL, label="Memoria API (MB)")
axs[1].plot([float(r["t"]) for r in rec], [float(r["mem_jmeter_mb"]) / 10 for r in rec], color=NARANJA,
            label="Memoria JMeter (MB / 10)")
axs[1].set_ylabel("MB")
axs[1].set_xlabel("Segundos")
axs[1].legend(fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "p8_estabilidad.png")
plt.close(fig)

# P4 / P7: con vs sin pausas, éxito vs error
fig, ax = plt.subplots(figsize=(7, 3.8))
eti = ["50 usr\ncon pausas\n(E02b)", "50 usr\nsin pausas\n(E04)", "300 usr\nsin pausas\n(E07b)"]
okr, err = [], []
for i in ["E02b", "E04", "E07b"]:
    s = met(i)["estadisticas"]["TOTAL"]
    okr.append(s["throughput_rps"] * (1 - s["error_pct"] / 100))
    err.append(s["throughput_rps"] * s["error_pct"] / 100)
ax.bar(eti, okr, color=AZUL, label="exitosas/s")
ax.bar(eti, err, bottom=okr, color="#d9534f", alpha=0.6, label="fallidas/s")
for i, (o, e) in enumerate(zip(okr, err)):
    ax.text(i, o + e + 40, f"ok {o:.0f}/s\nerr {100 * e / (o + e):.0f} %", ha="center", fontsize=8)
ax.set_ylim(0, 3800)
ax.set_ylabel("Peticiones por segundo")
ax.set_title("P4/P7 · Sin pausas la API rechaza conexiones")
ax.legend(fontsize=8, loc="upper left")
fig.tight_layout()
fig.savefig(OUT / "p4_p7_pausas_errores.png")
plt.close(fig)
print("Gráficas en", OUT)
