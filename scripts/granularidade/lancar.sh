#!/bin/bash
# Lança o experimento de granularidade na VM (rode da raiz do repo na VM, `~/pyramid/repo`).
# Uso: bash scripts/granularidade/lancar.sh <pasta do experimento> <carga> <referências> [medir]
#   medir: só mede Python em P2 com passo de 15 dias (3 origens), imprime tempo e memória e para.
# Sem `medir`:
# 1. Elixir em 12 meses (P0, P1, P2) e a conferência com os experimentos anteriores; para se algo não confere.
# 2. Todas as linguagens, do passo mais longo ao mais curto (as duas populações de um passo antes do seguinte), em segundo plano: duas cadeias, Python à parte.
set -e
V=$1; CARGA=$2; REFS=$3
PY=.venv/bin/python
S=scripts/granularidade
if [ "$4" = "medir" ]; then
  /usr/bin/time -v $PY $S/rodar.py --carga $CARGA --saida $V/medicao --linguas python --passos 0.5 --pops P2 --amostra 3 --refazer 2>&1 | tee $V/medicao_python.log | grep -E "estado pronto|por origem|pico|Maximum resident|Elapsed"
  exit 0
fi
$PY $S/rodar.py --carga $CARGA --saida $V --linguas elixir --passos 12 --pops P0 P1 P2 --vazamento 2>&1 | tee -a $V/rodar_elixir_12.log
$PY $S/conferir_p0.py $V elixir $REFS --estrito 2>&1 | tee -a $V/conferencia_elixir.log
nohup sh -c "$PY $S/rodar.py --carga $CARGA --saida $V --linguas elixir clojure ocaml zig --pops P0 P1 P2 --vazamento > $V/rodar_pequenas.log 2>&1" < /dev/null &
nohup sh -c "$PY $S/rodar.py --carga $CARGA --saida $V --linguas python --pops P0 P1 P2 --vazamento > $V/rodar_python.log 2>&1" < /dev/null &
echo lançado
