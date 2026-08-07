# ESEM 2014 — Figura 2

**Arquivo gerado:** `output/plots/esem14_fig2_status_2011-12-31.png`
**Comando:** `pyramid plot --figure pyramid-grid-status`

## O que a figura mostra

Quatro projetos lado a lado, fotografados em 31/dez/2011: homebrew, paperclip,
clojure e blueprint-css. Cada um vira uma pirâmide.

A leitura é a de uma pirâmide populacional de país. Cada barra horizontal é uma
faixa de idade — só que aqui "idade" é há quanto tempo a pessoa está no projeto,
contada em trimestres. A base é quem chegou agora, o topo é quem está lá desde o
começo. As barras crescem para os dois lados: à esquerda quem só participa de
discussão, à direita quem escreve código.

Cada ano de idade tem quatro barras, uma por trimestre.

## O que saiu igual

- **blueprint-css: idêntico ao artigo.** Todas as barras, inclusive o espaço
  vazio entre o terceiro e o quarto trimestre.
- **O primeiro ano de todos os quatro projetos.** A base das quatro pirâmides —
  que é onde está a maior parte das pessoas — reproduz o artigo.
- **A forma geral e a escala.** Cada painel tem escala própria, e a nossa bate
  com a do artigo: 750 no homebrew, 100 no paperclip, 10 no clojure, 5 no
  terminal.
- **O status de cada projeto** (atrativo, flutuante, estagnado, terminal) sai
  correto nos quatro.

## O quanto saiu diferente

Somando pessoa por pessoa, em cada barra, a diferença entre a nossa figura e a
do artigo:

| Projeto | Pessoas no artigo | Na nossa | Diferença total |
|---|---|---|---|
| blueprint-css | 13 | 13 | **nenhuma** |
| paperclip | 519 | 524 | 38 pessoas (7%) |
| clojure | 46 | 49 | 11 pessoas |
| homebrew | 3810 | 3882 | 363 pessoas (9%) |

O tamanho da população bate nos quatro projetos (diferença de até 2%). O que
sobra é gente na barra errada, não gente a mais ou a menos.

## Onde está a diferença

Quase tudo é homebrew, e sempre no mesmo lugar: **no lado do código, nas barras
de baixo** — quem entrou no projeto há menos de um ano. Ali temos
consistentemente umas 14% de pessoas a mais que o artigo.

| Barra | Código, no artigo | Código, na nossa |
|---|---|---|
| a base (chegou nos últimos 3 meses) | 320 | 368 |
| 3 a 6 meses | 393 | 451 |
| 6 a 9 meses | 294 | 336 |
| 9 a 12 meses | 332 | 380 |

Do lado da discussão, nas mesmas barras, a diferença é de menos de 3%
(581/565, 740/733, 365/357, 219/216).

## Por que isso acontece

Como o lado da discussão bate e o do código não, o problema não é a régua de
idade nem o critério de quem está ativo — esses valeriam para os dois lados
igualmente. O que sobra é **a linha que separa "escreve código" de "só
participa da discussão"**.

O artigo lista os tipos de participação numa tabela, mas não diz de que lado
ficam alguns casos de fronteira. Cada caso desses que a gente classifica como
código e o artigo classificava como discussão empurra uma pessoa de um lado
para o outro da mesma barra — que é exatamente o desvio observado.

Já foram testadas e descartadas, porque pioravam o resultado:

- usar parâmetros de desenho diferentes por projeto;
- mudar a régua de idade (contar só os meses de atividade real em vez do tempo
  corrido desde a chegada);
- incluir movimentações de issue (abrir, fechar, reabrir) como atividade.

O experimento em aberto é revisar a fronteira código/discussão contra a tabela
de tipos do artigo.

## Nota de correção

Até a §31 do log, este documento e os números do log registravam diferenças
muito maiores (o total era 7734 em vez de 411). Era erro de conferência, não da
figura: o programa que lia a imagem do artigo numerava as barras de cima para
baixo e o nosso programa numera de baixo para cima, então a comparação casava o
topo do artigo com a base da nossa. A figura em si nunca mudou.

Detalhamento com números: `discrepancias.md` §20, §21, §31.
