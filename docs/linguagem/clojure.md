# Clojure: a pirâmide da linguagem

Saída da amostra de desenvolvimento, para conferência humana antes da coleta
grande. Reproduz com:

```bash
GHAPI_DIR=data/ghapi uv run python scripts/figuras_linguagem.py
```

Os números deste documento saem de `numeros.json`, gerado por esse comando.
Nenhum valor foi digitado à mão.

## A amostra

Três repositórios com Clojure como linguagem principal, escolhidos à mão:
`clj-kondo/clj-kondo`, `borkdude/edamame` e `weavejester/medley`. Eles somam um
escopo `Clojure` só.

| | |
|---|---|
| repositórios | 3 |
| eventos | 25.436 |
| contribuidores | 624 |
| primeiro evento | 2013-08-25 |
| último evento | 2026-08-21 |
| períodos de atividade (spans) | 1.014 |
| série de snapshots | 51 trimestres, 2013-12-31 a 2026-06-30 |

Eventos por tipo:

| tipo | quantidade |
|---|---|
| `issue_events` | 13.469 |
| `issue_comments` | 6.458 |
| `commits` | 3.282 |
| `pull_requests` | 1.429 |
| `pull_request_comments` | 761 |
| `commit_comments` | 37 |

`issue_events` é mais da metade da base. Ele já vem colapsado em 29,5% pela
limpeza de duplicata exata do contrato, porque rotular uma issue com três
etiquetas gera três eventos do mesmo ator no mesmo segundo.

Não aparece `issues` (abertura de issue) nesta lista. A taxonomia ativa em
`config/settings.yaml` (`taxonomy.variant: prose`) exclui esse tipo das duas
categorias, coding e non-coding, por decisão medida na replicação (ver
`discrepancias.md`, seção 32). O adaptador `ghapi` aplica esse mesmo corte.

## A pirâmide

![Pirâmide de Clojure em 2026-06-30](figuras/piramide_Clojure.png)

O eixo vertical é a idade desde a primeira contribuição, em bandas de 3 meses.
O lado direito é quem escreve código, o esquerdo é quem só conversa, e o cinza
no meio é quem começou conversando e passou a codar.

A forma é a de uma comunidade que renova pela base. A banda de menos de 1 ano
carrega a maior parte da população dos dois lados, e acima de 8 anos só sobra
um contribuidor ativo: `weavejester` (id 8780), na banda 52, com 4.691 dias
desde o primeiro evento em 2013-08-25, que é a criação do `medley`. Ele é o
dono do repositório mais velho da amostra e a única pessoa daquela época que
ainda aparece.

## Os dois números de população, e por que diferem

| | janela | não-código | código |
|---|---|---|---|
| a figura desenha | 12 meses | 39 | 42 |
| o CCR e o NCR contam | 3 meses | 6 | 22 |

A diferença é declarada e medida. A figura usa
`plots.pyramid_window_months: 12`, fixado pela leitura em pixel da Fig.2 do
ESEM14: com snapshot em fim de período, "janela de 12 meses" quer dizer "quem
contribuiu durante o ano". As métricas usam `periods.inactivity_months: 3`, que
é onde o IEICE16 crava o número. Ver `discrepancias.md`, seções 19 e 40.

Quem olhar a figura e a tabela lado a lado precisa saber disso: são duas
populações diferentes do mesmo escopo.

## Os números do artigo, no snapshot de 2026-06-30

| medida | valor |
|---|---|
| contribuidores de código | 22 |
| contribuidores de não-código | 6 |
| novatos (banda 0, até 3 meses) | 9 |
| experientes (banda 1 ou mais) | 19 |
| CCR | +0,727 |
| NCR | -0,526 |
| tipo | **C** |

CCR e NCR seguem a fórmula do IEICE16 p.1308, com corte em zero e o `moved`
contando do lado de código.

**Tipo C** quer dizer mais código que conversa, e mais experiente que novato.
No IEICE16 são os projetos que a comunidade já consolidou: quem está lá escreve
código, e a renovação por baixo está fraca no trimestre.

## A série completa

51 snapshots trimestrais. Últimos oito:

| snapshot | código | não-código | novatos | experientes | CCR | NCR | tipo |
|---|---|---|---|---|---|---|---|
| 2024-09-30 | 19 | 17 | 13 | 23 | +0,105 | -0,435 | C |
| 2024-12-31 | 19 | 6 | 8 | 17 | +0,684 | -0,529 | C |
| 2025-03-31 | 13 | 9 | 5 | 17 | +0,308 | -0,706 | C |
| 2025-06-30 | 11 | 9 | 4 | 16 | +0,182 | -0,750 | C |
| 2025-09-30 | 20 | 13 | 14 | 19 | +0,350 | -0,263 | C |
| 2025-12-31 | 11 | 12 | 6 | 17 | -0,083 | -0,647 | D |
| 2026-03-31 | 16 | 12 | 11 | 17 | +0,250 | -0,353 | C |
| 2026-06-30 | 22 | 6 | 9 | 19 | +0,727 | -0,526 | C |

Distribuição dos 51 trimestres: C em 28, A em 9, B em 9, D em 5.

CCR mediano de +0,350 e NCR mediano de -0,091 na série inteira. A leitura: a
população de Clojure fica consistentemente do lado do código, com o NCR
puxando para o lado experiente na maior parte dos trimestres. O último
snapshot (+0,727) é mais extremo que a mediana, mas na mesma direção dela, ao
contrário do que uma leitura de um snapshot isolado sugeriria sem olhar a
série.

## As outras linguagens da amostra

A coleta tem três repositórios Clojure, e o que aparece de outra linguagem são
os arquivos soltos dentro deles.

| linguagem | repositórios | eventos | pessoas | tipo |
|---|---|---|---|---|
| Clojure | 3 | 25.436 | 624 | C |
| Batchfile | 1 | 23 | 4 | sem ativo |
| Dockerfile | 1 | 20 | 6 | sem ativo |
| Java | 1 | 10 | 3 | sem ativo |
| Shell | 1 | 6 | 3 | C |
| Emacs Lisp | 2 | 4 | 2 | sem ativo |

As cinco últimas são ruído da amostra, e existem porque `outside_eligible: keep`
mantém o evento cujo caminho de arquivo aponta para uma linguagem que não é a
principal do repositório. Elas somem com `outside_eligible: drop`.

O escopo `unknown` recebe evento sem linguagem em repositório sem linguagem
detectada. Ele é contado e não vira figura, porque "unknown" não é uma
linguagem. Nesta amostra ele está vazio.

## O que não sai desta amostra, e por quê

Dois números do artigo não aparecem aqui. Os dois são limitação de tamanho de
amostra. O código roda; o que falta é escopo elegível suficiente para a
mediana e para o limiar significarem alguma coisa.

**Magnetismo e stickiness (MSR14 Tabela 2, Fig.2 e Fig.3).** O quadrante compara
o escopo com a mediana anual dos escopos elegíveis. Nesta amostra só Clojure
passa de `min_active_devs`, então a mediana é o próprio valor dele, o empate cai
do lado baixo, e os sete anos saem `terminal`. O magnetismo dá 1,0 por
construção, porque Clojure é o dataset inteiro. Medido rodando o estágio com a
trava removida.

**Projeção coorte-componente (IEICE16 Fig.8, Tabelas 3 e 4).** A elegibilidade é
mais de 100 contribuidores **ativos** no snapshot base. Clojure tem 624
contribuidores em treze anos e menos de 40 ativos no snapshot da classificação,
então nenhum escopo é elegível e a projeção sai vazia.

Os dois voltam quando a amostra tiver várias linguagens acima do corte. A trava
está em `UNIDADES`, no topo de `attractiveness.py` e de `projection.py`, com o
motivo escrito.

## Duas limitações desta coleta, herdadas do formato de entrada

Esta rodada não usa a mesma coleta da rodada maior (`data/clojure_first_round`,
1011 repositórios), que chegou num formato de CSV diferente do que o adaptador
`ghapi` lê. Duas limitações desse formato, que vão pesar no próximo documento
gerado a partir dele:

1. **Identidade quebrada entre commit e issue/PR.** A coleta em CSV identifica
   quem commitou pelo nome do git (por exemplo, "Nikita Prokopov") e quem abriu
   issue ou PR pelo login do GitHub (por exemplo, "tonsky"). Sem uma chave em
   comum, a mesma pessoa conta como duas na pirâmide quando ela faz as duas
   coisas.
2. **Arquivo do commit pré-filtrado.** A coleta em CSV só lista arquivo com
   extensão Clojure para cada commit, então não há como saber se aquele commit
   também tocou outra linguagem no mesmo repositório.

Um documento de sugestões para a próxima coleta cobre isso em detalhe, fora
deste repositório.

## O que conferir nesta validação

1. A forma da pirâmide bate com a de uma comunidade que renova pela base.
2. Os 624 contribuidores e os 25.436 eventos batem com a coleta.
3. CCR e NCR do snapshot batem com a tabela, lembrando que a figura usa janela
   de 12 meses e a métrica usa 3.
4. `borkdude` aparece uma vez só. Ele está nos três repositórios, com primeiro
   evento em 2019-02-04 no `medley`, e é essa a data que vale. Sob
   `unit: project` ele seria três pessoas, a mais nova estreando em agosto.
5. O tipo do último snapshot é C, e a série mostra que a maioria dos
   trimestres também é C.
