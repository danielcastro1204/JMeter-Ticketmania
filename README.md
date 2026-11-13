# Tiquetmania · Pruebas de rendimiento con JMeter

[![Pruebas de rendimiento](https://github.com/danielcastro1204/JMeter-Ticketmania/actions/workflows/rendimiento.yml/badge.svg)](https://github.com/danielcastro1204/JMeter-Ticketmania/actions/workflows/rendimiento.yml)

Monorepo del taller: la API de Tiquetmania, el plan de JMeter del pipeline, el pipeline de GitHub Actions
y la experimentación individual viven en el mismo repositorio, así que el pipeline prueba exactamente el
commit que se sube.

```
JMeter-Ticketmania/
├── api/
│   ├── ticketmania_simple.py        # API del curso (Python 3.8+, sin dependencias)
│   └── README.md
├── pruebas/
│   ├── jmeter/                      # Ejercicio 1: plan que usa el pipeline
│   │   ├── Ticketmania.jmx
│   │   └── datos.csv                # misma carpeta que el .jmx (ruta relativa)
│   └── experimentacion/             # Ejercicio 2: plan independiente (el pipeline no lo ejecuta)
│       ├── experimentacion.jmx      # plantilla parametrizada con ${__P(...)}
│       ├── escenarios/              # E01a.jmx … E10.jmx: copia concreta de cada escenario (lo que se ejecutó)
│       ├── datos.csv                # tarifa, cantidad, total_esperado
│       ├── datos_control_total_erroneo.csv
│       ├── run_experimentos.py      # ejecuta los escenarios en no-GUI y mide CPU/memoria
│       ├── graficas.py              # genera resultados/graficas/*.png
│       ├── RESPUESTAS.md            # las 10 preguntas «¿Qué pasaría si...?» respondidas
│       ├── entrega/                 # documento Word (y PDF) con capturas para entregar
│       └── resultados/              # por escenario: reporte HTML, metricas.json, recursos.csv, .jtl.zip; capturas/
├── .github/
│   └── workflows/
│       └── rendimiento.yml          # pipeline (un solo job)
└── README.md
```
