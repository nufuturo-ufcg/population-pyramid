#!/usr/bin/env bash
# Valida/prepara a fonte de dados ANTES de `docker compose up`.
# Existe porque o Compose, se o bind-mount não existir, cria um DIRETÓRIO vazio
# no lugar em vez de dar erro — e aí o MariaDB sobe limpo, sem importar nada, e
# o pipeline falha lá na frente com "tabela não existe". Falha cedo e explícito.
set -euo pipefail

RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; RST=$'\033[0m'
die() { echo "${RED}erro:${RST} $*" >&2; exit 1; }
ok()  { echo "${GRN}ok:${RST} $*"; }
warn(){ echo "${YLW}aviso:${RST} $*" >&2; }

cd "$(dirname "$0")/.."
[[ -f .env ]] || die "sem .env — rode: make setup DATASET_DIR=/caminho/absoluto"
set -a; source .env; set +a

: "${DATASET_SOURCE:?DATASET_SOURCE nao definido no .env}"
ZENODO_URL="https://zenodo.org/records/268528/files/msr14-mysql.zip"

need_dataset_dir() {
  : "${DATASET_DIR:?DATASET_DIR nao definido no .env}"
  # Docker NÃO expande ~ nem caminhos relativos em bind-mount.
  [[ "$DATASET_DIR" == /* ]] || die "DATASET_DIR precisa ser caminho ABSOLUTO (recebi '$DATASET_DIR'). Docker nao expande ~ nem caminho relativo."
  [[ "$DATASET_DIR" != *" "* ]] || warn "DATASET_DIR tem espaco no caminho; se o mount falhar, mova a pasta."
}

case "$DATASET_SOURCE" in

  existing_db)
    ok "modo existing_db — nao vou subir banco nenhum"
    command -v docker >/dev/null || die "docker nao encontrado"
    ;;

  local)
    need_dataset_dir
    [[ -d "$DATASET_DIR" ]] || die "DATASET_DIR nao existe: $DATASET_DIR"
    if [[ ! -f "$DATASET_DIR/msr14-mysql" ]]; then
      if [[ -f "$DATASET_DIR/msr14-mysql.zip" ]]; then
        die "achei msr14-mysql.zip mas nao o dump extraido. Rode: unzip '$DATASET_DIR/msr14-mysql.zip' -d '$DATASET_DIR'"
      fi
      die "nao achei '$DATASET_DIR/msr14-mysql' (o dump SQL extraido, ~423 MB, SEM extensao .sql)"
    fi
    sz=$(wc -c < "$DATASET_DIR/msr14-mysql")
    (( sz > 400000000 )) || die "msr14-mysql tem $sz bytes; esperado ~443.178.361. Download truncado?"
    ok "dump encontrado ($sz bytes), sera montado read-only"
    ;;

  download)
    need_dataset_dir
    mkdir -p "$DATASET_DIR"
    if [[ ! -f "$DATASET_DIR/msr14-mysql" ]]; then
      [[ -f "$DATASET_DIR/msr14-mysql.zip" ]] || { ok "baixando do Zenodo (~105 MB)"; curl -fL --progress-bar -o "$DATASET_DIR/msr14-mysql.zip" "$ZENODO_URL"; }
      ok "extraindo (~423 MB)"; unzip -o -q "$DATASET_DIR/msr14-mysql.zip" -d "$DATASET_DIR"
    fi
    [[ -f "$DATASET_DIR/msr14-mysql" ]] || die "extracao nao produziu msr14-mysql"
    ok "dump pronto"
    ;;

  *) die "DATASET_SOURCE invalido: '$DATASET_SOURCE' (use existing_db, local ou download)" ;;
esac

# --- sanity check de conteúdo -------------------------------------------------
# Vale para os 3 modos: nunca confiar que o banco apontado é o certo só porque
# respondeu à conexão. 90 projetos raiz é a assinatura deste dataset.
if [[ "$DATASET_SOURCE" == "existing_db" ]]; then
  echo "conferindo o banco em ${DB_HOST}:${DB_PORT} ..."
  n=$(docker exec msr14 mariadb -u"${DB_USER}" -p"${DB_PASSWORD}" "${DB_NAME}" -N -B \
        -e "SELECT COUNT(*) FROM projects WHERE forked_from IS NULL AND id<>108342;" 2>/dev/null | tail -1) \
    || die "nao consegui consultar o container 'msr14'. Ele esta rodando? (docker start msr14)"
  [[ "$n" == "90" ]] || die "esperava 90 projetos raiz, achei '$n'. Banco errado ou import incompleto."
  ok "banco confirmado: 90 projetos raiz"
fi
