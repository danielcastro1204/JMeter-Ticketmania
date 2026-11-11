# Ejercicio 2 · Experimentación con JMeter

> **Aviso:** las 10 preguntas oficiales están en `guia-tecnica-jmeter_v3.md`, que no estaba disponible al construir esto.
> Los 10 escenarios de abajo (E1–E10) son una propuesta mía que cubre los temas típicos (carga, estrés, rampa, temporizadores,
> sincronización, datos). **Reasigna cada escenario a la pregunta oficial que corresponda** y ajusta el texto.

Plan: `experimentacion.jmx` (independiente del pipeline; parámetros `-Jthreads -Jramp -Jloops -Jdelay -Jrange -Jsync -Jcsv`).
Ejecución: `./run_all.sh` (no-GUI, API en 127.0.0.1:8080). Resultados crudos y reportes HTML en `resultados/`.
Base común: flujo Tarifas → Selección → Pago, 5 iteraciones, ramp 10 s, temporizador 500–1500 ms (salvo lo que cambia).
Entorno: API y JMeter en la misma máquina; API de práctica en memoria que responde al instante.

| ID | Variable que cambia | Muestras | Throughput (req/s) | Media (ms) | p95 (ms) | Máx (ms) | % Error |
|---|---|---|---|---|---|---|---|
| E1 | Base: 10 usuarios | 150 | 5,88 | 2,3 | 3 | 17 | 0 |
| E2 | 50 usuarios | 750 | 31,15 | 1,8 | 3 | 18 | 0 |
| E3 | 200 usuarios | 3000 | 116,9 | 1,0 | 2 | 18 | 0 |
| E4 | 500 usuarios | 7500 | 290,81 | 1,1 | 3 | 24 | 0 |
| E5 | 100 usuarios, ramp 1 s | 1500 | 84,29 | 1,2 | 3 | 23 | 0 |
| E6 | 100 usuarios, ramp 30 s | 1500 | 34,45 | 1,5 | 3 | 18 | 0 |
| E7 | 50 usuarios, sin temporizador | 750 | 77,19 | 1,3 | 3 | 19 | 0 |
| E8 | 100 usuarios sincronizados (Sync Timer) | 300 | 77,04 | 3,4 | 7 | 47 | 0 |
| E9 | 50 usuarios, solo VIP | 750 | 30,27 | 1,6 | 3 | 27 | 0 |
| E10 | 50 usuarios, solo general | 750 | 28,99 | 1,4 | 3 | 20 | 0 |

## Respuestas
1. **¿Más usuarios degradan el tiempo de respuesta? (E1→E4)** No en este rango: la media se mantuvo en 1–2,3 ms de 10 a 500 usuarios y el p95 en 2–3 ms. Limitación: la API es trivial y local; no se alcanzó el punto de saturación, así que no se puede afirmar cuánto aguanta.
2. **¿Cómo escala el throughput con los usuarios? (E1–E4)** Casi linealmente: 5,9 → 31,2 → 116,9 → 290,8 req/s. Mientras los usuarios esperan por el temporizador, el throughput lo marca el número de hilos activos, no la API. Un aplanamiento (saturación) no apareció.
3. **¿Qué pasa con el % de errores al subir la carga?** Se mantuvo en 0 % en todos los escenarios, incluso con 500 usuarios. No se pueden extraer conclusiones sobre el límite de errores: nunca se llegó a él.
4. **Ramp-up corto vs largo (E5 vs E6)** Con la misma carga total (1500 muestras), ramp 1 s dio 84,3 req/s y ramp 30 s dio 34,5 req/s: la rampa corta concentra la carga. La media fue similar (1,2 vs 1,5 ms). Limitación: la diferencia de throughput refleja la duración de la prueba, no peor desempeño de la API.
5. **Efecto del temporizador (E2 vs E7)** Quitarlo subió el throughput de 31,2 a 77,2 req/s con los mismos 50 usuarios, y la media pasó de 1,8 a 1,3 ms (sin cambio relevante). El temporizador controla el ritmo de llegada; no altera la latencia de la API.
6. **Concurrencia real con Sync Timer (E8)** Al liberar 100 hilos a la vez la media subió a 3,4 ms, el p95 a 7 ms y el máximo a 47 ms, el peor del conjunto. La concurrencia simultánea sí agrega latencia, pequeña. Limitación: 300 muestras y una sola repetición.
7. **¿Influye la tarifa? (E9 vs E10)** No: VIP 1,6 ms vs general 1,4 ms de media, con throughput de 30,3 vs 29,0 req/s. Diferencia dentro del ruido; el cálculo del total es el mismo para todas.
8. **Media vs p95 vs máximo** En todos los escenarios la media (1–3,4 ms) oculta picos: el máximo llegó a 17–47 ms. Por eso el p95 y el máximo informan mejor que la media. Limitación: los picos pudieron deberse al arranque de JVM/conexiones y no a la API.
9. **¿Qué mide realmente esta prueba?** JMeter y la API comparten máquina: los resultados mezclan ambos y no representan capacidad de producción. Para saberlo habría que medir CPU/memoria (PerfMon) y separar generador y servidor.
10. **¿Por qué no-GUI para medir?** La interfaz consume recursos del mismo equipo. Todas las ejecuciones se hicieron en no-GUI y sin el Árbol de Resultados (que además se retiró del plan). El GUI solo se usó para depurar. Limitación: no se comparó GUI vs no-GUI.

## Cómo reproducir
`cd pruebas/experimentacion && ./run_all.sh` (con `jmeter` en el PATH). Cada reporte: `resultados/E#-reporte/index.html`.
