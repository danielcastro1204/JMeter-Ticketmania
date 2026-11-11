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
│   └── experimentacion/             # Ejercicio 2: plan independiente
│       ├── experimentacion.jmx
│       ├── datos.csv, datos_general.csv, datos_vip.csv
│       ├── run_experimentos.py      # ejecuta los escenarios en no-GUI y mide recursos
│       ├── RESPUESTAS.md            # las 10 preguntas, diseño, resultados y limitaciones
│       └── resultados/              # por escenario: reporte HTML, metricas.json, recursos.csv, .jtl.zip
├── .github/
│   └── workflows/
│       └── rendimiento.yml          # pipeline (un solo job)
└── README.md
```

## Ejercicio 1 · Pipeline de rendimiento

### Plan `pruebas/jmeter/Ticketmania.jmx`

| Elemento | Configuración |
|---|---|
| CSV Data Set Config | Nombre de archivo `datos.csv` (ruta **relativa**), variables `tarifa,cantidad`, primera línea ignorada, reciclar en EOF |
| Grupo de Hilos *Seleccion de tarifa y Pago* | **200 hilos**, subida **300 s**, contador del bucle **1** |
| Gestor de Cabecera HTTP | `Content-Type` y `Accept`: `application/json` |
| Temporizador Aleatorio Uniforme | 500 ms + 0–1000 ms (pausas de 500 a 1500 ms) |
| Peticiones | `GET /api/tarifas` → `POST /api/seleccion` (JSON Extractor `num_reserva`) → `POST /api/pago` (JSON Assertion `$.estado = APROBADO`) |
| Debug Sampler / Ver Árbol de Resultados | Deshabilitados (solo para depurar; no deben inflar la medición) |

### Pipeline `.github/workflows/rendimiento.yml`

Un único job (`rendimiento`) en `ubuntu-latest`, disparado por `push` a `main` o manualmente (`workflow_dispatch`):

1. `actions/checkout` descarga el repositorio.
2. `actions/setup-java` instala **Java 17** (Temurin).
3. Descarga **Apache JMeter 5.6.3** desde archive.apache.org y agrega su `bin` al `PATH` con `$GITHUB_PATH`.
4. Levanta la API en segundo plano (`nohup python3 api/ticketmania_simple.py --puerto 8080 &`).
5. Bucle de espera (hasta 30 intentos × 2 s) hasta que `http://127.0.0.1:8080/api/salud` responde; si no, el job falla.
6. Ejecuta `jmeter -n -t Ticketmania.jmx -l resultados.jtl -e -o reporte` **desde `pruebas/jmeter/`**, para que `datos.csv` se resuelva por ruta relativa.
7. Genera `resultados.jtl` y el reporte HTML `reporte/`.
8. Paso de decisión: lee el `.jtl` (columna `success`) y termina con código 1 si hay alguna petición fallida → el job queda en rojo. JMeter por sí solo no falla cuando una petición responde mal.
9. Sube `reporte-rendimiento` (reporte HTML + `.jtl` + log) como artefacto con `if: always()`, aunque haya fallado un paso anterior.

El reporte se descarga desde la pestaña **Actions → ejecución → Artifacts → reporte-rendimiento**.

> En GitHub Actions la API y JMeter comparten una máquina virtual compartida: el pipeline comprueba que
> la carga corre de principio a fin sin errores, **no** mide la capacidad de la API. La medición fina se
> hace en local (Ejercicio 2).

### Ejecución local (hecha antes de subir el plan)

```bash
python api/ticketmania_simple.py            # terminal 1: http://127.0.0.1:8080
cd pruebas/jmeter                           # terminal 2
jmeter -n -t Ticketmania.jmx -l resultados.jtl -e -o reporte
```

Resultado local: ver la sección *Ejecución local del Ejercicio 1* en
[`pruebas/experimentacion/RESPUESTAS.md`](pruebas/experimentacion/RESPUESTAS.md#ejecución-local-del-ejercicio-1).

## Ejercicio 2 · Experimentación individual

Todo está en [`pruebas/experimentacion/RESPUESTAS.md`](pruebas/experimentacion/RESPUESTAS.md): las 10 preguntas,
la variable que cambia en cada una, la métrica elegida, el escenario, los valores observados, la
interpretación y la limitación de cada respuesta.

Para reproducir (desde `pruebas/experimentacion/`, sin la API corriendo, porque el script la levanta y la reinicia en cada escenario):

```bash
pip install psutil
JMETER_HOME=/ruta/apache-jmeter-5.6.3 JAVA=/ruta/jdk-17/bin/java python run_experimentos.py
```

El plan `experimentacion.jmx` está parametrizado con propiedades (`${__P(hilos,10)}`, `${__P(rampup,10)}`,
`${__P(pausa_min,500)}`, `${__P(sync,1)}`, `${__P(csv,datos.csv)}`, `${__P(conexion,keep-alive)}`, `${__P(utg1..4,0)}`…),
así que cada ejecución cambia **una sola variable** con `-J` sin editar el plan. El Ultimate Thread Group requiere el
plugin *jpgc - Custom Thread Groups* (`jmeter-plugins-casutg`).
