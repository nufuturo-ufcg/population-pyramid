# O método, direto

Do dump ao número, na ordem em que a ferramenta faz. Sem analogia (isso é o
`COMO_FUNCIONA.md`) e sem o placar de divergências (isso é o
`RESUMO_EXECUTIVO.md`). Cada decisão ambígua citada aqui tem parâmetro em
`config/settings.yaml` e discussão em `discrepancias.md`.

## 1. A base de dados

O dump é do GHTorrent, usado no MSR14 Mining Challenge. GHTorrent espelha o
GitHub em tabelas relacionais, uma por tipo de evento ou entidade.

Tabelas usadas:

- `projects`, `users`
- `commits`, `project_commits`
- `pull_requests`, `pull_request_history`
- `commit_comments`, `issues`, `issue_comments`, `pull_request_comments`, `issue_events`

Os dois artigos citam a mesma base:

- MSR14 (Yamashita et al.): "we analyze the GitHub dataset provided by Gousios ... 90 OSS projects."
- ESEM14: "Similar to the previous study, we analyze the GitHub dataset provided by Gousios."

Escala, depois do filtro da seção 2:

- 90 projetos
- 1.743.265 eventos
- ~80,5 mil pares (projeto, contribuidor)
- primeiro evento em 2003-02-13, último em 2013-10-07

## 2. O parser

Lê o dump e devolve uma tabela única, uma linha por contribuição:

    scope_id | contributor_id | event_type | timestamp

`event_type` é um enum fechado de sete valores, um por tabela de origem:

- `commits`
- `pull_requests`
- `commit_comments`
- `issues`
- `issue_comments`
- `pull_request_comments`
- `issue_events`

Descarte no caminho:

- linha sem contribuidor (`commits.author_id` e `issues.reporter_id` nulos, quando o GHTorrent não resolveu o usuário)
- linha com data inválida (`0000-00-00`)

Nada além disso.

## 3. Os projetos que entram

O dump tem 91 repositórios raiz (fork não conta, só o projeto original). Um
deles aparece na lista mas não tem nenhuma atividade registrada, e foi
removido à mão. Sobram 90.

Cada projeto é identificado por um número, não pelo nome: há dois
repositórios diferentes chamados `symfony` no dump.

Cada projeto conta só a atividade dele, não a dos forks feitos a partir dele.

Não há duplicadas: cada pessoa entra uma vez.

## 4. Coding, discussion e moved

Cada contribuição cai num de dois grupos:

- código: commit, pull request
- conversa: comentário em commit, em pull request, em issue, ou evento de issue

Quem só tem contribuição de conversa fica do lado esquerdo da pirâmide. Quem
tem contribuição de código fica do lado direito.

Existe um terceiro caso: quem começou conversando e só depois passou a
codar. Essa pessoa fica do lado direito também, mas marcada numa cor
diferente, pra mostrar que ela veio da conversa. Não é uma coluna à parte no
meio da pirâmide.

Em cada data de corte, o programa olha duas coisas de cada pessoa: quando ela
codou pela primeira vez, e quando ela conversou pela primeira vez (se ela
nunca codou, essa segunda data não existe). A partir disso:

- ainda não codou até a data de corte: fica do lado da conversa
- codou, e conversou antes de codar: fica do lado do código, marcada como veio da conversa
- codou, e nunca conversou antes: fica do lado do código, sem marca

Quem conversa em 2011 e só começa a codar em 2012 fica do lado da conversa na
foto de 2011 e muda de lado na foto de 2012.

## 5. A montagem da pirâmide

O programa monta um recorte do projeto a cada 3 meses, do fim de março de
2010 ao fim de setembro de 2013. São 15 recortes, na mesma janela de anos das
figuras dos artigos (dezembro de 2011, e junho de 2010 a junho de 2013), com
mais pontos no meio.

Em cada recorte, cada pessoa recebe três coisas:

**Lado.** Código ou conversa, como na seção 4.

**Altura.** O tempo desde a primeira contribuição que colocou a pessoa
naquele lado, contado em blocos de 3 meses. 0 a 3 meses é a barra mais baixa,
3 a 6 meses a próxima, e assim por diante.

**Viva ou não.**

- O IEICE16 define o critério: "we consider that a contributor left a
  project when he/she did not give any contribution on that project for more
  than three months". Sem contribuição por mais de 3 meses conta como fora
  do projeto, e é esse critério que o programa usa nas contas de
  crescimento, tipos e projeção.
- A pirâmide desenhada usa uma janela maior, 12 meses, porque essa foi a
  largura que bateu com a figura publicada quando medimos pixel por pixel.

Quem some por mais de 3 meses e volta ao projeto depois reaparece com a
idade completa, contada desde a primeira aparição, não desde a volta. O
IEICE16 descreve esse efeito: "very few contributors might come back to the
project after three-month (or more) interval. They disappear from the
pyramids while they are inactive temporarily. In that case, we consider them
as experienced contributors when they come back to the project."

Todas essas contas rodam nos 90 projetos do dump. A projeção
coorte-componente é uma exceção: roda só nos projetos com mais de 100
contribuintes ativos no recorte de março de 2013, 34 no total. O artigo não
justifica o corte de 100, só declara: "we project a future population size
for the 36 projects that have more than 100 contributors."

## 6. CCR, NCR e os quatro tipos

Sobre as pessoas vivas do projeto no recorte, o programa calcula duas
proporções definidas no IEICE16.

**CCR, a proporção entre quem coda e quem só conversa.**

O IEICE16 chama essa conta de Coding Contributors Ratio. Coding é quem está
do lado código (coding + moved, seção 4). Non é quem está do lado conversa.

    CCR = (coding − non) / o maior dos dois

O resultado vai de −1 a 1. Acima de zero, tem mais gente codando. Abaixo de
zero, mais gente só conversando.

**NCR, a proporção entre quem chegou agora e quem já tem tempo de casa.**

O IEICE16 define quem é quem: "we define newcomers as contributors who have
less than three months of activity periods, and we define experienced
contributors as those with longer activity periods."

    NCR = (novato − veterano) / o maior dos dois

Mesma escala de −1 a 1. Acima de zero, mais novato que veterano. Abaixo de
zero, o contrário.

**Os quatro tipos.** Cruzando CCR e NCR, cada projeto cai num quadrante. O
IEICE16 descreve os quatro:

| Tipo | CCR | NCR | O que o IEICE16 diz |
|---|---|---|---|
| A | > 0 | > 0 | "more newcomers than experienced contributors, and more coding contributors than non-coding ones" |
| B | < 0 | > 0 | "more newcomers than experienced contributors, and more non-coding contributors than coding ones" |
| C | > 0 | < 0 | "more experienced contributors than newcomers, and more coding contributors than non-coding ones" |
| D | < 0 | < 0 | "more experienced contributors than newcomers, and more non-coding contributors than coding ones" |

Projeto sem ninguém vivo no recorte não entra em nenhum tipo. Empate exato em
CCR ou NCR, valor igual a zero, cai no lado de baixo do corte.

## 7. O que mais sai da pirâmide

Duas contas adicionais usam os mesmos recortes trimestrais: uma projeta o
futuro, outra compara com o método anterior aos artigos do Onoue et al.

### Projeção coorte-componente

Cada pessoa está numa faixa de idade (seção 5): há quanto tempo ela
contribui, em blocos de 3 meses.

Pra prever quantas pessoas vão estar numa faixa daqui a 3 meses, o programa
olha o que aconteceu com essa mesma faixa da última vez. Um exemplo com
números inventados:

1. A faixa "3 a 6 meses" no recorte de março de 2013 tem 40 pessoas.
2. Três meses depois, no recorte de junho, a faixa seguinte, "6 a 9 meses",
   tem 30 pessoas. Boa parte dessas 30 são as mesmas 40 de março, que
   continuaram ativas e envelheceram uma faixa. As outras saíram do projeto
   pelo caminho.
3. 30 dividido por 40 dá 0,75: de cada 10 pessoas que estavam numa faixa, 7
   ou 8 seguem vivas na faixa seguinte, 3 meses depois. Essa razão é a taxa
   de sobrevivência daquela faixa.
4. Pra prever setembro, o programa aplica essa mesma taxa na faixa "6 a 9
   meses" de junho: 30 pessoas × 0,75 ≈ 22 pessoas esperadas na faixa "9 a
   12 meses" em setembro.

O programa repete essa conta faixa por faixa, sempre usando a taxa observada
entre os dois recortes mais recentes.

A faixa mais nova, 0 a 3 meses, não tem faixa anterior pra calcular taxa de
sobrevivência: ninguém "envelhece" pra dentro dela, as pessoas só chegam.
Pra ela, o IEICE16 usa uma conta mais simples: a média entre quantas pessoas
estavam nessa faixa no recorte atual e no recorte anterior.

O programa também não conta gente que sai de um projeto e some pra dentro de
outro como se fosse chegada nova: "we do not consider that contributors move
to other projects in our study, so we do not calculate net migration." Cada
projeto é projetado sozinho.

Roda separado por lado (non-coding, moved, coding), só nos 34 projetos
definidos na seção 5.

### Contra um método mais simples

O IEICE16 compara a projeção coorte-componente com um método ingênuo: "the
baseline method, which assumes that the number of contributors of September
and June 2013 are the same."

O erro usa "ABRE (Absolute Balanced Relative Error)", que divide sempre pelo
menor dos dois valores, pra não favorecer quem chuta baixo.

O teste de Wilcoxon diz quais tipos e lados têm diferença estatisticamente
significativa entre os dois métodos.

### Magnetismo e stickiness

Vêm do MSR14 (Yamashita et al.), o trabalho anterior aos artigos do Onoue et
al. Contam só commits e pull requests, um ano por vez.

- Magnetismo: "we calculate the magnetism of a project as the proportion of
  contributors who made their first contribution in the time period under
  study who contribute to a given project."
- Novato do ano é quem fez a primeira contribuição daquele ano em qualquer
  projeto do dataset, não só nesse. Por isso essa conta não roda num
  subconjunto de projetos: mudaria quem conta como novato.
- Stickiness: "we calculate the stickiness of a project as the proportion of
  the contributors in the time period under study who have also made
  contributions in the following time period."

Os quatro quadrantes, definidos pelo MSR14:

| Quadrante | Magnetismo | Stickiness |
|---|---|---|
| Attractive | alto | alto |
| Fluctuating | alto | baixo |
| Stagnant | baixo | alto |
| Terminal | baixo | baixo |

O corte é a mediana entre os projetos elegíveis daquele ano, recalculada ano
a ano. Só entram projetos com mais de 10 desenvolvedores no ano.

### 2013 fica sem quadrante

- O dump termina em outubro de 2013, sem ano seguinte completo.
- A pirâmide de 2013 sai: usa só os dados até aquele recorte.
- O quadrante de 2013 não sai: stickiness pede o ano seguinte, que o dump
  não tem.

### O que sai no fim

- As pirâmides por status e por tipo.
- O gráfico de transição entre faixas.
- O comparativo CCR × NCR.
- A projeção sobreposta ao valor real.
- As tabelas de erro e de quadrante.

Cada número é comparado com o publicado nos artigos.
