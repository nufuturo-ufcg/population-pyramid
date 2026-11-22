#!/bin/bash
# Lança S1b e S3h (IEICE16 com horizonte de 12 meses) na VM (rode da raiz do repo na VM, `~/pyramid/repo`).
# Uso: bash scripts/granularidade/lancar_h12.sh <pasta do experimento> <carga>
# 1. Elixir em S1b e S3h (R0 a R3 saem juntos) com teste de vazamento; confere e para se falhar.
# 2. Em paralelo: linguagens pequenas e Python (S1b e S3h em processos separados).
set -e
V=$1; CARGA=$2
PY=.venv/bin/python
S=scripts/granularidade
mkdir -p $V
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas elixir --cenarios S1b S3h --vazamento 2>&1 | grep -v -E "Warning|nanmean" | tee -a $V/cenarios_elixir.log
$PY - <<PYEOF
import sys
import pandas as pd
for c in ("S1b", "S3h"):
    v = pd.read_csv("$V/unidades/elixir_%s_vazamento.csv" % c)
    ok = bool(v["estados_iguais"].all()) and bool((v["maior_diferenca_relativa"] < 1e-9).all()) and bool(v["controle_eventos_futuros_difere"].any())
    print("vazamento elixir", c, "ok" if ok else "FALHOU")
    if not ok:
        sys.exit("vazamento em Elixir %s: parei" % c)
PYEOF
nohup bash -c "
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas elixir clojure ocaml zig --cenarios S1b S3h --vazamento > $V/cenarios_pequenas.log 2>&1 &
p1=\$!
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas python --cenarios S1b --vazamento > $V/cenarios_python_s1b.log 2>&1 &
p2=\$!
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas python --cenarios S3h --vazamento > $V/cenarios_python_s3h.log 2>&1 &
p3=\$!
wait \$p1 \$p2 \$p3
echo TUDO_PRONTO > $V/tudo_pronto.txt
" > $V/lancar_h12.out 2>&1 < /dev/null &
echo lançado
