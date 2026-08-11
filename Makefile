.PHONY: help setup hooks check run-all extract classify snapshots metrics attractiveness project validate plots figuras-artigo test lint fmt types qa clean
.DEFAULT_GOAL := help

UV := uv run

help:
	@echo "make setup [DATASET_DIR=/caminho/absoluto]  cria .env, instala deps e hooks"
	@echo "make check                                  valida a fonte de dados"
	@echo "make run-all                                pipeline inteiro (estagios 1-8)"
	@echo "make validate                               compara com config/checkpoints.yaml"
	@echo "make test                                   testes unitarios"
	@echo "make lint                                   ruff check"
	@echo "make fmt                                    ruff format"
	@echo "make types                                  mypy em src/"
	@echo "make qa                                     hooks do prek em todos os arquivos + testes"

setup:
	@test -f .env || cp .env.example .env
ifdef DATASET_DIR
	@python3 -c 'import re,sys,pathlib; d=sys.argv[1]; assert d.startswith("/"), "DATASET_DIR precisa ser absoluto"; p=pathlib.Path(".env"); p.write_text(re.sub(r"^DATASET_DIR=.*$$", lambda m: "DATASET_DIR="+d, p.read_text(), flags=re.M)); print("DATASET_DIR ->", d)' "$(DATASET_DIR)"
endif
	uv sync
	@chmod +x scripts/prepare_dataset.sh
	@$(MAKE) --no-print-directory hooks
	@echo "pronto. edite .env se precisar, depois: make check"

hooks:
	$(UV) prek install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push

check:
	@./scripts/prepare_dataset.sh

extract:        ; $(UV) pyramid extract --project all
classify:       ; $(UV) pyramid classify
snapshots:      ; $(UV) pyramid snapshots
metrics:        ; $(UV) pyramid metrics
attractiveness: ; $(UV) pyramid attractiveness --year all
project:        ; $(UV) pyramid project
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

clean:
	rm -rf output/* logs/*
