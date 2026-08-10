# IEICE 2016: Figura 8

**Arquivo gerado:** `output/plots/ieice16_fig8_projecao_2013-09-30.png`
**Comando:** `pyramid plot --figure pyramid-projection-overlay`

## O que a figura mostra

A pirâmide real de um projeto com a **previsão desenhada por cima**.

O método é emprestado da demografia: olha-se quantas pessoas havia em cada faixa
de idade num momento passado, calcula-se a taxa com que elas passam para a faixa
seguinte, e projeta-se quantas deveriam estar em cada faixa hoje. A figura
compara essa previsão com o que de fato aconteceu.

A pergunta do artigo é se esse método prevê melhor do que a alternativa ingênua
("vai continuar tudo igual ao que estava").

## O que saiu igual

- **A conclusão principal do artigo se sustenta.** O método demográfico erra
  menos que a alternativa ingênua, e a diferença é estatisticamente
  significativa. Este é o achado central da seção, e ele reproduz.
- **A mecânica da figura**: pirâmide real, linha da previsão sobreposta, e os
  seis projetos que o artigo usa.

## O que saiu diferente

**Quantos projetos entram na conta: 34 aqui, 36 no artigo.** O critério é ter
mais de cem pessoas ativas na data-base. Dois projetos ficam logo abaixo desse
corte na nossa contagem.

**Os números célula a célula da tabela que acompanha a figura batem pouco.** De
40 comparações, 6 caem dentro de uma margem de 2%. Em 14 de 20 pares, a direção
do resultado é a mesma do artigo. O valor não é o mesmo.

**Um resultado secundário inverte.** O artigo conclui que a previsão de curto
prazo é melhor que a de longo prazo; na replicação acontece o contrário, e sem
significância estatística. É o único achado do artigo que não reproduz.

## Por que isso acontece

O artigo não detalha várias escolhas do cálculo: de qual data ele parte, com
que largura de faixa e, a mais importante, se a pirâmide projetada é a de
*todas as pessoas que já passaram pelo projeto* ou só a das *pessoas ativas*.

Essa última escolha muda tudo. Testamos as duas: só com a população ativa o
achado central do artigo aparece. Foi a leitura adotada, e está registrada como
decisão, não como fato do artigo.

Sobrando essas ambiguidades, os valores absolutos não convergem. O que fizemos
foi separar as duas coisas: o achado central, que reproduz e está checado, e os
números de célula, que não reproduzem e estão travados contra deriva. Ou seja,
o pipeline avisa se eles mudarem, mesmo sem bater com o artigo.

**Sobre o resultado que inverte:** ele depende de uma janela de tempo que o
artigo não especifica. Não forçamos parâmetro para fazê-lo bater: inverter um
resultado por escolha de parâmetro seria fabricar concordância.

Detalhamento: `docs/discrepancias.md`, seções 12.1 a 12.5.
