#!/bin/bash
# Variante da carga v3 com leitura sequencial do duckdb (`parallel=false`), nas cinco linguagens, e o que vem depois.
# Uso (na raiz do repo na VM): bash scripts/granularidade/lancar_v3b.sh <pasta v3b>
# A pasta v3b tem `vitalidade_fontes_v3b.yaml` (igual ao v3 com `leitura_sequencial: true` em cada linguagem). A carga de Python
# já foi lançada à parte em <pasta>/carga.log; o script espera o FIM dela. Nada da v3 é tocado.
V=$1
PY=.venv/bin/python
S=scripts/granularidade
GRAN=$V/granularidade
export PYRAMID_FONTES_YAML=$V/vitalidade_fontes_v3b.yaml
mkdir -p $V

echo "$(date -u +%H:%M:%S) 1 carga de clojure, elixir, ocaml e zig" >> $V/andamento.log
for l in clojure elixir ocaml zig; do
  date; echo INICIO $l
  $PY scripts/origem_dos_novatos.py --saida $V/carga --linguagens $l --autores --fundir-duplicados --commits-pelo-sha --sem-contas-de-sistema --memoria 20GB --threads 12 2>&1 | tail -6
  echo FIM $l
done > $V/carga_pequenas.log 2>&1
echo "$(date -u +%H:%M:%S) 1 carga das pequenas pronta" >> $V/andamento.log
while ! grep -q FIM $V/carga.log; do sleep 30; done
echo "$(date -u +%H:%M:%S) 1 carga de python pronta" >> $V/andamento.log
$PY $S/compara_cargas.py $HOME/pyramid/v3/carga $V/carga clojure elixir ocaml zig python > $V/compara_cargas.txt 2>&1

echo "$(date -u +%H:%M:%S) 2 P1" >> $V/andamento.log
$PY $S/rodar.py --carga $V/carga --saida $GRAN --linguas clojure elixir ocaml zig python --passos 12 --pops P1 --vazamento > $V/granularidade.log 2>&1
echo "$(date -u +%H:%M:%S) 2 P1 pronta" >> $V/andamento.log

echo "$(date -u +%H:%M:%S) 3 RQ2 e rq3 em paralelo" >> $V/andamento.log
mkdir -p $V/rodada
for l in clojure elixir ocaml zig python; do
  mkdir -p $V/rodada/$l
  [ -e $V/rodada/$l/origem ] || ln -s $V/carga/$l/origem $V/rodada/$l/origem
done
( $PY scripts/vitalidade_grade.py --saida $V/rodada --populacoes mais_de_uma_ocasiao --set rodada=oficial --processos 3 > $V/rodada.log 2>&1; echo "$(date -u +%H:%M:%S) 3 RQ2 pronta" >> $V/andamento.log ) &
bash $S/lancar_rq3.sh $V/rq3 $V/carga $GRAN > $V/rq3_lanca.log 2>&1
while [ ! -f $V/rq3/tudo_pronto.txt ]; do sleep 20; done
echo "$(date -u +%H:%M:%S) 3 rq3 pronta" >> $V/andamento.log
bash $S/lancar_cobertura.sh $V/cobertura-v2 $V/carga $GRAN > $V/cobertura_lanca.log 2>&1
while [ ! -f $V/cobertura-v2/tudo_pronto.txt ]; do sleep 20; done
echo "$(date -u +%H:%M:%S) 3 cobertura-v2 pronta" >> $V/andamento.log
$PY $S/diagnostico_otimista.py $V/carga $V/cobertura-v2 $V/cobertura-v2/diagnostico_otimista.csv clojure elixir ocaml python > $V/diagnostico_otimista.log 2>&1
$PY $S/repos_por_ano.py $V/carga $V/investigacao clojure elixir ocaml python zig > $V/investigacao.log 2>&1
$PY $S/figuras_v3_dados.py $V/carga $V/figuras > $V/figuras_dados.log 2>&1
echo "$(date -u +%H:%M:%S) 3 repos por ano, diagnóstico e dados das figuras prontos" >> $V/andamento.log
wait
echo "$(date -u +%H:%M:%S) TUDO PRONTO" >> $V/andamento.log
