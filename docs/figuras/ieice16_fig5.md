# IEICE 2016: Figura 5

**Arquivo gerado:** `output/plots/ieice16_fig5_2013-09-30.png`
**Comando:** `pyramid plot --figure type-scatter`
**Conferir os números:** `output/plots/ieice16_fig5_2013-09-30.csv` traz um
projeto por linha, com NCR, CCR e o tipo atribuído. É o mesmo dado que virou
desenho.

## O que a figura mostra

Os 90 projetos do estudo em um gráfico de dispersão, na foto de 30/set/2013.

Os dois eixos medem se o projeto está ganhando ou perdendo gente, separando dois
grupos: quem escreve código e quem participa só de discussão. O gráfico é
dividido em quatro quadrantes, batizados de tipo A, B, C e D.

## O que saiu igual

- **A forma da nuvem de pontos** e a posição dos quadrantes. Os eixos seguem a
  figura publicada: NCR na horizontal, CCR na vertical, o que põe os quadrantes
  na ordem C, A, D, B (da esquerda para a direita, de cima para baixo).
- **Os oito projetos que o artigo nomeia como exemplo caem todos no tipo certo:**

| Projeto | Tipo |
|---|---|
| jquery/jquery | A |
| divio/django-cms | A |
| mxcl/homebrew | A |
| FortAwesome/Font-Awesome | B |
| gitlabhq/gitlabhq | B |
| cakephp/cakephp | C |
| Bukkit/CraftBukkit | C |
| rails/rails | D |

- **O total de projetos: 90**, igual ao artigo.

## O que saiu diferente

A contagem por quadrante desloca dois ou três projetos:

| | Artigo | Replicação |
|---|---|---|
| Tipo A | 23 | 26 |
| Tipo B | 42 | 40 |
| Tipo C | 18 | 15 |
| Tipo D | 3 | 4 |
| Classificados | 86 | 85 |
| Sem classificação | 4 | 5 |

## Por que isso acontece

A divisória entre os quadrantes é o valor zero: acima de zero o projeto está
ganhando gente, abaixo está perdendo. Vários projetos ficam com valores muito
perto de zero, e nesse caso a diferença de uma única pessoa decide o quadrante.

Foi verificado que **a sobra do tipo A e a falta do tipo C são o mesmo
deslocamento**: são projetos de fronteira que cruzaram a linha. A soma continua
90, e nenhum projeto nomeado no artigo mudou de lugar.

O projeto a mais sem classificação segue a mesma lógica: fica sem tipo quem não
tem gente suficiente para medir, e um projeto ficou logo abaixo desse limite.

Detalhamento: `docs/discrepancias.md`, seção 3.1.
