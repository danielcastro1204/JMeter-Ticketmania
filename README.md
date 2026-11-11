# Tiquetmania · Pruebas de rendimiento con JMeter

Monorepo con la API de Tiquetmania, el plan de JMeter y el pipeline de GitHub Actions.

```
tiquetmania/
├── api/ticketmania_simple.py
├── pruebas/jmeter/{Ticketmania.jmx, datos.csv}
├── pruebas/experimentacion/{experimentacion.jmx, run_all.sh, RESPUESTAS.md}
├── .github/workflows/rendimiento.yml
└── README.md
```

> **Nota:** `api/ticketmania_simple.py` incluido es una réplica funcional hecha a partir de las reglas de la guía
> (tarifas, selección, pago). Reemplázalo por el archivo original del curso antes de entregar.

## Ejecución local
```bash
python3 api/ticketmania_simple.py            # http://127.0.0.1:8080
cd pruebas/jmeter
jmeter -n -t Ticketmania.jmx -l resultados.jtl -e -o reporte
```

## Plan de JMeter
Grupo de Hilos estándar: 200 usuarios, subida 300 s, 1 iteración. Flujo: Tarifas → SeleccionTarifaYCantidad
(JSON Extractor `num_reserva`) → Pago (JSON Assertion `estado` = `APROBADO`). Temporizador aleatorio uniforme 500–1500 ms.
CSV `datos.csv` con ruta relativa. Criterio de aceptación: pendiente (se define en clase); por ahora 0 peticiones fallidas.

## Pipeline (`.github/workflows/rendimiento.yml`)
Se dispara con push a `main` o manualmente. Instala Java 17 y JMeter 5.6.3, levanta la API y espera a `/api/salud`,
ejecuta JMeter en no-GUI, falla en rojo si el `.jtl` tiene peticiones fallidas y siempre sube el artefacto `reporte-rendimiento`.
En la nube no hay PerfMon y la medición no sirve para capacidad: solo comprueba que la carga corre de principio a fin.

## Ejercicio 2 · Experimentación
Ver `pruebas/experimentacion/RESPUESTAS.md` (plan independiente, 10 escenarios, resultados y limitaciones).
