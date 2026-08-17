# IEICE 2016: Figura 7

**Arquivo gerado:** `output/plots/ieice16_fig7_centrados_2013-09-30.png`
**Comando:** `pyramid plot --figure pyramid-grid-centered`

## O que a figura mostra

Dois projetos, na foto de 30/set/2013: **mxcl/homebrew** e **rails/rails**.

São os dois casos que ficam no centro do gráfico da Figura 5, quase em cima do
cruzamento dos eixos, sem tender claramente para nenhum quadrante. O artigo os
separa em um painel próprio justamente porque a posição central é interessante:
mostra comunidade em equilíbrio, nem crescendo nem encolhendo de forma marcada.

## O que saiu igual

- **Os dois projetos são os mesmos** que o artigo escolhe.
- **Os tipos batem:** homebrew fica no tipo A, rails no tipo D.
- **As formas das duas pirâmides** reproduzem o original.
- **As escalas independentes** por painel, como no artigo.

## O que saiu diferente

Nada de substantivo.

## Observação

Esta é a figura onde o tipo D aparece: ele não cabe na Figura 6 porque o
dataset inteiro tem só três ou quatro projetos assim.

Vale notar que estes dois projetos, por estarem no centro do gráfico, são
exatamente o tipo de caso sensível a variação mínima de contagem. Que os dois
tenham caído no tipo certo é um sinal a favor do método, mas é apenas um sinal.
Com dois casos, não dá para tirar conclusão estatística.

## Janela da população

A pirâmide desenha quem contribuiu nos últimos **três meses**, que é a regra
que o próprio IEICE16 escreve na p.1306 e a mesma que produz o CCR e o NCR do
projeto. Com isso o painel mostra a população que gerou o rótulo de tipo ao
lado, e nenhum painel estoura a régua impressa no artigo. Para redesenhar com
outra janela: `pyramid plot --figure all --window-months 12`. Ver
`docs/replicacao/discrepancias.md`, seção 40.
