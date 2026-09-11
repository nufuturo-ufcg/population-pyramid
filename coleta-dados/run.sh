#!/bin/bash
# Executa a etapa 2 do pipeline (coleta de eventos)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_NAME="${1:-run}"
RUN_DIR="$SCRIPT_DIR/runs/$RUN_NAME"

# Parse --limit e --language dos argumentos
LIMIT_FLAG=""
LANGUAGE_FLAG=""
for ((i=2; i<=$#; i++)); do
    eval "arg=\${$i}"
    if [[ "$arg" == "--limit" ]]; then
        NEXT=$((i+1))
        eval "val=\${$NEXT}"
        LIMIT_FLAG="--limit $val"
    fi
    if [[ "$arg" == "--language" ]]; then
        NEXT=$((i+1))
        eval "val=\${$NEXT}"
        LANGUAGE_FLAG="--language $val"
    fi
done

mkdir -p "$RUN_DIR/reports"

# /tmp e tmpfs pequeno (3.7G, com quota) e os clones bare do etapa_2B
# esgotam a quota com paralelismo. /mnt/data e disco real de 200G.
export TMPDIR=/mnt/data/tmp/etapa2-git

source "$SCRIPT_DIR/venv/bin/activate"

echo "=== Etapa 2: coleta de eventos ==="
python "$SCRIPT_DIR/scripts/capturar_logs.py" "$RUN_DIR" $LANGUAGE_FLAG $LIMIT_FLAG

echo ""
echo "=== Pipeline concluído ==="
echo "Dados salvos em: $RUN_DIR"
echo "Log em: $RUN_DIR/reports/etapa_2.log"
