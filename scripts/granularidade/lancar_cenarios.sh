#!/bin/bash
# Lança o experimento de cenários IEICE16 na VM (rode da raiz do repo na VM, `~/pyramid/repo`).
# Uso: bash scripts/granularidade/lancar_cenarios.sh <pasta do experimento> <carga> <pasta de projecao-granularidade>
# 1. Elixir em S1 e S3 (R0 a R3 já entram) com teste de vazamento; confere o vazamento e para se falhar.
# 2. Em paralelo (os métodos usam um núcleo só): linguagens pequenas em S1, S3 e S2; Python com S1, S3 e S2 em processos separados.
# 3. A projeção por repositório por último (corte de mais de 100 primeiro), pequenas e Python em processos separados.
set -e
V=$1; CARGA=$2; GRAN=$3
PY=.venv/bin/python
S=scripts/granularidade
mkdir -p $V
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas elixir --cenarios S1 S3 --vazamento --granularidade $GRAN 2>&1 | grep -v -E "Warning|nanmean" | tee -a $V/cenarios_elixir_s1_s3.log
$PY - <<PYEOF
import sys
import pandas as pd
for c in ("S1", "S3"):
    v = pd.read_csv("$V/unidades/elixir_%s_vazamento.csv" % c)
    ok = bool(v["estados_iguais"].all()) and bool((v["maior_diferenca_relativa"] < 1e-9).all()) and bool(v["controle_eventos_futuros_difere"].any())
    print("vazamento elixir", c, "ok" if ok else "FALHOU")
    if not ok:
        sys.exit("vazamento em Elixir %s: parei" % c)
PYEOF
nohup bash -c "
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas elixir clojure ocaml zig --cenarios S1 S3 S2 --vazamento --granularidade $GRAN > $V/cenarios_pequenas.log 2>&1 &
p1=\$!
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas python --cenarios S1 --vazamento > $V/cenarios_python_s1.log 2>&1 &
p2=\$!
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas python --cenarios S3 --vazamento > $V/cenarios_python_s3.log 2>&1 &
p3=\$!
$PY $S/cenarios.py --carga $CARGA --saida $V --linguas python --cenarios S2 --vazamento --granularidade $GRAN > $V/cenarios_python_s2.log 2>&1 &
p4=\$!
wait \$p1 \$p2 \$p3 \$p4
echo CENARIOS_PRONTOS > $V/cenarios_prontos.txt
$PY $S/repos_ieice.py --carga $CARGA --saida $V --linguas elixir clojure ocaml zig --vazamento > $V/repos_pequenas.log 2>&1 &
p5=\$!
$PY $S/repos_ieice.py --carga $CARGA --saida $V --linguas python --vazamento > $V/repos_python.log 2>&1 &
p6=\$!
wait \$p5 \$p6
echo TUDO_PRONTO > $V/tudo_pronto.txt
" > $V/lancar_cenarios.out 2>&1 < /dev/null &
echo lançado
