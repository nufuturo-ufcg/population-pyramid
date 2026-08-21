#!/bin/bash
# Executa as etapas do pipeline em sequência

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

source venv/bin/activate

echo "=== Etapa 1: Coleta de repositórios ==="
python etapa_1_coleta.py

echo ""
echo "=== Etapa 2: Coleta de eventos ==="
python etapa_2_eventos.py

echo ""
echo "=== Pipeline concluído ==="
