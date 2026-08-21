#!/usr/bin/env bash
# Confere a coleta da API do GitHub para o adaptador `adapters/ghapi`.
# Roda ANTES do pipeline. Existe porque coleta incompleta falha em silêncio: um
# `.jsonl` que parou no meio por cota estourada some com os eventos mais antigos
# e envelhece a pirâmide inteira sem nenhum erro aparecer. Falha cedo e explícito.
#
# O contrato do que a coleta entrega está em docs/ferramenta/COLETA_GITHUB.md.
set -euo pipefail

RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; RST=$'\033[0m'
die() { echo "${RED}erro:${RST} $*" >&2; exit 1; }
ok()  { echo "${GRN}ok:${RST} $*"; }
warn(){ echo "${YLW}aviso:${RST} $*" >&2; }

# O .env mora na raiz do repositório.
AQUI="$(cd "$(dirname "$0")" && pwd)"
cd "$AQUI/../.."

[[ -f .env ]] && { set -a; source .env; set +a; }

GHAPI_DIR="${GHAPI_DIR:-data/ghapi}"
[[ -d "$GHAPI_DIR" ]] || die "GHAPI_DIR '$GHAPI_DIR' nao existe. Colete antes, ou aponte a variavel no .env.
  amostra de desenvolvimento:
    GHAPI_DIR=$GHAPI_DIR .venv/bin/python adapters/ghapi/coleta_amostra.py clj-kondo/clj-kondo"

MANIFESTO="$GHAPI_DIR/_coleta.json"
[[ -f "$MANIFESTO" ]] || die "sem '$MANIFESTO'. A coleta precisa declarar a data de corte, senao duas execucoes em semanas diferentes nao sao comparaveis."
[[ -f "$GHAPI_DIR/repos.jsonl" ]] || die "sem '$GHAPI_DIR/repos.jsonl'."

# As seis buscas paginadas, mais `languages` e `commit_files`, que têm extensão
# própria. A lista bate com a tabela de docs/ferramenta/COLETA_GITHUB.md.
BUSCAS=(commits issues issue_comments commit_comments pull_request_comments issue_events)

# Um `python -` só: percorrer JSON em bash pede jq, que nem toda máquina tem.
PY="${PY:-.venv/bin/python}"
[[ -x "$PY" ]] || PY="python3"

echo "conferindo a coleta em ${GHAPI_DIR} ..."
"$PY" - "$GHAPI_DIR" "${BUSCAS[@]}" <<'EOF' || die "coleta incompleta. Veja as linhas acima."
import json
import sys
from pathlib import Path

raiz = Path(sys.argv[1])
buscas = sys.argv[2:]
man = json.loads((raiz / "_coleta.json").read_text(encoding="utf-8"))

problemas: list[str] = []
if not man.get("corte"):
    problemas.append("_coleta.json sem a chave 'corte'")

declarados = [int(r) for r in man.get("repos", [])]
if not declarados:
    problemas.append("_coleta.json sem repositorios em 'repos'")

linhas = (raiz / "repos.jsonl").read_text(encoding="utf-8").splitlines()
no_jsonl = [int(json.loads(x)["id"]) for x in linhas if x.strip()]
if sorted(no_jsonl) != sorted(declarados):
    problemas.append(f"repos.jsonl tem {sorted(no_jsonl)}, _coleta.json declara {sorted(declarados)}")

contagens = man.get("contagens", {})
for rid in declarados:
    if not (raiz / "languages" / f"{rid}.json").is_file():
        problemas.append(f"{rid}: falta languages/{rid}.json")
    tsv = raiz / "commit_files" / f"{rid}.tsv"
    if not tsv.is_file():
        problemas.append(f"{rid}: falta commit_files/{rid}.tsv")
    for busca in buscas:
        arq = raiz / busca / f"{rid}.jsonl"
        if not arq.is_file():
            problemas.append(f"{rid}: falta {busca}/{rid}.jsonl")
            continue
        # Contagem de linha contra o manifesto. É o que pega coleta que parou no
        # meio: o arquivo existe, tem conteúdo, e mente sobre estar completo.
        tem = sum(1 for linha in arq.open(encoding="utf-8") if linha.strip())
        declarado = contagens.get(str(rid), {}).get(busca)
        if declarado is None:
            problemas.append(f"{rid}: _coleta.json nao declara contagem de {busca}")
        elif tem != declarado:
            problemas.append(f"{rid}: {busca} tem {tem} linhas, _coleta.json declara {declarado}")

for p in problemas:
    print(f"  {p}", file=sys.stderr)
print(f"{len(declarados)} repositorios, {len(problemas)} problemas")
sys.exit(1 if problemas else 0)
EOF

n=$("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1]))['repos']))" "$MANIFESTO")
corte=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['corte'])" "$MANIFESTO")
ok "coleta confirmada: ${n} repositorios, corte em ${corte}"

# `language` nulo vira escopo `unknown`, que é contado e não plota. Avisar aqui
# evita a pergunta "por que essa pirâmide não saiu" três estágios adiante.
sem_lang=$("$PY" -c "
import json, sys
n = sum(1 for l in open(sys.argv[1], encoding='utf-8') if l.strip() and json.loads(l).get('language') is None)
print(n)
" "$GHAPI_DIR/repos.jsonl")
[[ "$sem_lang" == "0" ]] || warn "${sem_lang} repositorios com language nulo. Eles caem no escopo 'unknown'."
