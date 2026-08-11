.PHONY: help setup hooks check run-all extract classify snapshots metrics attractiveness projection validate plots figuras-artigo test lint fmt types qa clean
.DEFAULT_GOAL := help

UV := uv run
# Cada adaptador traz o próprio preparo de dados em adapters/<nome>/.
# Sobrescreva na linha de comando: make check ADAPTER=outro
ADAPTER ?= msr14
PREPARE := adapters/$(ADAPTER)/prepare_dataset.sh

help:
	@echo "preparo"
	@echo "  make setup [DATASET_DIR=/caminho/absoluto]  cria .env, instala deps e hooks"
	@echo "  make hooks                                  so instala os hooks do prek"
	@echo "  make check [ADAPTER=msr14]                  prepara e valida a fonte de dados"
	@echo "pipeline (ADAPTER escolhe a fonte; padrao msr14)"
	@echo "  make run-all                                check + os 7 estagios na ordem"
	@echo "  make extract classify snapshots metrics     estagios 1 a 4, isolados"
	@echo "  make attractiveness projection plots        estagios 5 a 7, isolados"
	@echo "  make validate                               compara com config/checkpoints.yaml"
	@echo "  make figuras-artigo                         recorta as figuras dos PDFs originais"
	@echo "qualidade"
	@echo "  make test                                   testes unitarios"
	@echo "  make lint                                   ruff check"
	@echo "  make fmt                                    ruff format"
	@echo "  make types                                  mypy em src/"
	@echo "  make qa                                     hooks do prek em tudo + testes"
	@echo "  make clean                                  apaga output/ e logs/, menos output/plots/"
	@echo ""
	@echo "cada comando aceita as flags da CLI: uv run pyramid --help"

setup:
	@test -f .env || cp .env.example .env
ifdef DATASET_DIR
	@python3 -c 'import re,sys,pathlib; d=sys.argv[1]; assert d.startswith("/"), "DATASET_DIR precisa ser absoluto"; p=pathlib.Path(".env"); p.write_text(re.sub(r"^DATASET_DIR=.*$$", lambda m: "DATASET_DIR="+d, p.read_text(), flags=re.M)); print("DATASET_DIR ->", d)' "$(DATASET_DIR)"
endif
	uv sync
	@chmod +x $(PREPARE)
	@$(MAKE) --no-print-directory hooks
	@echo "pronto. edite .env se precisar, depois: make check"

hooks:
	$(UV) prek install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push

check:
	@test -x $(PREPARE) || chmod +x $(PREPARE)
	@./$(PREPARE)

extract:        ; $(UV) pyramid extract --project all
classify:       ; $(UV) pyramid classify
snapshots:      ; $(UV) pyramid snapshots
metrics:        ; $(UV) pyramid metrics
attractiveness: ; $(UV) pyramid attractiveness --year all
projection:     ; $(UV) pyramid projection
plots:          ; $(UV) pyramid plot --figure all
validate:       ; $(UV) pyramid validate --report output/validation_report.md
figuras-artigo: ; $(UV) --with pillow python scripts/crop_figuras_artigo.py

run-all: check
	$(UV) pyramid run-all

test:
	$(UV) pytest -q

lint:
	$(UV) ruff check

fmt:
	$(UV) ruff format

types:
	$(UV) mypy

qa:
	$(UV) prek run --all-files
	$(UV) pytest -q

# output/plots/ é a única pasta de saída versionada: os docs embutem as figuras.
# Regerar é `make plots`, e o diff conta se a figura mudou.
clean:
	@mkdir -p output logs
	find output -mindepth 1 -maxdepth 1 ! -name plots -exec rm -rf {} +
	rm -rf logs/*
