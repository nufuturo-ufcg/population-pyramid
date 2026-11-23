#!/bin/bash
# Lança o experimento projecao-rq3/cobertura na VM (rode da raiz do repo na VM, `~/pyramid/repo`).
# Uso: bash scripts/granularidade/lancar_cobertura.sh <pasta do experimento> <carga> <pasta de projecao-granularidade>
# 1. Elixir no S2 com teste de vazamento; confere e para se falhar.
# 2. Em paralelo: Clojure, OCaml e Python no S2 com teste de vazamento.
set -e
V=$1; CARGA=$2; GRAN=$3
PY=.venv/bin/python
S=scripts/granularidade
mkdir -p $V
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas elixir --cenarios S2 --vazamento --granularidade $GRAN 2>&1 | grep -v -E "Warning|nanmean" | tee -a $V/cenarios_elixir.log
$PY - <<PYEOF
import sys
import pandas as pd
v = pd.read_csv("$V/unidades/elixir_S2_vazamento.csv")
ok = bool(v["estados_iguais"].all()) and bool((v["maior_diferenca_relativa"] < 1e-9).all()) and bool(v["controle_eventos_futuros_difere"].any()) and bool(v["controle_promocoes_difere"].any())
print("vazamento elixir S2", "ok" if ok else "FALHOU")
if not ok:
    sys.exit("vazamento em Elixir S2: parei")
PYEOF
nohup bash -c "
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas clojure ocaml --cenarios S2 --vazamento --granularidade $GRAN > $V/cenarios_pequenas.log 2>&1 &
p1=\$!
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas python --cenarios S2 --vazamento --granularidade $GRAN > $V/cenarios_python_s2.log 2>&1 &
p2=\$!
wait \$p1 \$p2
echo TUDO_PRONTO > $V/tudo_pronto.txt
" > $V/lancar_cobertura.out 2>&1 < /dev/null &
echo lançado
