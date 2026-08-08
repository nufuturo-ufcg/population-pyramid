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

# Sobe o banco do compose e ESPERA o import terminar. Sem isso, `make run-all`
# num clone limpo vai direto num MySQL que nao existe. O MariaDB so fica healthy
# depois que o entrypoint roda o /docker-entrypoint-initdb.d, entao "healthy"
# aqui significa "dump importado".
compose_up_db() {
  command -v docker >/dev/null || die "docker nao encontrado"
  docker compose version >/dev/null 2>&1 || die "precisa do 'docker compose' v2 (plugin)"
  [[ "${DB_PORT:-}" == "3307" ]] || die "no modo ${DATASET_SOURCE} o compose publica a 3307; ajuste DB_PORT=3307 no .env (recebi '${DB_PORT:-vazio}')"

  if [[ "$(docker inspect -f '{{.State.Running}}' pyramid-db 2>/dev/null || echo false)" == "true" ]]; then
    ok "container pyramid-db ja esta de pe — reaproveitando (para reimportar do zero: docker rm -f pyramid-db && docker volume rm pyramid-replication_db-data)"
  else
    ok "subindo o banco (compose, profile withdb). O PRIMEIRO boot importa 423 MB e demora."
    docker compose --profile withdb up -d db || die "compose falhou ao subir o db"
  fi

  local t=0 limit="${DB_IMPORT_TIMEOUT:-3600}" st
  while :; do
    st=$(docker inspect -f '{{.State.Health.Status}}' pyramid-db 2>/dev/null || echo missing)
    [[ "$st" == "healthy" ]] && break
    [[ "$st" == "missing" ]] && die "container pyramid-db nao existe/morreu. Veja: docker compose --profile withdb logs db"
    if (( t >= limit )); then
      die "banco nao ficou pronto em ${limit}s (status=$st). Veja: docker compose --profile withdb logs db"
    fi
    if (( t % 60 == 0 )); then echo "  ... importando o dump, ${t}s decorridos (status=$st)"; fi
    sleep 10; t=$(( t + 10 ))
  done
  ok "banco de pe e importado (porta ${DB_PORT})"
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
    compose_up_db
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
    compose_up_db
    ;;

  *) die "DATASET_SOURCE invalido: '$DATASET_SOURCE' (use existing_db, local ou download)" ;;
esac

# --- sanity check de conteúdo -------------------------------------------------
# Vale para os 3 modos: nunca confiar que o banco apontado é o certo só porque
# respondeu à conexão. 90 projetos raiz é a assinatura deste dataset.
case "$DATASET_SOURCE" in
  existing_db) db_container="${DB_CONTAINER:-msr14}" ;;
  *)           db_container="${DB_CONTAINER:-pyramid-db}" ;;
esac

echo "conferindo o banco em ${DB_HOST}:${DB_PORT} (container ${db_container}) ..."
n=$(docker exec "$db_container" mariadb -u"${DB_USER}" -p"${DB_PASSWORD}" "${DB_NAME}" -N -B \
      -e "SELECT COUNT(*) FROM projects WHERE forked_from IS NULL AND id<>108342;" 2>/dev/null | tail -1) \
  || die "nao consegui consultar o container '${db_container}'. Ele esta rodando? (docker start ${db_container})"
[[ "$n" == "90" ]] || die "esperava 90 projetos raiz, achei '$n'. Banco errado ou import incompleto."
ok "banco confirmado: 90 projetos raiz"
