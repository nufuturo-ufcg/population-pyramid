#!/usr/bin/env bash
# Confere que existe coleta em GHAPI_DIR antes de `make run-all`.
# A conferência de conteúdo mora no `source.py`, que precisa abrir os arquivos
# de qualquer jeito. Aqui fica só o que evita rodar o pipeline inteiro contra um
# caminho errado e descobrir três estágios adiante.
set -euo pipefail

RED=$'\033[31m'; GRN=$'\033[32m'; RST=$'\033[0m'
die() { echo "${RED}erro:${RST} $*" >&2; exit 1; }
ok()  { echo "${GRN}ok:${RST} $*"; }

AQUI="$(cd "$(dirname "$0")" && pwd)"
cd "$AQUI/../.."
[[ -f .env ]] && { set -a; source .env; set +a; }

GHAPI_DIR="${GHAPI_DIR:-data/ghapi}"
[[ -d "$GHAPI_DIR" ]] || die "GHAPI_DIR '$GHAPI_DIR' nao existe. Aponte no .env para a pasta da coleta.
  amostra de desenvolvimento:
    GHAPI_DIR=$GHAPI_DIR .venv/bin/python adapters/ghapi/coleta_amostra.py clj-kondo/clj-kondo"

n=$(find "$GHAPI_DIR" -type f \( -name '*.json' -o -name '*.jsonl' \) -size +0 | wc -l | tr -d ' ')
[[ "$n" -gt 0 ]] || die "'$GHAPI_DIR' nao tem nenhum .json ou .jsonl com conteudo."

ok "coleta encontrada em ${GHAPI_DIR}: ${n} arquivos"
