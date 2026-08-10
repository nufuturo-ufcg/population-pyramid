.PHONY: setup check run-all extract classify snapshots metrics attractiveness project validate plots figuras-artigo test clean
.DEFAULT_GOAL := help

UV := uv run

help:
	@echo "make setup [DATASET_DIR=/caminho/absoluto]  cria .env e instala deps"
	@echo "make check                                  valida a fonte de dados"
	@echo "make run-all                                pipeline inteiro (estagios 1-8)"
	@echo "make validate                               compara com config/checkpoints.yaml"
	@echo "make test                                   testes unitarios"

setup:
	@test -f .env || cp .env.example .env
ifdef DATASET_DIR
	@python3 - "$(DATASET_DIR)" <<< 'import re,sys,pathlib; p=pathlib.Path(".env"); d=sys.argv[1]; assert d.startswith("/"), "DATASET_DIR precisa ser absoluto"; p.write_text(re.sub(r"^DATASET_DIR=.*$$", "DATASET_DIR="+d, p.read_text(), flags=re.M)); print("DATASET_DIR ->", d)'
endif
	uv sync
	@chmod +x scripts/prepare_dataset.sh
	@echo "pronto. edite .env se precisar, depois: make check"

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

clean:
	rm -rf output/* logs/*
