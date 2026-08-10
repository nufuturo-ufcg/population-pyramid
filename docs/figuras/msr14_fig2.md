# MSR 2014 — Figura 2

**Arquivo gerado:** `output/plots/msr14_fig2_2011.png`
**Comando:** `pyramid plot --figure magnet-sticky`

## O que a figura mostra

Um gráfico de dispersão com dois eixos:

- **atratividade** — o quanto o projeto puxa gente nova;
- **retenção** — o quanto o projeto segura quem já chegou.

As linhas que dividem o gráfico em quatro quadrantes não são valores fixos: são
as medianas do próprio conjunto de projetos. Cada quadrante recebe um nome
(atrativo, flutuante, estagnado, terminal).

## O que saiu igual

- **A estrutura da tabela do artigo: 41 de 41.** O artigo marca algumas células
  com traço (projeto sem atividade naquele ano) e outras com asterisco (menos de
  dez pessoas, poucas para classificar). Todas as 41 caem no mesmo lugar na
  replicação.
- **48 das 55 classificações, ou 87%.**

## O que saiu diferente

Sete células, de um total de 55:

| Projeto | Ano | Artigo | Replicação |
|---|---|---|---|
| xbmc/xbmc | 2007 | atrativo | flutuante |
| xbmc/xbmc | 2009 | atrativo | estagnado |
| jquery/jquery | 2010 | flutuante | atrativo |
| chriseppstein/compass | 2010 | flutuante | terminal |
| scala/scala | 2010 | flutuante | sem atividade |
| django/django | 2011 | atrativo | estagnado |
| mojombo/jekyll | 2011 | terminal | flutuante |

## Por que isso acontece

**Cinco das sete são projetos de fronteira.** Como as divisórias do gráfico são
medianas, um projeto que cai quase em cima da linha muda de quadrante com
qualquer variação mínima. Basta uma pessoa a mais ou a menos na contagem. Isso
não indica método errado — indica que o projeto está no limite, e o artigo tem
o mesmo problema.

**Duas têm causa própria, e não são culpa da classificação:**

- **scala em 2010** — o dump tem um buraco de 18 meses nesse projeto. Não há
  atividade registrada no período, então não há o que classificar. É limitação
  dos dados de origem, não da replicação.
- **django em 2011** — o repositório ainda não tinha migrado para o GitHub
  nessa época. O que o dump enxerga é uma fração da atividade real.

Nos dois casos, a checagem foi feita contra a fonte externa (o próprio GitHub) e
confirmou que o dado está faltando na origem.

Detalhamento: `discrepancias.md` §16 e §17.
