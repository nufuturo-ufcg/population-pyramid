# O método, direto

Do dump ao número, na ordem em que a ferramenta faz. Sem analogia (isso é o
`COMO_FUNCIONA.md`) e sem o placar de divergências (isso é o
`RESUMO_EXECUTIVO.md`). Cada decisão ambígua citada aqui tem parâmetro em
`config/settings.yaml` e discussão em `discrepancias.md`.

## 1. A ferramenta recebe o quê, em que formato

**Entrada:** o dump MySQL do GHTorrent usado no MSR'14 Mining Challenge, montado
read-only (`DB_NAME=msr14`). É um banco relacional, não arquivo: a ferramenta lê
por SQL, e todo SQL vive em `src/pyramid/sources/`.

Tabelas usadas: `projects`, `users`, `commits`, `project_commits`,
`pull_requests`, `pull_request_history`, `commit_comments`, `issues`,
`issue_comments`, `pull_request_comments`, `issue_events`.

**Primeira coisa que o pipeline faz:** achatar tudo isso em uma tabela só, com
quatro colunas, uma linha por ato de contribuição:

    scope_id | contributor_id | event_type | timestamp

`event_type` é um enum fechado de sete valores (`commits`, `pull_requests`,
`commit_comments`, `issues`, `issue_comments`, `pull_request_comments`,
`issue_events`). Depois desse ponto ninguém mais sabe que existiu um MySQL: os
estágios seguintes só veem "quem fez algo, de que tipo, quando, em que projeto".

Escala real: **90 projetos, 1.743.265 eventos, ~80,5 mil pares
(projeto, contribuidor)**, do primeiro evento em 2003-02-13 ao último em
2013-10-07.

Descarte no caminho: linha sem contribuidor (`commits.author_id` e
`issues.reporter_id` são NULL quando o GHTorrent não resolveu o usuário) e linha
com data inválida (`0000-00-00`). Nada além disso.

Saída de cada estágio: um `.parquet` por projeto em `output/<estágio>/`, mais um
`_manifest.json` com o que rodou. Estágio já feito não roda de novo sem
`--force`.

## 2. Quais repositórios entram

Todos os 90, sempre por `project.id`.

- **Filtro:** `forked_from IS NULL` (só raiz, nada de fork). Isso dá 91 linhas;
  a 108342 (`Craftbukkit/Bukkit`) é namespace fantasma com zero atividade e é
  excluída por id explícito. Restam **90**, e esse número é conferido a cada
  execução.
- **Nunca por nome:** `symfony` resolve para dois ids (51671 `symfony/symfony` e
  74915 `xphere-forks/symfony`).
- **Escopo de um evento:** o que pertence ao repositório raiz
  (`commits.project_id`, `issues.repo_id`, `pull_requests.base_repo_id`).
  Contar também a família de forks foi testado e muda ~2% da população ativa
  (`commit_scope: root` é o que está em vigor).
- **Identidade:** uma linha de `users` = uma pessoa. Sem fusão de contas
  (`identity_merge: none`); a fusão existe como diagnóstico fora do pipeline.

Recortes menores aparecem depois, e cada um é declarado onde é usado: Tipos A-D
exigem ao menos um contribuidor vivo no snapshot; a projeção exige > 100
contribuintes ativos na base (34 projetos); os quadrantes de atratividade
exigem ≥ 10 devs no ano.

## 3. Coding, Discussion (non-coding) e Moved

**Primeiro, o tipo do evento.** Divisão em vigor (`taxonomy.variant: prose`,
IEICE'16 p.1307 prosa == ESEM'14 §3):

| Lado | Eventos |
|---|---|
| coding | `commits`, `pull_requests` |
| non-coding (discussion) | `commit_comments`, `issue_comments`, `pull_request_comments`, `issue_events` |
| fora | `issues` |

A leitura alternativa (`table1`: `issues` dentro, `issue_events` fora) está
implementada e é rodável; o artigo se contradiz na mesma página.

**Depois, a categoria da pessoa.** Ela não é fixa: é recalculada em cada
snapshot T, a partir de duas datas por (projeto, pessoa):

- `init_c` = primeiro evento de coding
- `init_d` = primeiro evento de non-coding

Então, no snapshot T:

| Categoria | Regra |
|---|---|
| **non_coding** | não tem `init_c` até T — só conversou |
| **moved** | tem `init_c ≤ T` **e** `init_d < init_c` — discutiu antes de codar |
| **coding** | tem `init_c ≤ T` e não discutiu antes — entrou codando |

Consequência de projeto: quem discute em 2011 e só commita em 2012 aparece como
`non_coding` nas pirâmides de 2011 e vira `moved` a partir de 2012. Essa
migração é o conteúdo da Fig.3 do ESEM'14.

Para CCR, projeção e para o eixo da figura, **`moved` conta do lado coding** —
ele é um lado próprio só na cor da barra.

## 4. Como a pirâmide é montada

A série de snapshots é fim de trimestre civil, de **2010-03-31 a 2013-09-30**:
15 datas. Em cada snapshot T, cada contribuidor do projeto recebe:

1. **Lado** — a categoria da seção 3 (non-coding à esquerda; coding + moved à
   direita).
2. **Idade** — `T − start_ref`, onde `start_ref` é `init_c` para quem já codou e
   `init_d` para quem não codou. É tenure de calendário: **gap de inatividade
   não desconta idade**, igual à idade numa pirâmide demográfica. A leitura
   alternativa (somar só os períodos ativos) foi refutada — zera os Tipos C e D.
3. **Banda** — faixas de 3 meses (90 dias), fechadas em cima:
   `(0,90] → banda 0`, `(90,180] → banda 1`, ... O rótulo do eixo y de uma banda
   é `(banda+1) × 3 meses`.
4. **Vivo ou não** — a pessoa está viva em T se o último evento dela é recente.
   O artigo: "left the project when he/she did not give any contribution for
   more than three months". A ferramenta guarda `idle_days` e o consumidor
   escolhe a janela:
   - **CCR/NCR, Tipos e projeção usam 3 meses** (o texto do artigo);
   - **as pirâmides desenhadas usam 12 meses** (`plots.pyramid_window_months`),
     largura que veio da medição em pixel da Fig.2 do ESEM'14.

Desenhar é então só contar: para cada banda, quantos de cada categoria, non-coding
para a esquerda, coding+moved para a direita.

Sobre períodos de atividade: os eventos de cada pessoa são quebrados em spans
separados por mais de 3 meses de silêncio. Os spans decidem quem está vivo; não
decidem idade. Quem sai e volta reaparece já velho — que é o "we consider them
as experienced contributors when they come back" do artigo, de graça.

## 5. CCR e NCR

Sobre a **população viva** do projeto no snapshot (janela de 3 meses), quatro
contagens:

    coding      = categoria ∈ {coding, moved}
    non         = categoria == non_coding
    new         = banda 0            (até 3 meses de casa)
    experienced = banda ≥ 1

E as duas razões, como publicadas (IEICE'16 p.1308-1309):

    CCR = (coding − non) / max(coding, non)
    NCR = (new − experienced) / max(new, experienced)

O denominador é sempre o maior lado, então ambos ficam em **[−1, 1]**. CCR > 0 =
mais gente codando que conversando; NCR > 0 = mais novato que veterano.

**Tipos A-D** são os quadrantes desse plano, com corte em zero (a mediana não
entra):

| Tipo | CCR | NCR | Leitura |
|---|---|---|---|
| A | > 0 | > 0 | novatos entrando e codando |
| B | < 0 | > 0 | novatos entrando, mas conversando |
| C | > 0 | < 0 | veteranos codando |
| D | < 0 | < 0 | veteranos conversando |

Projeto sem nenhum contribuidor vivo não é classificado (`ratio` devolve NaN) —
é o que derruba projetos da Fig.5. Empate exato (CCR ou NCR == 0) cai no lado
baixo, e a contagem de empates vai para o manifesto em vez de sumir dentro de um
quadrante.

## 6. O que mais sai daí

Tudo abaixo é derivado das mesmas pirâmides.

**Projeção coorte-componente** (IEICE'16 §4), por banda, separada para
non-coding / moved / coding:

    SR(b)             = Pop(b+1, jun/2013) / Pop(b, mar/2013)
    Pop(b+1, set/13)  = SR(b) × Pop(b, jun/2013)
    Pop(banda 0)      = média das duas contagens mais recentes   (o "nascimento")

Migração entre projetos é zero, por decisão explícita do artigo. Baseline =
"set/2013 é igual a jun/2013". Erro = **ABRE** com denominador `min(real, previsto)`.
Roda nos 34 projetos com mais de 100 contribuintes ativos em mar/2013.

**Magnetismo × stickiness** (MSR'14, adotado pelo ESEM'14), anual, só com
`commits` e `pull_requests`:

    magnetismo(P,Y) = novatos do ano Y que contribuíram em P / novatos do ano Y (dataset inteiro)
    stickiness(P,Y) = devs de P em Y que voltam em Y+1        / devs de P em Y

"Novato do ano Y" é propriedade global da pessoa: a primeira contribuição dela
em *todo* o dataset caiu em Y. Por isso este estágio recusa rodar num
subconjunto de projetos — mudaria o denominador em silêncio. Corte alto/baixo é
a **mediana entre os projetos elegíveis daquele ano** (≥ 10 devs), recalculada
ano a ano, e os quadrantes são attractive / floating / stagnant / terminal.

**2013 é right-censored** (o dump acaba em out/2013): o ano **renderiza
pirâmide** — forma é estoque, olha para trás — e **não recebe quadrante** —
stickiness é fluxo e precisaria de 2014. Nada é anualizado para forçar
classificação.

**Artefatos gerados** (`uv run pyramid plot`, em `output/plots/`): as pirâmides
por status e por tipo, a grade de transição, o scatter CCR × NCR, a sobreposição
projeção × real, e as tabelas ABRE / quadrantes em CSV e Markdown. O
`validate` compara cada número desses com os valores publicados e escreve
`output/validation_report.md`.

## Ordem de execução

    extract → classify → snapshots → metrics → attractiveness → projection

`uv run pyramid run-all` roda os seis; `uv run pyramid plot` desenha; `uv run
pyramid validate --report output/validation_report.md` confere contra os artigos.
