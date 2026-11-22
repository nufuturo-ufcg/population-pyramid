#!/bin/bash
# Lança o experimento projecao-rq3 na VM (rode da raiz do repo na VM, `~/pyramid/repo`).
# Uso: bash scripts/granularidade/lancar_rq3.sh <pasta do experimento> <carga> <pasta de projecao-granularidade>
# 1. Diagnóstico das origens do S2 (parte 2a).
# 2. Elixir em S1 e S2 com teste de vazamento; confere e para se falhar.
# 3. Em paralelo: Clojure, OCaml, Zig e Python (S1 e S2 em processos separados) com teste de vazamento.
set -e
V=$1; CARGA=$2; GRAN=$3
PY=.venv/bin/python
S=scripts/granularidade
mkdir -p $V
$PY $S/diagnostico_origens_s2.py $CARGA clojure elixir ocaml python zig 2>&1 | grep -v -E "Warning|nanmean" > $V/diagnostico_origens_s2.txt
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas elixir --cenarios S1 S2 --vazamento --granularidade $GRAN 2>&1 | grep -v -E "Warning|nanmean" | tee -a $V/cenarios_elixir.log
$PY - <<PYEOF
import sys
import pandas as pd
for c in ("S1", "S2"):
    v = pd.read_csv("$V/unidades/elixir_%s_vazamento.csv" % c)
    ok = bool(v["estados_iguais"].all()) and bool((v["maior_diferenca_relativa"] < 1e-9).all()) and bool(v["controle_eventos_futuros_difere"].any())
    print("vazamento elixir", c, "ok" if ok else "FALHOU")
    if not ok:
        sys.exit("vazamento em Elixir %s: parei" % c)
PYEOF
nohup bash -c "
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas elixir clojure ocaml zig --cenarios S1 S2 --vazamento --granularidade $GRAN > $V/cenarios_pequenas.log 2>&1 &
p1=\$!
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas python --cenarios S1 --vazamento > $V/cenarios_python_s1.log 2>&1 &
p2=\$!
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas python --cenarios S2 --vazamento --granularidade $GRAN > $V/cenarios_python_s2.log 2>&1 &
p3=\$!
wait \$p1 \$p2 \$p3
echo TUDO_PRONTO > $V/tudo_pronto.txt
" > $V/lancar_rq3.out 2>&1 < /dev/null &
echo lançado
