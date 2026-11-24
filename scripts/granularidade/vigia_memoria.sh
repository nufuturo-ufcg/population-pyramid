#!/bin/bash
# Roda um comando e vigia a memória residente dele. Se passar de <limite_gb> GB, avisa no log, para o comando com
# SIGTERM e sai com código 3, em vez de deixar o processo cair. Grava a memória a cada 30 s em <log>.csv.
# Uso: vigia_memoria.sh <limite_gb> <log> comando args...
LIMITE_GB=$1; LOG=$2; shift 2
LIMITE_KB=$((LIMITE_GB * 1024 * 1024))
"$@" &
PID=$!
PICO=0
echo "hora_utc,rss_gb,disponivel_gb" > "$LOG.csv"
while kill -0 $PID 2>/dev/null; do
  RSS=$(ps -o rss= -p $PID | tr -d ' ')
  [ -z "$RSS" ] && break
  DISP=$(awk '/MemAvailable/{printf "%.0f", $2/1048576}' /proc/meminfo)
  [ "$RSS" -gt "$PICO" ] && PICO=$RSS
  echo "$(date -u +%H:%M:%S),$((RSS / 1048576)),$DISP" >> "$LOG.csv"
  if [ "$RSS" -gt "$LIMITE_KB" ]; then
    echo "$(date -u +%H:%M:%S) MEMORIA ACIMA DE ${LIMITE_GB} GB (rss $((RSS / 1048576)) GB): parando o comando" >> "$LOG"
    kill -TERM $PID; sleep 10; kill -KILL $PID 2>/dev/null
    echo "PICO_GB $((PICO / 1048576))" >> "$LOG"
    exit 3
  fi
  sleep 30
done
wait $PID
CODIGO=$?
echo "FIM codigo $CODIGO pico_gb $((PICO / 1048576))" >> "$LOG"
exit $CODIGO
