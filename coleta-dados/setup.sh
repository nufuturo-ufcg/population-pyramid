#!/bin/bash
# Setup: cria venv, instala dependências, cria diretórios necessários

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Configurando ambiente ==="

if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual..."
    python3 -m venv venv
else
    echo "venv já existe."
fi

echo "Instalando dependências..."
source venv/bin/activate
pip install -r requirements.txt

mkdir -p reports

echo ""
echo "=== Setup concluído ==="
echo "Para ativar o ambiente: source venv/bin/activate"
