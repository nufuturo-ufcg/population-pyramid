#!/bin/bash
# Executa as etapas do pipeline em sequência

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_NAME="${1:-2026-08-23-clojure}"
RUN_DIR="$SCRIPT_DIR/runs/$RUN_NAME"

# Parse --limit do segundo argumento
LIMIT_FLAG=""
if [[ "$2" == "--limit" && -n "$3" ]]; then
    LIMIT_FLAG="--limit $3"
fi

mkdir -p "$RUN_DIR/reports"

source "$SCRIPT_DIR/venv/bin/activate"

echo "=== Etapa 1: Coleta de repositórios ==="
python "$SCRIPT_DIR/scripts/etapa_1_coleta.py" "$RUN_DIR" $LIMIT_FLAG

echo ""
echo "=== Etapa 2: coleta de eventos ==="
python "$SCRIPT_DIR/scripts/etapa_2_orchestrator.py" "$RUN_DIR" $LIMIT_FLAG

echo ""
echo "=== Pipeline concluído ==="
echo "Dados salvos em: $RUN_DIR"
