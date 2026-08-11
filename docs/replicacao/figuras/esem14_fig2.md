# ESEM 2014: Figura 2

**Arquivo gerado:** `output/plots/esem14_fig2_status_2011-12-31.png`
**Comando:** `pyramid plot --figure pyramid-grid-status`

## O que a figura mostra

Quatro projetos lado a lado, fotografados em 31/dez/2011: homebrew, paperclip,
clojure e blueprint-css. Cada um vira uma pirâmide.

A leitura é a de uma pirâmide populacional de país. Cada barra horizontal é uma
faixa de idade: só que aqui "idade" é há quanto tempo a pessoa está no projeto,
contada em trimestres. A base é quem chegou agora, o topo é quem está lá desde o
começo. As barras crescem para os dois lados: à esquerda quem só participa de
discussão, à direita quem escreve código.

Cada ano de idade tem quatro barras, uma por trimestre.

## O que saiu igual

- **blueprint-css: idêntico ao artigo.** Todas as barras, inclusive o espaço
  vazio entre o terceiro e o quarto trimestre.
- **O primeiro ano de todos os quatro projetos.** A base das quatro pirâmides
  (que é onde está a maior parte das pessoas) reproduz o artigo.
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
sobra é gente na barra errada. Não é gente a mais ou a menos.

## Onde está a diferença

Quase tudo é homebrew, e sempre no mesmo lugar: **no lado do código, nas barras
de baixo**: quem entrou no projeto há menos de um ano. Ali temos
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
idade nem o critério de quem está ativo. Esses critérios valeriam para os dois lados
igualmente. O que sobra é **a linha que separa "escreve código" de "só
participa da discussão"**.

O artigo lista os tipos de participação numa tabela, mas não diz de que lado
ficam alguns casos de fronteira. Cada caso desses que a gente classifica como
código e o artigo classificava como discussão empurra uma pessoa de um lado
para o outro da mesma barra, e é exatamente esse o desvio observado.

Já foram testadas e descartadas, porque pioravam o resultado:

- usar parâmetros de desenho diferentes por projeto;
- mudar a régua de idade (contar só os meses de atividade real em vez do tempo
  corrido desde a chegada);
- incluir movimentações de issue (abrir, fechar, reabrir) como atividade.

O experimento em aberto é revisar a fronteira código/discussão contra a tabela
de tipos do artigo.

## Nota de correção

Até a seção 31 do log, este documento e os números do log registravam diferenças
muito maiores (o total era 7734 em vez de 411). Era erro de conferência. Não era
erro da figura: o programa que lia a imagem do artigo numerava as barras de cima
para baixo e o nosso programa numera de baixo para cima, então a comparação casava
o topo do artigo com a base da nossa. A figura em si nunca mudou.

Detalhamento com números: `docs/replicacao/discrepancias.md`, seções 20, 21 e 31.

## O que já foi descartado (para não refazer)

Duas hipóteses sobre "quem entra em cada lado da pirâmide" foram testadas e
morreram. Ficam registradas aqui porque as duas pareciam boas no papel.

**"Abrir um pull request devia contar como discussão. Não devia contar como código."**
Parece razoável: abrir um PR é pedir para conversar sobre um código. Não é
necessariamente escrever código. Mas quando mudamos o PR de lado, o erro contra
o artigo triplica. E tem um argumento que fecha a questão: o painel do
blueprint-css hoje é idêntico ao do artigo, quadradinho por quadradinho. Ele só
fica idêntico com o PR contando como código. Qualquer outro arranjo estraga o
único painel que estava perfeito. Então: abrir PR é código, comentar num PR é
discussão. É assim no artigo e é assim que funciona.

**"O artigo conta quem abre issue, e é essa a gente que falta na discussão."**
O artigo de fato se contradiz: a tabela dele diz que abrir issue conta, o texto
dele diz que não. Testamos as duas versões. Contar quem abre issue traz gente
nova para o lado da discussão, sim, mas nas faixas de idade erradas, e o erro
total *piora* (de 411 para 647). O texto do artigo ganha da tabela do próprio
artigo. Seguimos com a versão do texto.

## O que ainda não bate no homebrew

O homebrew concentra quase todo o erro que sobrou (363 dos 411). E o erro tem
uma forma muito precisa:

| | nosso | artigo |
|---|---|---|
| lado do código | 1811 | 1611 |
| lado da discussão | 2071 | 2200 |

São **129 pessoas que nós chamamos de programador e o artigo chama de
conversa**, mais **71 pessoas que o artigo simplesmente não tem**. Os números
são exatos, e é isso que qualquer explicação futura precisa acertar.

### Uma ideia que parecia boa e não era

A primeira suspeita foi a idade. Hoje, quem escreve código tem a idade contada
desde o primeiro commit; quem só conversa, desde a primeira conversa. Se o
artigo contasse a idade de todo mundo desde a primeira aparição no projeto, os
programadores ficariam mais velhos e sairiam das faixas jovens, que é para
onde o nosso excesso aponta.

Testamos. Não é isso, e o motivo é simples: mudar a régua da idade muda a
**altura** em que a pessoa aparece na pirâmide. Nunca muda o **lado**. Como o nosso
problema é de lado (129 pessoas na coluna errada), nenhum acerto de idade,
janela ou faixa vai resolver. Isso fecha uma família inteira de tentativas.

### Duas regras de corte que também não eram

Existem 674 pessoas no homebrew que estão do lado do código apenas por terem
aberto um pull request, sem nunca ter feito um commit. O tamanho do grupo bate
com a forma do erro, então testamos duas maneiras de recortá-lo:

- **Trocar quem é considerado autor do pull request.** O banco tem duas colunas
  para isso e elas às vezes discordam. No homebrew discordam em 49 casos de
  13.171, e o número de autores distintos é idêntico. Não muda nada.
- **Exigir que o pull request tenha sido aceito.** Dos 674, 661 nunca tiveram
  nenhum pull request aceito. A regra tiraria 661 pessoas quando precisamos
  tirar 129. A correção seria desproporcional ao problema.

### Onde isso fica

O homebrew segue com essa diferença declarada e medida, sem hipótese em aberto
no momento. Os outros três painéis estão em erro 38 (paperclip), 11 (clojure) e
**0** (blueprint-css, idêntico ao artigo).

O detalhamento técnico, com as tabelas de cada rodada, está em
`docs/replicacao/discrepancias.md`, seção 33.
