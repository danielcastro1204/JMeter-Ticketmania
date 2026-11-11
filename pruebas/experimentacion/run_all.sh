#!/usr/bin/env bash
# Ejecuta cada escenario en modo no-GUI (API debe estar en 127.0.0.1:8080). Uso: ./run_all.sh
cd "$(dirname "$0")"; rm -rf resultados; mkdir -p resultados
tail -n +2 scenarios.csv | while IFS=, read id desc th ramp loops delay range sync csv; do
  echo ">> $id $desc"
  jmeter -n -t experimentacion.jmx -Jthreads=$th -Jramp=$ramp -Jloops=$loops -Jdelay=$delay -Jrange=$range -Jsync=$sync -Jcsv=$csv \
    -l resultados/$id.jtl -e -o resultados/$id-reporte > /dev/null 2>&1
done
python3 analizar.py
