# Estado do projeto, 2026-08-10

Replicação independente de Onoue et al. (ESEM'14, MSR'14, IEICE'16) sobre o dump MSR'14 do
GHTorrent (out/2013, 90 projetos). O pipeline roda do zero em máquina limpa e reproduz o próprio
`validation_report.md`. São 167 checks: **97 batem, 70 divergem**. Os 70 estão declarados aqui,
nenhum em aberto sem análise.

O achado central do IEICE'16 se sustenta. No agregado, prever crescimento por faixa etária erra
menos que a previsão ingênua (cohort 0,3894 contra baseline 0,5000, p = 0,0124).

Este documento lista o que diverge, com a explicação mais provável e o que já testamos sem sucesso.
Onde o número bate, ele aparece só como linha de placar, sem discussão.

## Escopo: quais projetos e quais pessoas entram

- **Universo.** Os 90 projetos do dump. O escopo é sempre o id do projeto, nunca o nome, porque
  `symfony` aparece duas vezes na lista.
- **Contribuidor vivo em T.** Teve atividade nos 3 meses anteriores ao snapshot T.
- **Tipos A-D (item 1).** Entram os projetos com ao menos um contribuidor vivo no snapshot de
  2013-09-30. Passam 85 dos 90, e 5 ficam sem contribuidor vivo. O artigo classifica 86 e deixa
  4 de fora.
- **Projeção (itens 4 a 8).** O IEICE'16 trabalha com "the 36 projects that have more than 100
  contributors" (p.1311). Aplicamos "more than" ao pé da letra: corte `> 100` sobre o número de
  contribuintes do projeto no snapshot base de 2013-03-31. Sobram 34 projetos. O 35º tem
  exatamente 100 contribuintes e entraria com `>=`, o que seria calibrar o corte pelo resultado
  esperado.
- **2013.** O dump acaba em out/2013, então o ano é right-censored. Ele renderiza pirâmide, que é
  medida de estoque, e fica sem quadrante, que exige o ano seguinte.

## Como ler e como conferir

Cada item termina em **Conferir**, que dá o nome do check dentro de
[`output/validation_report.md`](../output/validation_report.md), onde o valor do artigo e o nosso
ficam lado a lado, e o arquivo que desenha o número. As figuras estão em
[`output/plots/`](../output/plots/), a leitura em prosa de cada uma em
[`docs/figuras/`](figuras/). Quem quiser refazer tudo do zero acha o passo a passo no
[`README.md`](../README.md).

Os nomes de check terminam no id do projeto. O nome não serve de chave: `symfony` aparece duas vezes na
lista dos 90. Os ids que aparecem neste documento:

- **79163** é `mxcl/homebrew`
- **79166** é `mojombo/jekyll`
- **104307** é `thoughtbot/paperclip`
- **19786** é `clojure/clojure`
- **101472** é `joshuaclayton/blueprint-css`

Assim, o check `attractiveness.2011.79166` se lê "o quadrante do jekyll em 2011".

**L1** é a medida de desacordo usada aqui: a soma das diferenças, uma a uma, entre o artigo e a
réplica. L1 = 0 é acordo perfeito. Nos tipos (item 1) a unidade é projeto; na Fig.2 do ESEM'14
(item 9) a unidade é pessoa dentro de uma barra.

---

## 1. Distribuição dos Tipos A-D (IEICE'16, Fig.5): L1 = 9 projetos

| | A | B | C | D | classificados | sem contribuidor |
|---|---|---|---|---|---|---|
| artigo | 23 | 42 | 18 | 3 | 86 | 4 |
| replicação | 26 | 40 | 15 | 4 | 85 | 5 |

O L1 é a soma coluna a coluna dessa tabela: 3 + 2 + 3 + 1 = 9. Como cada projeto trocado de caixa
sai de uma coluna e entra em outra, isso é da ordem de 4 a 5 projetos com rótulo diferente, e o
saldo cai todo no mesmo eixo: sobra A, falta C.

| artigo | replicação |
|---|---|
| ![](figuras/artigo/ieice16_fig5_artigo.png) | ![](../output/plots/ieice16_fig5_2013-09-30.png) |
| ![](figuras/artigo/ieice16_fig6_artigo.png) | ![](../output/plots/ieice16_fig6_tipos_2013-09-30.png) |

**Explicação mais provável: o artigo usa uma definição de "newcomer" mais generosa que a nossa.**
O desvio se concentra em 4 projetos grandes que damos como A e o artigo dá como C. Os projetos
pequenos batem quase de graça. Fechar o buraco exige reclassificar de 25% a 30% dos novatos como
experientes, o que é diferença de critério.

O que já testamos e não explica:

- Empate na fronteira: o NCR tem um vão vazio entre -0,25 e +0,08, nenhum projeto está colado no zero.
- Janela de morte por silêncio maior que 3 meses: com 6 meses a distribuição vira 3/2/34/49 e some com os 65 projetos A+B do artigo.
- Elegibilidade por população viva no lugar do histórico: dá 30 projetos (5/17/6/2, L1 = 8), erra o total e mantém os A.
- Base de idade (`age_basis`) e largura de banda: varridas nas duas leituras possíveis, o eixo A contra C não se mexe.
- Desempate no zero: a Tabela 2 do MSR'14 é inconsistente nele, 4 empates pedem `>` e 2 pedem `>=`, e a leitura literal de "higher than" é a que maximiza acordo.

**Onde conferir:**

- No [`validation_report.md`](../output/validation_report.md): as quatro linhas com a contagem de
  cada tipo, a linha com o total de projetos classificados e a linha com os não classificados
  (`types.counts.A-D`, `types.total_classified`, `types.unclassified`).
- A figura: [`output/plots/ieice16_fig5_2013-09-30.png`](../output/plots/ieice16_fig5_2013-09-30.png).
- A leitura em prosa: [`docs/figuras/ieice16_fig5.md`](figuras/ieice16_fig5.md).

## 2. `mojombo/jekyll` em 2011: artigo `terminal`, replicação `floating`

Os outros 4 projetos nomeados na Fig.2 do ESEM'14 batem, 4 de 5.

| artigo | replicação |
|---|---|
| ![](figuras/artigo/msr14_fig2_artigo.png) | ![](../output/plots/msr14_fig2_2011.png) |

**Explicação mais provável: o mesmo viés do item 1.** Magnetismo é a contagem de novatos sobre o
total, então classificar novato demais empurra o jekyll para cima da mediana e de `terminal` para
`floating`. O jekyll é o projeto que mais cresceu no período (14, 40, 29, 77 e 81 devs por ano),
logo o mais exposto ao critério de primeira aparição. Nossa série reproduz a trajetória do artigo
adiantada em um ano.

O que já testamos e não explica:

- Offset global de um ano na série: o deslocamento é local ao jekyll, os outros projetos ficam no lugar.
- Janela de ano civil no lugar de janela móvel: não muda o quadrante do jekyll.

**Onde conferir:**

- No [`validation_report.md`](../output/validation_report.md): a linha do quadrante do jekyll em
  2011, que é a que erra, e as quatro linhas que batem, dos outros projetos da mesma figura
  (homebrew, paperclip, clojure e blueprint-css).
- A figura: [`output/plots/msr14_fig2_2011.png`](../output/plots/msr14_fig2_2011.png).

## 3. Tabela 2 do MSR'14, 48 de 55 células (87%)

Essa tabela dá o quadrante de cada projeto em cada ano (`attractive`, `floating`, `stagnant`,
`terminal`), a partir de magnetismo e stickiness comparados à mediana do ano. São 12 projetos, anos
de 2004 a 2011, 55 células preenchidas. Ela é artefato publicado do MSR'14, então entra no critério
de aceite célula a célula.

![](figuras/artigo/msr14_tab2_artigo.png)

| ano | projeto | artigo | replicação | por quê |
|---|---|---|---|---|
| 2007 | `xbmc/xbmc` | attractive | floating | empate exato na mediana |
| 2009 | `xbmc/xbmc` | attractive | stagnant | empate exato na mediana |
| 2010 | `scala/scala` | floating | n/a | zero eventos de código em 2010 no dump |
| 2010 | `jquery/jquery` | floating | attractive | 5,1% da mediana |
| 2010 | `chriseppstein/compass` | floating | terminal | 4,6% da mediana |
| 2011 | `django/django` | attractive | stagnant | repo ainda não estava no GitHub |
| 2011 | `mojombo/jekyll` | terminal | floating | item 2 |

**Explicação mais provável: desempate na mediana somado a buracos de cobertura do dump.** Longe da
linha, com margem acima de 10%, o acordo é 37 de 37, tirando jekyll e django, que têm causa
própria. As duas células de margem 0,0% são o projeto que define a mediana do ano naquele eixo, e
o artigo resolve o empate para o outro lado. `scala` e `django` são buracos de dado compatíveis
com outro *vintage* do GHTorrent, que recompleta o passado a cada coleta.

O que já testamos e não explica:

- Correção sistemática única no magnetismo: `django` e `jquery` pedem correção em direções opostas no mesmo eixo.
- Inverter a regra de empate para o lado alto: corrige as 2 células do xbmc e quebra 4 que hoje batem, o total cai de 48 para 46.
- Varredura de `min_active_devs` e de `stickiness_scope`: o ótimo continua na configuração atual.

A mesma grade, na versão da replicação, está em
[`output/plots/msr14_tab2_replicacao.md`](../output/plots/msr14_tab2_replicacao.md), no formato do
artigo: quadrante de 2011 na primeira coluna, um projeto por linha, um ano por coluna, e as sete
células que discordam em negrito com o valor do artigo ao lado.

**Onde conferir:**

- No [`validation_report.md`](../output/validation_report.md): a linha com a concordância geral da
  tabela e uma linha por célula, nomeada por ano e projeto (`msr14.tab2.<ano>.<id do projeto>`).
- A grade lado a lado: [`output/plots/msr14_tab2_replicacao.md`](../output/plots/msr14_tab2_replicacao.md).
- Os dados por trás: `output/attractiveness/attractiveness.parquet`.

## 4. Projeção: 34 projetos elegíveis, o artigo diz 36

Detalhe do corte na seção "Escopo". Dois projetos ficam em cima da linha dos 100. Mexer no corte
para chegar a 36 ajustaria o método ao resultado, então mantivemos 34, com a contagem travada por
teste.

**Onde conferir:**

- No [`validation_report.md`](../output/validation_report.md): a linha com o número de projetos
  elegíveis para a projeção (`projection.n_projects`).
- Os dados por trás: `output/projection/projection.parquet`.

## 5. Tabela 3 do IEICE'16, célula a célula: 6 de 40 dentro de ±2 p.p.

A tabela mede o erro de previsão (ABRE, quanto a projeção erra em média) em 40 células: 5 grupos de
projeto (A, B, C, D e o agregado) × 4 categorias de contribuidor (código, discussão, quem mudou de
lado, todos) × 2 métodos (por faixa etária e ingênuo). A tolerância de ±2 p.p. é dura de propósito:
o que interessa aqui é a direção, que está no item 6. O valor absoluto de cada célula fica em segundo plano.

**Explicação mais provável: a base é outra.** 34 projetos contra 36, coortes diferentes, e o ABRE
de coorte pequena é dominado por ruído de uma pessoa. A comparação célula a célula fica pouco
conclusiva nos dois sentidos, inclusive nas células que casaram.

**Onde conferir:**

- No [`validation_report.md`](../output/validation_report.md): as 40 linhas de erro de previsão,
  uma por célula, e a trava que registra quantas caíram dentro de ±2 p.p.
- A tabela: [`output/plots/ieice16_tab3_abre.csv`](../output/plots/ieice16_tab3_abre.csv) e a
  leitura em prosa em [`output/plots/ieice16_tab3_tab4.md`](../output/plots/ieice16_tab3_tab4.md).

## 6. Direção da comparação: 14 de 20 pares batem

São os mesmos 20 pares do item 5 (cada célula por faixa etária contra a sua ingênua), agora sem
olhar o valor: só quem erra menos, que é o que o artigo defende. Erram `A.non_coding`, `B.non_coding`,
`B.moved` (empate), `B.coding`, `D.moved` e `All.non_coding`.

**Explicação mais provável: `non_coding` é a categoria doente.** É a única das quatro que inverte
de sinal também no agregado (artigo 0,5000 contra 0,6667; replicação 0,5804 contra 0,5000) e sem
significância (p = 0,1145). Mesma família de causa do item 5, porque as coortes de discussão são
as mais ralas.

**Onde conferir:**

- No [`validation_report.md`](../output/validation_report.md): as 20 linhas de direção, uma por
  par, e a trava que registra quantos pares batem.
- A tabela: [`output/plots/ieice16_tab3_abre.csv`](../output/plots/ieice16_tab3_abre.csv).

## 7. Significância estatística: o artigo acha 16, nós achamos 5

Nos mesmos 20 pares, o teste pergunta se a vantagem do item 6 é grande o bastante para não ser
sorte. O artigo acha significância em 16 deles. A replicação confirma **5**: `A.non_coding`,
`C.moved`, `All.moved`, `All.coding` e `All.all`. Em 2 pares ocorre o inverso, com significância
na replicação e não no artigo (`A.coding` p = 0,0003; `C.non_coding` p = 0,0216).

**Explicação mais provável: poder estatístico.** n menor (34 projetos) e coortes ralas nas faixas
altas. O sinal existe e sobrevive no agregado, com força menor do que o artigo sugere. A vantagem
da previsão por faixa se dilui quando o recorte é isolado.

**Onde conferir:**

- No [`validation_report.md`](../output/validation_report.md): as 20 linhas do teste, uma por par.
- A tabela: [`output/plots/ieice16_tab4_wilcoxon.csv`](../output/plots/ieice16_tab4_wilcoxon.csv).

## 8. Curto contra longo prazo: ordem trocada

| | short | long | p |
|---|---|---|---|
| artigo | 0,4055 | 0,3333 | 0,0460 |
| replicação | 0,3363 | 0,4816 | 0,1768 |

| artigo | replicação |
|---|---|
| ![](figuras/artigo/ieice16_fig8_artigo.png) | ![](../output/plots/ieice16_fig8_projecao_2013-09-30.png) |

**Explicação mais provável: cauda longa rala.** Com janela de 2010 a 2013 e 34 projetos, as bandas
acima de 4 anos têm poucos contribuintes por coorte (n = 135/200) e o resultado fica dominado por
ruído.

**Onde conferir:**

- No [`validation_report.md`](../output/validation_report.md): a linha da direção entre curto e
  longo prazo e a linha da significância desse par.
- A figura: [`output/plots/ieice16_fig8_projecao_2013-09-30.png`](../output/plots/ieice16_fig8_projecao_2013-09-30.png).

## 9. Fig.2 do ESEM'14 (dez/2011), banda a banda: L1 = 411 pessoas

| painel | L1 |
|---|---|
| `mxcl/homebrew` | 363 |
| `thoughtbot/paperclip` | 38 |
| `clojure/clojure` | 11 |
| `joshuaclayton/blueprint-css` | 0 |

| artigo | replicação |
|---|---|
| ![](figuras/artigo/esem14_fig2_artigo.png) | ![](../output/plots/esem14_fig2_status_2011-12-31.png) |

O resíduo é praticamente todo do homebrew, com assinatura exata: **+200 no lado do código, -129 no
da discussão, +71 de população total**.

**Explicação mais provável: a fronteira `coding` contra `non_coding`.** 674 contribuidores vivos
estão do lado do código só por terem aberto pull request sem nenhum commit, sendo 601 nas 4 bandas
mais novas, onde mora o excesso. O tamanho é compatível com a forma do erro. Nenhuma regra testada
recorta exatamente 129 desses 674.

O que já testamos e não explica:

- Âncora de idade: por construção ela só move gente entre bandas, e o saldo -129/+200 fica idêntico.
- Autoria do PR por `user_id` no lugar de `actor_id`: 49 linhas divergentes em 13.171, com a mesma contagem de autores.
- Só PR mergeado conta como código: levaria o homebrew de +200 para -461.
- PR fora da conta, nem código nem discussão: a população cai para 3835 (alvo 3811) e o lado do código desaba 475.
- `moved` contado do lado da discussão: são 481 pessoas no homebrew contra as 129 necessárias, e o paperclip piora de 38 para 82.
- Limiar de 2 eventos de código: 589 pessoas têm exatamente um evento de código no homebrew, então a identidade 200 = 129 + 71 é coincidência.
- Dump anterior do GHTorrent: explicaria a população maior e o excesso nas faixas novas, e não temos o dump antigo para testar. Fica como observação.

**Onde conferir:**

- A figura, contra a Fig.2 do artigo:
  [`output/plots/esem14_fig2_status_2011-12-31.png`](../output/plots/esem14_fig2_status_2011-12-31.png).
- A tabela banda a banda: [`docs/figuras/esem14_fig2.md`](figuras/esem14_fig2.md).

---

## O que as divergências têm em comum

1. **Classificamos novato demais.** Duas métricas independentes apontam o mesmo viés na mesma
   direção: sobra A e falta C nos tipos (item 1), e o magnetismo do jekyll sai alto (item 2). É a
   ambiguidade mais cara do trabalho, e o artigo não fixa a definição em lugar nenhum do texto.
2. **Coortes ralas derrubam os recortes finos.** Itens 5, 6, 7 e 8 têm a mesma raiz: n pequeno,
   ABRE instável, significância que some fora do agregado.
3. **Buracos de cobertura do dump.** `scala/2010`, `django/2011` e provavelmente parte do resíduo do
   homebrew são compatíveis com um *vintage* diferente do GHTorrent, hipótese que o dump publicado
   não permite testar.

Nenhum dos nove itens derruba o achado principal. Os itens 5 a 8 enfraquecem generalizações
secundárias do IEICE'16.
