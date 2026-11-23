#!/bin/bash
# Item 4 de `projecao-rq3/correcao-elegibilidade/hipoteses.md`: carga nova e o que vem depois, na VM.
# Uso (na raiz do repo na VM, `~/pyramid/repo`): bash scripts/granularidade/lancar_v3.sh <pasta v3>
# A pasta v3 tem `vitalidade_fontes_v3.yaml` (fontes com a API de linguagens e a regra de linhas repetidas).
# Ordem: 1. carga das cinco linguagens. 2. População P1 (granularidade, 12 meses).
# 3. Em paralelo: tabelas da RQ2 (rodada oficial) e a projecao-rq3 (Parte 2, cobertura-v2, repositórios por ano).
# Os resultados antigos não são tocados: tudo grava em <pasta v3>.
V=$1
PY=.venv/bin/python
S=scripts/granularidade
GRAN=$V/granularidade
export PYRAMID_FONTES_YAML=$V/vitalidade_fontes_v3.yaml
mkdir -p $V

echo "$(date -u +%H:%M:%S) 1 carga" >> $V/andamento.log
for l in clojure elixir ocaml zig python; do
  date; echo INICIO $l
  $PY scripts/origem_dos_novatos.py --saida $V/carga --linguagens $l --autores --fundir-duplicados --commits-pelo-sha --sem-contas-de-sistema --memoria 40GB --threads 24 2>&1 | tail -6
  echo FIM $l
done > $V/carga.log 2>&1
date >> $V/carga.log
echo "$(date -u +%H:%M:%S) 1 carga pronta" >> $V/andamento.log
$PY $S/compara_cargas.py $HOME/pyramid/projecao-granularidade/carga $V/carga clojure elixir ocaml zig > $V/compara_cargas.txt 2>&1
echo "$(date -u +%H:%M:%S) 1 comparação das cargas pronta" >> $V/andamento.log

echo "$(date -u +%H:%M:%S) 2 P1" >> $V/andamento.log
$PY $S/rodar.py --carga $V/carga --saida $GRAN --linguas clojure elixir ocaml zig python --passos 12 --pops P1 --vazamento > $V/granularidade.log 2>&1
echo "$(date -u +%H:%M:%S) 2 P1 pronta" >> $V/andamento.log

echo "$(date -u +%H:%M:%S) 3 RQ2 e rq3 em paralelo" >> $V/andamento.log
( $PY scripts/vitalidade_grade.py --saida $V/rodada --populacoes mais_de_uma_ocasiao --set rodada=oficial --processos 3 > $V/rodada.log 2>&1; echo "$(date -u +%H:%M:%S) 3 RQ2 pronta" >> $V/andamento.log ) &
bash $S/lancar_rq3.sh $V/rq3 $V/carga $GRAN > $V/rq3_lanca.log 2>&1
while [ ! -f $V/rq3/tudo_pronto.txt ]; do sleep 20; done
echo "$(date -u +%H:%M:%S) 3 rq3 pronta" >> $V/andamento.log
bash $S/lancar_cobertura.sh $V/cobertura-v2 $V/carga $GRAN > $V/cobertura_lanca.log 2>&1
while [ ! -f $V/cobertura-v2/tudo_pronto.txt ]; do sleep 20; done
echo "$(date -u +%H:%M:%S) 3 cobertura-v2 pronta" >> $V/andamento.log
$PY $S/repos_por_ano.py $V/carga $V/investigacao clojure elixir ocaml python zig > $V/investigacao.log 2>&1
echo "$(date -u +%H:%M:%S) 3 repos por ano pronta" >> $V/andamento.log
$PY $S/figuras_v3_dados.py $V/carga $V/figuras > $V/figuras_dados.log 2>&1
echo "$(date -u +%H:%M:%S) 3 dados das figuras prontos" >> $V/andamento.log
wait
echo "$(date -u +%H:%M:%S) TUDO PRONTO" >> $V/andamento.log
