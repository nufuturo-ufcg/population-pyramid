# ESEM 2014: Figura 3

**Arquivo gerado:** `output/plots/esem14_fig3_transicoes.png`
**Comando:** `pyramid plot --figure pyramid-transition`

## O que a figura mostra

Os mesmos projetos da Figura 2, mas agora acompanhados ao longo do tempo: uma
pirâmide por ano, em junho de 2010, 2011, 2012 e 2013. A ideia é ver a
comunidade mudando de forma.

São três projetos: homebrew (que vira atrativo e cresce), blueprint-css (que
fica instável o tempo todo) e jekyll.

## O que saiu igual

- **A trajetória do homebrew.** Ele vira atrativo a partir de junho de 2011 e a
  pirâmide vai ganhando altura, exatamente como o artigo descreve.
- **A trajetória do blueprint-css.** Instável e encolhendo o período inteiro.
- **A forma do jekyll em 2013**, que o artigo chama de equilibrada.

## O que saiu diferente

**Jekyll em 2011.** O artigo classifica como *terminal*; a nossa replicação dá
*flutuante*. É a única classificação divergente da figura.

## Por que isso acontece

O jekyll fica em cima da linha. A classificação depende de dois números, e um
deles cai muito perto do limite que separa "terminal" de "flutuante". Uma
diferença mínima na contagem de pessoas empurra o projeto de um lado para o
outro. Não é erro de método. É um projeto de fronteira.

## Uma decisão que vale explicar: 2013

O dump de dados termina em outubro de 2013. Isso significa que o ano de 2013
está incompleto: faltam três meses.

A figura desenha 2013 mesmo assim, mas **não atribui categoria a 2013**. O
motivo é simples:

- A **forma** da pirâmide olha para trás: quem já está no projeto continua lá,
  então um ano incompleto não distorce o desenho.
- A **categoria** olha para frente: precisa saber quem ficou no ano seguinte.
  Esse ano seguinte não existe no dump.

O próprio artigo faz a mesma coisa: descreve a forma de 2013 sem dar quadrante.
Não anualizamos os nove meses para forçar uma classificação: isso inventaria
número.

Detalhamento: `docs/replicacao/discrepancias.md`, seções 11.1 e 13.
