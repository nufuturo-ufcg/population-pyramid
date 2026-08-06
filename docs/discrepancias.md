# Discrepâncias vs. os artigos originais

Registro do que foi investigado quando um checkpoint não bateu, qual leitura foi
escolhida e por quê. Exigido pelo §9 do spec ("documentar qual foi investigado e
o resultado, não só 'não bateu'").

Checkpoint de referência: **IEICE16 Fig. 5**, snapshot set/2013 —
`A=23, B=42, C=18, D=3`, 86 projetos classificados de 90
(4 sem contribuidores no período).

---

## 1. Resultado atual

| | A | B | C | D | classificados | sem contribuidor |
|---|---|---|---|---|---|---|
| IEICE16 Fig.5 | 23 | 42 | 18 | 3 | 86 | 4 |
| Esta replicação | 27 | 40 | 14 | 4 | 85 | 5 |

Erro L1 = 11 tipos, sobre 85 projetos classificados (contra 86 no artigo). O
viés é sistemático e sempre o mesmo: **sobra projeto em A, falta em C** — ou
seja, classifico newcomer demais. A e C só diferem pelo sinal do NCR, então
bastariam 4 projetos com mais experientes que novos para fechar.

Os 8 projetos que o artigo nomeia individualmente batem **8/8** (§3.1a), e os 4
projetos que fechariam o gap custam **1-2 contribuidores cada** (§3.1b) — o
resíduo vive nos projetos de população 1-3, não numa falha do método.

O GATE do §9 pede acerto **exato**. Ele não passa. O que segue é o que foi
testado para tentar fechar.

## 2. Grid completo executado

Cada célula é uma leitura defensável do texto, não um knob arbitrário. Todas
rodadas contra o mesmo dump, mesmo snapshot.

### Taxonomia de eventos (ambiguidade 1)

O IEICE16 se contradiz entre a Tabela 1 (p.1307) e a prosa da mesma página.
Ambas dão "six development activities".

| Variante | A | B | C | D | classif. | erro |
|---|---|---|---|---|---|---|
| `table1` (`issues` dentro, `issue_events` fora) | 27 | 42 | 12 | 1 | 84 | 12 |
| `prose` (`issue_events` dentro, `issues` fora) | 27 | 39 | 14 | 3 | 85 | **11** |

Escolhida: `prose`. Ganha por pouco no L1, mas ganha por muito no argumento —
`issues` mistura PRs com issues de verdade (69.633 de 150.362 linhas são PRs
disfarçados), então contá-la infla a discussão com o que já foi contado como
coding. O ESEM14 §3 concorda com a prosa.

### Escopo de commits (ambiguidade 2 — o "primeiro suspeito" do §7.1 do spec)

| Escopo | A | B | C | D | classif. | erro |
|---|---|---|---|---|---|---|
| `root` (`commits.project_id`) | 27 | 39 | 14 | 3 | 85 | **11** |
| `family_project_commits` (agrega forks) | 28 | 39 | 14 | 3 | 85 | 12 |

Agregar os forks move ~2% dos contribuidores ativos e **piora**. O §7.1 fica
resolvido a favor de `root`: a hipótese de que a contagem estava baixa por não
agregar forks está descartada — o dump já tem contribuidores suficientes.

### Definição de idade (ambiguidade 3) — este era o erro grande

| Base | A | B | C | D | erro |
|---|---|---|---|---|---|
| `accumulated_active` (soma dos períodos de atividade) | 41 | 42 | 0 | 0 | 62 |
| `calendar_tenure` (tempo desde a origem) | 27 | 39 | 14 | 3 | **11** |

`accumulated_active` é a leitura literal de *"less than three months of activity
periods"* (p.1308) e é **impossível**: deixa C e D completamente vazios, quando o
artigo tem 21 projetos ali. Quase ninguém acumula 3 meses de atividade contínua,
então todo mundo vira newcomer para sempre. `calendar_tenure` é o que o método
demográfico emprestado exige — numa pirâmide etária, idade é idade, gap não
desconta. Adotada.

### Fim do período e população

| Fim do período | População | A | B | C | D | erro |
|---|---|---|---|---|---|---|
| snapshot | ativos (3m) | 27 | 39 | 14 | 3 | **11** |
| snapshot | cumulativa | 0 | 0 | 34 | 55 | 133 |
| último evento | ativos (3m) | 30 | 41 | 10 | 0 | 19 |
| último evento | cumulativa | 34 | 55 | 0 | 0 | 45 |

População cumulativa está fora de questão (erro 133, e classificaria 90 projetos
em vez de 86). Medir a idade até o último evento da pessoa em vez de até o
snapshot também piora. Mantido: idade até T, população = ativos nos últimos 3
meses.

## 3. O que sobra sem explicação

Depois de 16 combinações, o piso é erro 11. Hipóteses não testáveis com este
dump:

1. **A lista exata de eventos.** O artigo nunca enumera as tabelas do GHTorrent
   que usou. Qualquer evento a mais ou a menos no lado non-coding move o CCR de
   projetos que estão perto de zero — e Fig.5 mostra vários exatamente aí
   (homebrew e rails são descritos como "próximos do centro").
2. **A versão do GHTorrent.** Nosso dump é o do MSR14 Challenge (cobertura até
   2013-10-06). Os autores publicaram em 2016 e podem ter usado um dump mais
   recente, com backfill dos mesmos projetos.
3. **Empates.** Resolvido, ver §6.

## 3.1 Investigação dirigida dos Tipos A-D (§9.1 do spec)

Quatro testes. Nenhum derrubou o erro 11, mas o (a) e o (b) juntos mudam o que a
discrepância significa.

**(a) Os 8 projetos nomeados no artigo — batem todos os 8.** O IEICE16 rotula
por nome 8 pontos da Fig. 5. Conferidos um a um em `2013-09-30`:

| projeto | artigo | nosso | CCR | NCR |
|---|---|---|---|---|
| jquery | A | A | +0.74 | +0.34 |
| django-cms | A | A | +0.32 | +0.29 |
| homebrew | A | A | +0.21 | +0.25 |
| Font-Awesome | B | B | -0.96 | +0.84 |
| gitlabhq | B | B | -0.59 | +0.48 |
| cakephp | C | C | +0.90 | -0.11 |
| CraftBukkit | C | C | +0.55 | -0.36 |
| rails | D | D | -0.03 | -0.07 |

**8/8.** Inclusive `rails`, que está a -0.03/-0.07 da origem — o ponto mais
difícil dos oito, e cai no quadrante certo. Todo projeto que o artigo permite
verificar individualmente confere. O erro 11 está inteiramente nos 78 projetos
que o artigo só reporta em agregado.

**(b) O erro está nos projetos minúsculos.** Ordenando nossos 27 projetos Tipo A
pela distância até virar C (quantos contribuidores precisariam sair de `new` e
entrar em `experienced`):

| projeto | new | exp | pessoas p/ virar C |
|---|---|---|---|
| blueprint-css | 1 | 0 | 1 |
| symfony | 2 | 1 | 1 |
| zipkin | 10 | 9 | 1 |
| memcached | 3 | 0 | 2 |
| clojure | 7 | 4 | 2 |

**Os 4 projetos A→C que fechariam o gap custam 1-2 contribuidores cada, cinco
pessoas no total.** Metade desses projetos tem população de 1 a 3 pessoas em
set/2013 — um único contribuidor decide o quadrante do projeto inteiro. Não é
um viés sistemático do método; é ruído de amostra pequena, e qualquer diferença
de cobertura do dump (hipótese 2) o produz.

**(c) A data do snapshot vale ±4 no erro.** O artigo diz "September 2013" e
nunca dá o dia. Deslocando a grade trimestral inteira para cair em cada dia
candidato:

| snapshot | A | B | C | D | erro L1 | sem contribuinte |
|---|---|---|---|---|---|---|
| 2013-09-01 | 24 | 44 | 14 | 3 | **7** | 5 |
| 2013-09-15 | 26 | 44 | 13 | 3 | 10 | 4 |
| 2013-09-30 | 27 | 40 | 14 | 4 | 11 | 5 |
| 2013-10-06 | 26 | 39 | 15 | 5 | 11 | 5 |

`2013-09-01` daria o melhor número da replicação inteira (erro 7, e Tipo D
exato). **Ficamos em `2013-09-30`**: a série trimestral foi fixada em
`config/settings.yaml` antes desta varredura existir, e trocá-la agora seria
escolher a data pelo resultado. O que a tabela estabelece é que o checkpoint dos
Tipos A-D é subdeterminado pelo texto em ~±4 de erro L1 — "erro 11" e "erro 7"
aqui são a mesma replicação com uma frase ambígua lida de dois jeitos.

**(d) Projeto sem contribuinte: 5 vs 4 do artigo.** Não é causa independente —
sai de (c). Em `2013-09-15` são exatamente 4, como no artigo. Nos outros dias, 5.

**Conclusão.** Os três itens do §9.1 estão fechados sem mudança de método: a
parte verificável nominalmente bate 8/8, o resíduo agregado é dominado por
projetos de 1-3 pessoas, e a data ambígua sozinha explica ±4 dele. Nenhum
parâmetro foi girado para chegar aqui.

## 4. Discrepância aberta, independente desta

"the 36 projects that have more than 100 contributors" (p.1311, usado no filtro
da projeção). Medido: **32** projetos ativos com >100 contribuidores, **79** em
contagem cumulativa. Nenhum dos dois dá 36. Mover o início da janela para
2013-07-01 ainda dá 32, então não é artefato de borda. Ver
`projection.min_contributors_basis`.

---

## 5. Fronteira das bandas (resolvido pelo exemplo dos autores)

O IEICE16 nunca diz se a banda de 3 meses é fechada embaixo ou em cima. O
exemplo didático da Tabela 2 + Fig. 4 resolve: **C3 tem exatos 3 meses de
non-coding em t1 e é desenhado na banda "3 months"**, não na de 6; **C6 tem
exatos 6 meses de coding em t2 e cai na banda "6 months"**. Logo as faixas são
`(0,3]`, `(3,6]`, `(6,9]` — o rótulo do eixo é o limite SUPERIOR.

A implementação usava `floor(idade/3)`, que empurra 3 e 6 para a faixa
seguinte. Corrigido para `ceil(idade/3)-1` em `snapshots.py`.

**Efeito nos dados reais: nenhum.** Re-rodados os estágios 3 e 4 sobre os 90
projetos, as 1143 linhas de métricas ficaram idênticas em `new`,
`experienced`, `coding`, `non_coding`, `ccr`, `ncr` e `type` — nenhum
contribuidor real cai exatamente sobre um múltiplo de 91,3125 dias. A correção
é de fidelidade ao método, não de resultado.

O mesmo exemplo fixou outras duas decisões, ambas já implementadas assim e
agora cobertas por teste (`tests/test_classify.py`, 25 casos):

- **idade de quem migrou conta a partir de `init_c`.** C3 em t2 tem 6 meses de
  non-coding e 2 de coding, e aparece na banda "3 months" — a idade é a do lado
  coding. Idem C6 (8 non-coding / 6 coding → banda "6 months").
- **`moved` exige ter discutido ANTES de codar.** C4 tem os dois lados (8
  coding / 5 non-coding) mas é `coding`, porque `init_c < init_d`.

O teste reconstrói as duas pirâmides inteiras da Fig. 4 (quem está em qual
banda, de qual lado) e compara célula a célula.

---

## 6. Empate exato em CCR/NCR (resolvido, regra fixa)

Os artigos definem os quadrantes em palavras ("more coding than non-coding") e
nunca dizem o que fazer quando os dois lados empatam. A implementação antiga
deixava esses projetos em `unclassified` e expunha um knob `metrics.tie_side`
para alternar o comportamento.

**O knob foi removido.** Deixar a convenção de desempate configurável convidava
a girá-la até o checkpoint bater, que é exatamente o que o §0 do spec proíbe. A
regra agora é fixa em `metrics._type_of` e é a leitura literal: alto = `valor >
0`, logo zero cai do lado baixo.

Em set/2013 isso afeta 2 projetos, ambos com CCR exatamente 0 por terem
`coding == non_coding`:

| projeto | coding | non_coding | CCR | NCR | tipo |
|---|---|---|---|---|---|
| MiniProfiler | 19 | 19 | 0.00 | +0.69 | B |
| ccv | 2 | 2 | 0.00 | -0.67 | D |

Efeito no resultado: **erro L1 continua 11** (era 11 com os dois fora, é 11 com
os dois dentro). O que muda é a cobertura — 83 → 85 projetos classificados de
86, e some a coluna "empates" do relatório. Ou seja: a regra melhora a
comparabilidade com o artigo sem alterar o erro que ele mede.

---

## 7. Filtro de projeção ">100 contribuidores": 35 medidos vs 36 do artigo (aceito)

O IEICE16 §4 restringe a projeção a "projects with more than 100 contributors"
e diz que sobram 36 projetos (4 Tipo A, 21 B, 9 C, 2 D). A medição direta não
reproduz 36 em nenhuma combinação testada.

### Grid completo

Contagem de projetos com >100 contribuidores, variando a base do snapshot e
quem conta como contribuidor:

| base | quem conta | ativo | cumulativo |
|---|---|---|---|
| 2013-03-30 | todos | **35** | 76 |
| 2013-03-30 | só coding | 8 | 53 |
| 2013-03-30 | coding + moved | 11 | 59 |
| 2013-06-30 | todos | 30 | 78 |
| 2013-06-30 | só coding | 8 | 56 |
| 2013-06-30 | coding + moved | 10 | 61 |
| 2013-09-30 | todos | 30 | 79 |
| 2013-09-30 | só coding | 7 | 59 |
| 2013-09-30 | coding + moved | 10 | 64 |

`>=100` em vez de `>100` só move a linha set/2013-todos (30 → 31); nas demais
não muda nada, porque nenhum projeto tem exatamente 100.

Comando: `/tmp/f92.py` e `/tmp/f92b.py` (grid + quebra por tipo), sobre
`output/snapshots/*.parquet`.

### Por que a quebra por tipo não foi usada para decidir

A ideia de casar 4/21/9/2 para identificar a variante certa não funciona: a
nossa própria classificação A-D tem erro L1=11 sobre 86 projetos (item 5), e
esse erro entra direto na quebra do subconjunto. Todas as variantes dão L1 8-10
contra 4/21/9/2, ou seja, dentro do ruído da classificação de base — o teste
não discrimina. O `n` é o único sinal limpo.

### Por que 34 é ruído de fronteira e não erro de método

> **Correção (2026-08).** Esta seção dizia **35**, com o 35º projeto em 102
> contribuintes. Aquela contagem foi feita com a data errada `2013-03-30`, antes
> de a causa raiz ser corrigida no §8. Com `2013-03-31` a janela de atividade de
> 3 meses anda um dia para frente, dois contribuintes do projeto marginal saem, e
> o número correto é **34**. Os valores abaixo são os de agora.

Ordenando os projetos por contribuidores ativos em 2013-03-31, a fronteira do
limiar cai num degrau:

| rank | contribuidores |
|---|---|
| #34 | 105 |
| #35 | **100** |
| #36 | 97 |
| #37 | 95 |

Note onde o corte caiu: o 35º projeto tem **exatamente 100**. O artigo diz
"more than 100 contributors", e `> 100` o exclui — mas ler a mesma frase como
"pelo menos 100" devolveria 35. A escolha está em `eligible_scopes()` como `>`,
seguindo o texto ao pé da letra, e é a diferença entre 34 e 35 nesta réplica.

O 36º candidato está 3 abaixo do corte. Qualquer alargamento pequeno na
definição de "ativo" (janela de 3 meses um pouco maior, ou uma tabela de evento
a mais no escopo) o empurra para dentro. Não existe limiar "errado" aqui: o
método está certo e os projetos marginais simplesmente não alcançam 100 na
nossa contagem.

**Decisão: aceitar 34, base 2013-03-31, contribuidores ativos, corte `> 100`.**
ABRE e Wilcoxon não dependem do número exato de projetos no filtro, só do
tamanho da amostra, então dois projetos a menos não comprometem o resultado que
o artigo mede — ver §12.2, onde o agregado fecha a ~5% do publicado.
`test_checkpoint_projetos_elegiveis_perto_dos_36` trava o 34 para que a
contagem não volte a deslizar sem que alguém perceba.

### Bug latente encontrado no caminho

A série de snapshots gerava **`2013-03-30`**, não `2013-03-31`. Contornado na
hora ajustando a config para a data errada; a causa raiz foi corrigida depois —
ver §8, que substitui este parágrafo.

---

## 8. Bug de geração da série de snapshots (corrigido)

**Status:** corrigido em 2026-08. Causa raiz confirmada, não contornada.

### Sintoma

`snapshot_dates()` produzia `2011-12-30`, `2012-12-30`, `2013-03-30` — dia 30 em
meses de 31 dias. A config foi inicialmente ajustada para casar essas datas
erradas (§7), o que escondeu o problema em vez de resolvê-lo.

### Causa raiz

Não é âncora travada num dia fixo. O pandas aplica um `DateOffset` de forma
**iterativa**, então o dia-do-mês é truncado no primeiro mês curto e **nunca se
recupera**:

```
pd.date_range("2010-03-31", "2013-09-30", freq=pd.DateOffset(months=3))
  2010-03-31   <- ok
  2010-06-30   <- truncado (junho tem 30 dias)
  2010-09-30   <- "certo" por coincidência
  2010-12-30   <- ERRADO, dia 30 agora é permanente
  2011-03-30 ... 2013-09-30   <- todo o resto no dia 30
```

Toda data depois da primeira estava grudada no dia 30. As que pareciam corretas
(jun, set) estavam certas **só porque esses meses acabam mesmo no dia 30** — foi
essa coincidência que manteve o bug invisível, já que os checkpoints mais
exercitados (Fig.5 set/2013, Fig.3 jun/*) caíam justamente nelas.

### Alcance

| Checkpoint | Data usada | Estava certa? |
|---|---|---|
| IEICE16 Fig.5, Tipos A-D | 2013-09-30 | sim, por coincidência |
| ESEM14 Fig.3, transições | jun/2010-2013 | sim, por coincidência |
| ESEM14 Fig.2, dez/2011 | 2011-12-30 | **não**, era -31 |
| Projeção, base mar/2013 | 2013-03-30 | **não**, era -31 |

### Correção

`snapshots.py` passou a usar `pd.offsets.QuarterEnd()`, ancorado em fim de
trimestre civil, que é o que o método pede (IEICE16 §4.1: March, June,
September). `freq_months` agora exige múltiplo de 3 e falha alto caso contrário,
em vez de gerar uma série silenciosamente diferente. `projection_base` voltou
para `2013-03-31`.

Comandos usados:

```bash
uv run python -c "from pyramid.snapshots import snapshot_dates; print([str(t.date()) for t in snapshot_dates()])"
uv run pyramid snapshots --force && uv run pyramid metrics --force
```

Série corrigida (15 snapshots): `2010-03-31, 2010-06-30, 2010-09-30,
2010-12-31, 2011-03-31, ... 2013-03-31, 2013-06-30, 2013-09-30`.

### Regressão: nenhuma

Tipos A-D em set/2013 seguem **27/40/14/4**, 85 classificados, erro L1 = 11 —
idênticos a antes do fix, como esperado, já que essa data não era afetada.

### Guarda contra reincidência

Adicionado `snapshots.require_date_match()`, aplicado em `metrics.table()` e
obrigatório em todo filtro/join novo contra a série de datas. Um filtro por data
de snapshot que não casa nenhuma linha agora levanta `ValueError` listando as
datas válidas, em vez de devolver DataFrame vazio. Regra do projeto: **data
ausente da série é erro de config ou de geração da série, nunca "esse snapshot
está vazio"**. `check_dates()` continua validando as datas de config na entrada.

---

## 9. Checkpoint ESEM14 Fig.2 (dez/2011): bate 4/5

**Status:** os quatro projetos nomeados na *legenda* da Fig.2 batem, um por
quadrante. O quinto projeto rotulado pelo artigo para 2011 — **jekyll**, no
corpo do texto ("also a terminal project in 2011") — **não** bate, e é o item
aberto do **§13**. Esta seção documenta os quatro que fecham; ela dizia "4/4"
porque só olhava a legenda.

Rodando `pyramid attractiveness` e cortando o ano 2011, os quatro projetos
nomeados na Fig.2 caem exatamente nos quatro quadrantes do artigo:

| projeto | quadrante (paper e medido) | magnetismo | ×mediana | stickiness | vs. mediana |
|---|---|---|---|---|---|
| mxcl/homebrew | attractive | 0.214806 | 29,49x | 0.2557 | +0.0630 |
| thoughtbot/paperclip | floating | 0.014568 | 2,00x | 0.1641 | −0.0287 |
| clojure/clojure | stagnant | 0.003716 | 0,51x | 0.3478 | +0.1551 |
| joshuaclayton/blueprint-css | terminal | 0.001338 | 0,18x | 0.0000 | −0.1928 |

Medianas de 2011 sobre os 75 projetos elegíveis: magnetismo 0.007284,
stickiness 0.1928.

**Por que isto vale como evidência e não como coincidência.** É um projeto por
quadrante: acertar os quatro por acaso exige que os dois cortes (as duas
medianas) caiam certo simultaneamente nas duas dimensões. Um erro de escopo na
retenção, de filtro de devs ativos ou de janela anual moveria pelo menos um dos
quatro. A folga mais apertada é `paperclip` na stickiness (−0.0287, ~15% da
mediana); nos outros sete valores a margem é larga. Se um refactor futuro
mexer nessa margem, o teste que quebra primeiro é o do `paperclip`.

**Gate automatizado.** `tests/test_attractiveness.py`, marcador `checkpoint`:

- `test_checkpoint_quadrantes_dez_2011` lê os rótulos direto do
  `config/checkpoints.yaml` (não os repete no teste) e compara com o parquet;
- `test_checkpoint_2011_usa_os_quatro_quadrantes` garante que os quatro rótulos
  existem em 2011, para que afrouxar o checkpoint no futuro não deixe passar um
  bug que colapsasse tudo num quadrante só.

Ambos dão `skip` — não passam em falso — quando o parquet do estágio ainda não
foi gerado. Rodar só eles: `pytest -m checkpoint`.

**Nota de leitura sobre a tabela antiga desta seção.** A versão anterior deste
item trazia contagens do snapshot trimestral `2011-12-31` (homebrew com 1448
ativos, blueprint-css com 1). Elas não contradizem os números acima: magnetismo
e stickiness usam janela **anual** (ano civil de 2011), então homebrew aparece
com 1740 devs ativos no ano contra 1448 no trimestre. São janelas diferentes do
mesmo dado, e o §3.1 do ESEM14 é explícito em usar a anual.

`blueprint-css` com stickiness exatamente 0.0000 confirma pelo lado quantitativo
a leitura qualitativa que já estava aqui ("colapsada" na Fig.3): dos 11 devs que
tocaram o projeto em 2011, nenhum voltou em 2012.

**O que continua aberto:** a transição temporal da Fig.3 (jun/2010 → jun/2013),
registrada em `checkpoints.yaml` sob `transitions`. É um checkpoint qualitativo
e depende de `plots.py`. Os quatro pontos são renderizados por inteiro,
**2013 incluído** — ver §11 para por que a censura de out/2013 não afeta a forma
da pirâmide e por que o artigo também não classifica 2013.

---

## 10. "symfony" — dois projetos raiz com o mesmo nome (resolvido, sem mudança)

**Status:** investigado, nenhuma alteração no pipeline. A hipótese que motivou a
checagem estava errada no mecanismo, mas a checagem valeu — confirmou por uma
fonte independente que o projeto certo já estava em uso.

### Hipótese testada

Que a lista dos 90 estivesse usando `xphere-forks/symfony` (id 74915) — fork do
`symfony/symfony` real que o GHTorrent não marcou (`forked_from` NULL por
engano) — no lugar do id 51671, e que trocar fecharia 1 dos 4 projetos do
resíduo dos Tipos A-D.

### O que a base mostra

```sql
SELECT p.id, CONCAT(u.login,'/',p.name), p.created_at
FROM projects p JOIN users u ON u.id=p.owner_id
WHERE p.name='symfony' AND p.forked_from IS NULL;
```
```
51671  symfony/symfony        2010-01-04
74915  xphere-forks/symfony   2013-08-19
```

**Os dois estão nos 90** — não há troca a fazer. `symfony` é a única colisão de
`name` dentro do filtro (`GROUP BY name HAVING COUNT(*)>1` devolve só ela). O
pipeline identifica escopo por `p.id` e rotula com `CONCAT(login,'/',name)`,
então os dois aparecem como labels distintos e nenhum sombreia o outro.

Em 2013-09-30 (`metrics.table('2013-09-30')`):

| id | label | coding | non | total | CCR | NCR | Tipo |
|---|---|---|---|---|---|---|---|
| 51671 | symfony/symfony | 298 | 370 | **668** | -0.195 | -0.029 | D |
| 74915 | xphere-forks/symfony | 2 | 1 | **3** | +0.500 | +0.500 | A |

Os "2 contribuidores ativos" que motivaram a suspeita são do fork (74915), não
do symfony real. O symfony real tem 668 contribuidores e já estava sendo usado.

### Confirmação independente

O IEICE16 Fig.8 usa `symfony` entre os projetos de projeção, que exigem >100
contribuidores. Dos dois, só 51671 passa no filtro (668 vs 3) — checado:
`t[t.total>100]` contém 51671 e não contém 74915. O symfony do artigo é o
51671, que é o que o pipeline já usa. Fecha a questão sem depender da nossa
leitura do dump.

### Contrafactual (rodado, não adotado)

Excluir 74915 como se fosse fork:

| cenário | A | B | C | D | classificados | L1 |
|---|---|---|---|---|---|---|
| atual | 27 | 40 | 14 | 4 | 85 | **11** |
| sem 74915 | 26 | 40 | 14 | 4 | 84 | **10** |

Melhora L1 em 1 e **piora** a contagem de classificados (84 contra 86 do
artigo). Não adotado: os dois sanity checks do §1.1.1 concordam no mesmo
conjunto de 90 (`forked_from IS NULL AND id<>108342` e `forked_from IS NULL AND
language IS NOT NULL` — 74915 é PHP, entra nos dois; 108342 tem `language`
NULL, sai dos dois). Remover 74915 daria 89 projetos e contradiria o escopo
declarado pelo artigo. Trocar 1 ponto de L1 por um desvio no escopo é mau
negócio.

### Nuance que isso revelou sobre o resíduo

`symfony/symfony` é Tipo D com **NCR = -0.0295**, o menor |NCR| de todos os 85.
O artigo tem 3 Tipos D e nomeia `rails`; nós temos 4 (`knitr`, `ccv`,
`rails`, `symfony`). Se symfony caísse do outro lado do zero seria B, e a
contagem viraria 3 D / 41 B (L1 = 9).

Isso qualifica o §9.1 item 5: **nem todo o resíduo é ruído de amostra pequena.**
Os casos `blueprint-css` (1 contribuidor) e `memcached` (3) são; `symfony`, com
668 contribuidores, não é — é um projeto genuinamente sobre a linha, onde NCR
fica a 3 centésimos de zero. Nenhuma decisão de método desempata isso: o corte
em zero é o que os artigos especificam, e a regra de empate já está fixada
(§6 deste doc). Fica como fronteira real, não como erro. Não reabrir sem uma
fonte nova (ex.: o valor exato de NCR do symfony na Fig.5, se for legível).

## 11. Truncamento à direita: 2013 não classificável, 2012 subestimado em ~5%

**Status:** limitação conhecida do dataset, quantificada. Não é bug.

O dataset acaba em **2013-10-06 04:27:14**. Como stickiness do ano Y precisa
olhar Y+1 inteiro, isso tem duas consequências, de gravidade bem diferente:

**2013 não é classificável, e isso é definitivo.** Não há Y+1. O
`attractiveness.py` marca esses anos com `right_censored` e os exclui da
classificação em vez de reportar stickiness 0 — que é o modo silencioso de
errar aqui, porque 0 é indistinguível de "ninguém voltou" e jogaria todo
projeto de 2013 no quadrante terminal. O log emite um `WARNING` explícito para
2013 por esse motivo.

**2012 é classificável, mas com stickiness levemente subestimada.** Devs ativos
em 2012 que só voltariam entre 7/out e 31/dez/2013 não aparecem. Isso é
mensurável nos anos completos — basta contar, nas retenções observadas, quantas
tiveram a primeira reaparição depois de 6/out:

| ano Y | retenções observadas | primeira volta só após 6/out de Y+1 | % |
|---|---|---|---|
| 2010 | 993 | 51 | 5,1% |
| 2011 | 2062 | 117 | 5,7% |
| 2012 | 2301 | 0 | 0,0% (por truncamento) |

Ou seja: a stickiness de 2012 perde da ordem de **5–6% das retenções**, não uma
fração grande. E, crucialmente, a classificação não usa o nível absoluto — usa
o corte na **mediana do próprio ano**. Um viés que atinge todos os projetos de
forma parecida desloca numerador e mediana juntos e se cancela em boa parte. O
que ele *pode* virar é desempate errado em projetos que já estejam colados na
mediana; os que estão longe dela não mudam de quadrante por 5%.

### 11.1 Consequência para a Fig.3: renderizar 2013, não classificar 2013

A censura atinge a **métrica anual**, não a **forma da pirâmide**. São coisas
independentes:

- a pirâmide de um ano Y é montada só com eventos até Y — é um retrato de
  estoque, olha para trás. jun/2013 tem 9 meses de dados *do próprio ano*, que
  é tudo que a pirâmide de 2013 precisa;
- stickiness de Y é uma métrica de fluxo que olha para frente, para Y+1. É essa
  que não existe para 2013.

Portanto a Fig.3 é renderizada nos **quatro pontos (2010, 2011, 2012, 2013)**,
com a pirâmide completa em cada um, e **nenhuma classificação formal**
(attractive / fluctuating / stagnant / terminal) é atribuída a 2013.

Isso não é uma acomodação nossa: é exatamente o que o ESEM14 faz. Os autores
trabalhavam com o mesmo dataset e o mesmo corte em out/2013, e no parágrafo do
`jekyll` (§5, discussão da Fig.3) a única categoria formal que eles cravam é a
de 2011 — para 2013 descrevem a *forma* e passam a linguagem condicional:

> "Number of discussion and coding contributors continued to increase, and the
> population pyramid becomes balanced shape in 2013. This project classiﬁed as
> terminal project in 2011. However, there are many discussion contributors,
> which is diﬀerent from the case of the blueprint-css. Therefore, **we think
> this project had a possibility to become attractive or ﬂuctuating project in
> near future**."
>
> — Onoue et al., ESEM 2014, §5 (grifo nosso)

Note a assimetria no próprio texto do artigo: "classified as terminal project
in 2011" (categoria afirmada, ano com Y+1 disponível) contra "had a possibility
to become attractive or fluctuating" (duas categorias em aberto, futuro além do
dataset). Eles descrevem a pirâmide de 2013 como "balanced shape" — um
adjetivo de forma, não um dos quatro quadrantes. Reproduzir isso é fidelidade,
não aproximação.

O último ano com classificação formal deste lado é, portanto, **2012** (com o
viés de ~5% da tabela acima). O gráfico anota `right-censored` no painel de
2013 em vez de um rótulo de quadrante.

**O que continua proibido:** inventar um 2013 parcial anualizado para forçar um
quadrante. Isso mistura uma janela de 9 meses com janelas de 12 e produz um
número que parece comparável e não é — e vai além do que os próprios autores
afirmaram com os mesmos dados.

---

## §12 — Projeção coorte-componente (IEICE16 §4, Tabelas 3 e 4)

### 12.1 Causa raiz: a pirâmide precisa ser a população *ativa*

A primeira versão da projeção usava, como população de cada banda, todo mundo
que já havia contribuído até o snapshot — o acumulado histórico. O resultado foi
um ABRE mediano de **0.006**, contra os **0.4000** publicados: duas ordens de
grandeza de "acurácia" a mais que o artigo.

O número denunciava o erro. Num acumulado histórico ninguém morre: a cada
trimestre a banda `b` inteira reaparece em `b+1`, a taxa de sobrevivência é
identicamente 1 e a projeção vira o deslocamento puro da última medida. Ela
acerta na mosca **sem ter previsto nada** — e, pior, o baseline (repetir a
última medida) erra, então o método coorte "ganhava" com folga em todas as
células. A conclusão do artigo era reproduzida pelos motivos errados.

A correção é aplicar o mesmo filtro que o resto do pipeline já usava:

> "we regarded that a contributor left the project when he/she did not give any
> contribution for more than three months"
> — IEICE16 §3.1

`src/pyramid/projection.py` agora filtra `snaps["active"]` antes de montar as
bandas, alinhando a projeção com `metrics.py` e `plots.py`. `tests/test_projection.py`
trava o comportamento por dois lados: `test_populacao_imortal_e_projetada_sem_erro`
fixa a aritmética que produz o acerto falso, e
`test_checkpoint_abre_na_ordem_de_grandeza_do_artigo` reprova qualquer ABRE fora
da faixa publicada — teria falhado com 0.006.

### 12.2 O que fecha e o que não fecha

Com o filtro correto, `All types / all`:

| | cohort | baseline |
|---|---|---|
| IEICE16 Tabela 3 | 0.4000 | 0.6000 |
| réplica | 0.4208 | 0.5000 |

O `cohort` fica a ~5% do publicado. Algumas células batem de forma quase
literal — Type C / non-coding sai **0.6723 / 1.0000** contra **0.6711 / 1.0000**
do artigo — mas isso é coincidência de amostra pequena, não validação: outras
divergem bem mais, e duas invertem o sinal da comparação (ver 12.3).

A conclusão central do §4 se sustenta: no agregado, a projeção por coorte erra
menos que o baseline (0.4208 < 0.5000, Wilcoxon p = 0.0073, contra p < 0.00001
no artigo). É o único predicado que `test_checkpoint_coorte_bate_o_baseline_no_agregado`
exige, justamente por não depender do dataset específico.

### 12.3 Divergências que permanecem — não corrigidas

**(a) 34 projetos elegíveis, não 36.** O artigo usa "36 projects that have more
than 100 contributors". Aplicando o corte sobre contribuidores *ativos* no
snapshot base (2013-03-31) chegamos a 34; dois projetos ficam na fronteira dos
100. Não forçamos o número: mexer no corte para chegar a 36 seria ajustar o
método ao resultado. `test_checkpoint_projetos_elegiveis_perto_dos_36` trava 34
para que a contagem não deslize em silêncio.

**(b) `non-coding` inverte o sinal.** No agregado o artigo tem cohort 0.5000 <
baseline 0.6667; nós temos 0.5664 > 0.5000, com Wilcoxon p = 0.32 (não
significativo). É a única das quatro categorias que anda para o lado errado.

**(c) curto vs. longo prazo inverte.** IEICE16 §4 reporta short-term 0.4055 pior
que long-term 0.3333 (p = 0.0460). Nós obtemos short 0.3412 e long 0.5000
(p = 0.1192) — ordem trocada e sem significância. A suspeita é que nossa cauda
longa seja rala demais: com a janela de 2010-2013 e 34 projetos, as bandas
acima de ~4 anos têm poucos contribuintes por coorte, e o ABRE de contagens
pequenas é dominado por ruído de ±1 pessoa. Não investigado a fundo.

**(d) 195 coortes sem denominador — tratado, ver 12.4.**

**Leitura honesta do conjunto:** a mecânica do §4 está reproduzida e a tese
central se sustenta, mas (b) e (c) são resultados do artigo que a réplica **não**
reproduz. O dataset não é o mesmo (34 projetos contra 36, coortes diferentes),
o que torna a comparação célula a célula pouco conclusiva nos dois sentidos —
inclusive nas células que casaram.

### 12.4 As 195 coortes órfãs: semântica corrigida, números inalterados

Quando a banda anterior está vazia no snapshot base, a taxa de sobrevivência é
`p_last[b+1] / p_base[b]` com `p_base[b] == 0`. São dois casos que o código
antigo tratava igual, e não são a mesma coisa:

- **banda vazia dos dois lados** (`p_base[b] == p_last[b] == 0`): ninguém
  envelhece para `b+1`, e prever 0 é uma afirmação substantiva. 3256 células,
  alvo de fato vazio em 98.9% delas. Continua prevendo 0.
- **coorte órfã** (`p_base[b] == 0` mas `p_last[b] > 0`): a banda apareceu
  povoada sem ter existido no trimestre anterior. A sobrevivência é indefinida.
  195 células — e o alvo tem gente de verdade em **73.8%** delas.

O ponto: `SR = 0` é uma previsão de extinção, não ausência de sinal. Cravar 0
onde não há denominador afirma "esta coorte vai desaparecer" em 195 lugares
onde o dado não diz nada, e erra em três de cada quatro. O erro é sistemático
numa direção só — infla o ABRE do método coorte e favorece a baseline de graça.
`project()` agora devolve `nan` (= "o método não responde") e a célula sai do
cálculo, em vez de entrar como acerto ou erro inventado.

**Onde caem, por (tipo, categoria):**

| tipo | coding | moved | non_coding | total | projetos | órfãs/projeto | alvo povoado |
|---|---|---|---|---|---|---|---|
| A | 20 | 13 | 8 | 41 | 8 | 5.1 | 73.2% |
| B | 50 | 37 | 27 | 114 | 19 | 6.0 | 72.8% |
| C | 10 | 8 | 9 | 27 | 5 | 5.4 | 81.5% |
| D | 7 | 2 | 4 | 13 | 2 | 6.5 | 69.2% |

C+D somam 40 (20.5% das órfãs), mas isso é só a contagem de projetos: **por
projeto a taxa é plana** (5.1 a 6.5) e a fração de alvo povoado idem (69–82%).
Não há concentração em tipo nenhum — a hipótese de que as órfãs explicariam o
comportamento anômalo de C/D nas Tabelas 3 e 4 **não se sustenta**.

**A correção não move nenhum número publicado.** Rodado o contrafactual com a
semântica antiga lado a lado:

| | linhas | pares | All/all cohort | All/all baseline | short | long | p |
|---|---|---|---|---|---|---|---|
| antigo (órfã → 0) | 1024 | 333 | 0.4208 | 0.5000 | 0.3412 | 0.5000 | 0.1192 |
| novo (órfã → nan) | 1206 | 333 | 0.4208 | 0.5000 | 0.3412 | 0.5000 | 0.1192 |

Idênticos, e o motivo importa: com previsão 0, `abre(actual, 0)` já caía em
`min(actual, 0) == 0` e devolvia `nan`; a célula morria depois, em vez de antes.
O viés que a análise acima descreve era real na intenção do código, mas nunca
chegou às medianas — as duas rotas descartavam as mesmas 195 coortes. O que
muda é o registro: 182 linhas que sumiam em silêncio agora existem com
`abre_cohort = nan`, auditáveis. **Isso desqualifica as órfãs como explicação
para 12.3(b) e 12.3(c)** — a inversão do `non-coding` e a de curto/longo prazo
sobrevivem intactas à correção e continuam sem causa identificada.

Travado por `test_coorte_orfa_nao_inventa_sobrevivencia_e_e_contada` e
`test_projecao_nunca_e_negativa`.

```
# breakdown por (tipo, categoria) e contrafactual da semântica antiga
DATASET_DIR=~/Downloads/268528 .venv/bin/python -c "..."   # ver 12.4 no histórico
DATASET_DIR=~/Downloads/268528 .venv/bin/pyramid projection --force
.venv/bin/pytest tests/test_projection.py -q
```

### 12.5 Comparação célula a célula com a Tabela 3 (antes de reportar qualquer ABRE)

Regra assumida: nenhum valor de ABRE por tipo é reportado como replicado sem
passar por esta comparação. Tolerância de 2% relativa (`tolerance_rel` em
`config/checkpoints.yaml`), 40 células (5 tipos × 4 categorias × cohort/baseline).

**7 de 40 células dentro de 2%.** As que batem:

| célula | artigo | réplica |
|---|---|---|
| A / all / baseline | 0.5000 | 0.5000 |
| B / moved / baseline | 0.5000 | 0.5000 |
| B / all / cohort | 0.5000 | 0.5000 |
| C / non_coding / cohort | 0.6711 | 0.6723 |
| C / non_coding / baseline | 1.0000 | 1.0000 |
| C / all / baseline | 0.6667 | 0.6607 |
| All types / moved / baseline | 0.5000 | 0.5000 |

Quatro das sete são o valor 0.5000 — mediana de coortes que caem em razões de
inteiros pequenos. Casar em 0.5000 é fraco como evidência: é o valor mais
provável de sair por acaso nesse regime. As duas células de C/non_coding e a
de C/all são as únicas coincidências não triviais, e §12.2 já as classificou
como amostra pequena, não validação.

**Direção (cohort < baseline?) concorda em 14 de 20 pares.** Das 6 que
discordam, 4 são empate exato na réplica (`c = b`, todas em 0.5000): B/moved,
B/all, C/moved, e o par de B/non_coding. Empate não é inversão — é resolução
insuficiente. Inversões reais, com o cohort de fato pior que a baseline:
**non_coding em B e no agregado**, e **D/moved**. É exatamente o 12.3(b), agora
localizado: o problema do `non-coding` não é difuso, mora no Type B (19 dos 34
projetos) e daí sobe para o agregado.

Conclusão operacional: a Tabela 3 **não** é reproduzida célula a célula, e não
deve ser apresentada como tal. O que se sustenta é o predicado agregado do §4
(cohort bate baseline, 0.4208 < 0.5000, p = 0.0073) e a direção em 14/20 pares.
`test_checkpoint_abre_na_ordem_de_grandeza_do_artigo` trava a faixa; nenhum
teste trava célula individual, de propósito.

---

## 13. jekyll em 2011: o checkpoint da Fig.2 é 4/5, não 4/4 (aberto)

**Como apareceu.** Não apareceu num teste — apareceu no `pyramid validate`. O
§9 fechou a Fig.2 com os quatro projetos que a *legenda* nomeia, um por
quadrante, e os dois testes de checkpoint travam exatamente esses quatro. Mas o
ESEM14 nomeia um quinto projeto no **corpo do texto**, na discussão da Fig.3
(p. 5, coluna 2):

> "Finally, we examine the changes of the jekyll's software population pyramids,
> which was **also a terminal project in 2011**."

Esse "also" liga jekyll aos projetos terminais da Fig.2. É um rótulo publicado,
verificável, e a réplica erra:

| ano | magnetismo | mediana | stickiness | mediana | quadrante |
|---|---|---|---|---|---|
| 2010 | 0.008734 | 0.011827 | 0.1034 | 0.2578 | **terminal** |
| 2011 | 0.009960 | 0.007284 | 0.0519 | 0.1928 | **floating** (artigo: terminal) |
| 2012 | 0.007741 | 0.007117 | 0.1975 | 0.1548 | attractive |
| 2013 | 0.016609 | — | — | — | não classificado (§11) |

**Onde exatamente erra: só no eixo do magnetismo.** Na stickiness jekyll é o
5º menor entre 75 elegíveis (0.0519 contra mediana 0.1928) — é terminal com
folga enorme nesse eixo. No magnetismo fica no posto 47 de 75, com a mediana no
posto 38: nove posições acima do corte, dentro de uma faixa densa
(0.0094–0.0110 cobre os postos 43–51). Em contagem bruta: jekyll teve 67
novatos em 2011 sobre 6727 novatos do dataset inteiro; para cair em terminal
precisaria de **≤ 49**. São 18 novatos de excesso, ~27%. Não é empate na
fronteira, e não vale tratar como ruído de arredondamento.

**Contrafactual testado e descartado: ancoragem em junho.** Os painéis da Fig.3
são rotulados 2010/06 … 2013/06, então "2011" podia significar a janela
jul/2010–jun/2011 em vez do ano civil. Reprocessei o estágio inteiro com o ano
deslocado seis meses (`/tmp/jun_anchor.py`, ano fiscal jul..jun):

```
DATASET_DIR=$DATASET_DIR .venv/bin/python /tmp/jun_anchor.py
  clojure        stagnant    ok
  homebrew       attractive  ok
  paperclip      floating    ok
  jekyll         floating    MISS (esperado terminal)
  blueprint-css  nan         MISS (esperado terminal; perde elegibilidade)
```

A ancoragem em junho piora o checkpoint de 4/5 para 3/5 — não conserta jekyll e
ainda derruba blueprint-css abaixo do mínimo de devs ativos. O ano civil é a
leitura certa, coerente com `checkpoints.yaml`, que registra a Fig.2 como
snapshot de dez/2011. **A hipótese da janela está descartada; o desvio de
jekyll é real.**

**O que isto provavelmente é.** A direção do erro coincide com a do §3.1: lá
sobra projeto no Tipo A e falta no Tipo C, isto é, a réplica **classifica
novato demais**. Aqui o magnetismo — que é literalmente uma contagem de novatos
sobre o total — sai alto demais para jekyll, e é exatamente isso que o empurra
de terminal para floating. São duas métricas independentes apontando o mesmo
viés na mesma direção, o que é evidência melhor do que qualquer uma das duas
sozinha. jekyll é o caso onde esse viés mais aparece porque foi o projeto que
mais cresceu em contribuidores no período (14 → 40 → 29 → 77 → 81 devs/ano):
quanto mais entrante, mais exposto ao critério de "primeira aparição".

Consistente com isso, a **trajetória** da réplica reproduz a narrativa do artigo
adiantada em um ano: terminal → (cresce) → attractive, com o artigo pondo
"terminal" em 2011 e a réplica em 2010. Note que os outros quatro projetos
batem no ano civil de 2011 sem deslocamento nenhum — **não** há offset global de
um ano; é específico de jekyll.

**O que foi mudado no repositório:** nada no cálculo. Corrigir isto exige
acertar a definição de novato, que é o §3.1 em aberto, e mexer nela para
consertar um projeto seria ajustar o método ao gabarito. O que muda é a
contabilidade honesta:

- o título do §9 passa a dizer 4/5, com ponteiro para cá;
- `checkpoints.yaml` ganha jekyll/2011 sob `attractiveness`, e o `validate`
  reporta a falha em vez de ignorá-la;
- `test_checkpoint_jekyll_2011_diverge` trava o valor **medido** (floating), não
  o do artigo, com a referência a esta seção. Se um refactor futuro fizer jekyll
  virar terminal, o teste quebra e obriga a reler esta seção — que é o
  comportamento certo, porque nesse dia o checkpoint vira 5/5 e este item fecha.

**Fica aberto.** Não há aproximação a fazer aqui: ou a definição de novato muda
e os cinco batem, ou o §3.1 permanece como a explicação comum dos dois desvios.

---

## 14. `scope_label` dependia de ordem de chamada (corrigido, sem efeito em número)

### Sintoma

`pyramid validate` reportava `types.examples.*` com "obtido" = `25875`, `78835`,
… — o próprio id do escopo — em vez de `jquery/jquery`, `divio/django-cms`. A
legenda da Fig.5 tinha o mesmo problema quando a figura era gerada sozinha
(`pyramid plot --figure fig5`), com os pontos rotulados por número.

### Causa raiz

`MSR14Source.list_scopes()` construía o dicionário `_labels` como efeito colateral
e `scope_label()` só lia esse dicionário. Quem chamasse `scope_label` sem ter
passado por `list_scopes()` **na mesma instância** caía no `.get(id, str(id))` e
recebia o id de volta. Os estágios do pipeline (`extract`, `classify`,
`snapshots`, `attractiveness`) chamam `list_scopes()` logo no início do `run()`,
então nunca viram o defeito; `metrics.table()` — usada por `validate` e pelo
`plot --figure fig5` fora do pipeline — não chama.

Este é o modo de falha ruim: sem exceção, sem log, só um rótulo plausível.

### Correção

`scope_label()` passou a carregar o mapa sob demanda (`_load_labels()`), com o
cache preservado. `list_scopes()` reusa o mesmo carregamento. Id que realmente
não é raiz continua virando string — aí o fallback é a resposta certa.

```
grep -n "def scope_label" -A 16 src/pyramid/sources/msr14.py
pyramid validate --report output/validation_report.md   # types.examples.* → nomes
pyramid plot --figure fig5                              # legenda com nomes
```

### Alcance

Nenhum número muda. `type`, `ccr`, `ncr`, quadrante e todas as tabelas são
calculados por `scope_id`; o rótulo é cosmético e entra só na apresentação. O
que muda é que os oito `types.examples.*` do relatório passam a ser verificáveis
por leitura — antes eles batiam por serem comparados contra o gabarito por id,
e o "obtido" impresso não dizia nada a quem lesse.

### Guarda contra reincidência

`validate` compara `types.examples.<id>` contra o tipo (A–D) do artigo e imprime
o rótulo na coluna de referência; se o rótulo regredir para o id, o relatório
mostra a regressão na cara. A regra geral que isto reforça — já aplicada ao
manifesto — é que **artefato nenhum guarda `repr` de objeto ou id cru onde um
nome estável é o esperado**.

## 15. Novato é do dataset, não do projeto (§3.1) — hipótese testada e descartada

O §13 fechou com uma suspeita nomeada: a réplica classificaria "novato demais",
e jekyll/2011 cairia em `attractive` porque o magnetismo sai alto. A única
alavanca real por trás disso é a definição de novato. Ou o numerador do
magnetismo conta *quem estreou no dataset*, ou conta *quem estreou naquele
projeto*. As duas leituras dão o mesmo número na Fig.1 do MSR'14 e divergem em
todo projeto que recebe veterano vindo de outro repositório.

### O que o artigo diz

MSR'14 §2, imediatamente antes da definição (p.1, coluna 2):

> However, the definition cannot be applied directly to open source projects,
> **where a contributor can contribute to several projects at the same time.**
> Therefore, we expand original definition to apply to open source projects as
> follows: [...] we calculate the magnetism of a project as **the proportion of
> contributors who made their first contribution in the time period under study
> who contribute to a given project.**

A frase resolve o caso sozinha, e resolve duas vezes:

1. `first contribution in the time period under study` qualifica a **pessoa**;
   `who contribute to a given project` é o filtro de quem, dentre esses,
   conta para o projeto. O projeto entra como recorte, não como universo.
2. O motivo declarado da expansão é justamente o contribuidor multi-projeto.
   Ler "novato" como "primeira aparição neste repositório" desfaz a expansão:
   voltaria a tratar cada projeto como um mundo fechado, que é a leitura que
   os autores dizem não poder aplicar.

É o que `src/pyramid/attractiveness.py` já faz — o denominador é global (todos
os novatos do ano no dataset) e o numerador é a interseção com o projeto.

```
grep -n "first_year\|newcomers_here\|newcomers_total" -B 2 -A 6 src/pyramid/attractiveness.py
sed -n '78,93p' /tmp/msr14.txt      # pdftotext -layout docs/papers/MSR14.pdf
```

### O denominador é sobre a população certa

`activity()` cobre os 90 escopos do dump — a mesma população dos 90 projetos do
MSR'14 (§1.1.1). Se um parquet faltasse, o denominador encolheria em silêncio,
por isso a função levanta `FileNotFoundError` em vez de rodar com 89. E as
triplas são únicas, então `newcomers_here` não infla por linha repetida:

```
pyramid attractiveness   # 36335 linhas, 36335 chaves (scope_id, contributor_id, year)
```

### Contrafactual (rodado, não adotado)

Variante **P** = "novato é quem aparece pela primeira vez *neste* projeto",
comparada contra a Tabela 2 do MSR'14 (12 projetos × 8 anos, 55 células com
rótulo publicado). Âncora primeiro: a variante **G** reimplementada bate com
`attractiveness.annual()` em **96/96** células — sem isso a comparação seria
entre duas reimplementações, não entre duas definições.

| variante | acertos | falhas |
|---|---|---|
| **G** — novato do dataset (atual) | **48/55 (87%)** | 7 |
| P — novato do projeto | 45/55 (82%) | 10 |

P **não corrige nenhuma** das 7 falhas de G. Quebra 3 células que G acertava
(2008 `scala`, 2008 `django-debug-toolbar`, 2008 `jekyll`) e mantém as outras
7 idênticas, jekyll/2011 inclusive.

```
DATASET_DIR=$DATASET_DIR .venv/bin/python scripts/contrafactual_novato.py
```

### A direção do efeito enterra a hipótese do §13

P conta **mais** novatos, não menos:

```
pares (projeto,pessoa,ano) nos 12 projetos x 8 anos: 3882
novatos sob G: 2906
novatos sob P: 3047  (+4.9%)
```

Se a réplica classifica novato demais, a variante alternativa classificaria
~5% a mais ainda. Não existe leitura de "novato" que empurre jekyll/2011 na
direção do artigo: o eixo está esgotado. O §13 continua aberto, mas sem este
suspeito — o resíduo de jekyll não vem da definição de novato, e a próxima
hipótese tem que atacar outra coisa (janela de atividade ou o corte do sticky).

### Guarda contra reincidência

Dois testes em `tests/test_attractiveness.py`:

- `test_exemplo_figura1_do_msr14` — a aritmética publicada (magnetismo 2/3 e
  1/3, sticky 1/1 e não 2/1). Trava a armadilha do sticky, mas **não** separa
  G de P: no exemplo dos autores ninguém é veterano do dataset e estreante em
  um projeto.
- `test_novato_e_do_dataset_nao_do_projeto` — separa. Veterano troca de
  projeto: o projeto novo tem magnetismo **0**, não 1/2. Sob P este teste falha.

```
.venv/bin/python -m pytest tests/test_attractiveness.py -q   # 11 passed
```

## 16. As 7 células residuais da Tabela 2 do MSR'14 (48/55 = 87%)

A Tabela 2 do MSR'14 virou instrumento permanente de validação (§11.1): 12
projetos × 8 anos, 55 células com quadrante publicado, mais as células `-`
(sem atividade) e `*` (devs ≤ 10) que testam a elegibilidade. A réplica bate
**48/55**, e a estrutura `-`/`*` bate **integralmente**. Esta seção fecha as 7
restantes — cada uma com causa nomeada e medida, nenhuma com correção de
conveniência.

### Antes: as duas ambiguidades do limiar, decididas pela própria tabela

O artigo diz apenas "we use the median magnet and sticky values as the
thresholds" (MSR'14 §2, p.3). Isso deixa duas coisas em aberto, e as duas
mudam célula: **sobre qual população a mediana é tirada** e **o que acontece
com quem cai exatamente em cima dela**. A tabela de 55 células é grande o
bastante para decidir as duas empiricamente.

| leitura do limiar | acertos |
|---|---|
| **(a) mediana anual dos elegíveis (adotada)** | **48/55 (87%)** |
| (c) mediana anual de todos os projetos, sem filtro | 34/55 (62%) |
| (d) mediana global, um limiar para todos os anos | 28/55 (51%) |
| (b) mediana de 2011 fixada para todos os anos | 25/55 (45%) |

| regra de empate | acertos |
|---|---|
| **`>` estrito — "higher than the median" (adotada)** | **48/55** |
| `>=` — empate conta como alto | 46/55 |

A margem de (a) sobre as alternativas é grande demais para ser sorte, e as duas
escolhas já estavam no código antes deste teste — a tabela confirmou, não
escolheu. O `>=` merece nota: ele **corrige** 2 das 7 falhas (xbmc/2007 e
xbmc/2009) e **quebra 4 células que hoje batem** (2005 `rails`, 2005 `xbmc`,
2007 `django`, 2004 `scala`). São 6 empates exatos na tabela, 4 pedindo `>` e
2 pedindo `>=`: a regra de empate do artigo é **irrecuperável por engenharia
reversa**, porque a própria Tabela 2 é inconsistente nela. Fica o `>` — leitura
literal de "higher than", e a que maximiza acordo.

```
DATASET_DIR=$DATASET_DIR .venv/bin/python scripts/contrafactual_limiar.py
```

### Onde as falhas caem: em cima da linha da mediana

Para cada célula, `margem` = distância relativa do projeto à mediana no eixo
que decide o quadrante (o menor dos dois desvios). Ela mede quanto o rótulo
depende de precisão numérica:

| células | n | margem mediana | margem mínima |
|---|---|---|---|
| batem | 48 | 19,3% | 0,0% |
| falham | 6 | 4,8% | 0,0% |

*(scala/2010 fica fora: não é erro de rótulo, é ausência de dado — abaixo.)*

Das 6, **4 estão a ≤ 5,1% da mediana** e 2 estão *exatamente em cima* dela:

| ano | projeto | artigo | réplica | magnet vs mediana | sticky vs mediana | margem |
|---|---|---|---|---|---|---|
| 2007 | `xbmc/xbmc` | attractive | floating | +83,3% | **+0,0%** | **0,0%** |
| 2009 | `xbmc/xbmc` | attractive | stagnant | **+0,0%** | +198,3% | **0,0%** |
| 2010 | `chriseppstein/compass` | floating | terminal | −4,6% | −40,3% | 4,6% |
| 2010 | `jquery/jquery` | floating | attractive | +143,1% | +5,1% | 5,1% |
| 2011 | `mojombo/jekyll` | terminal | floating | +36,7% | −73,1% | 36,7% |
| 2011 | `django/django` | attractive | stagnant | **−91,8%** | +335,7% | 91,8% |

As duas de margem 0,0% são o projeto que *define* a mediana daquele ano naquele
eixo — sob `>` estrito o projeto mediano nunca é "alto" no eixo em que ele é a
mediana. Isso não é aproximação nossa: é o mesmo empate que o artigo resolve
para o outro lado em 4 células e para este lado em 2. Nas células longe da
linha (margem > 10%), o acordo é **de 37/37 fora as duas de baixo** — o método
reproduz; o que não reproduz é o desempate.

### scala/2010: buraco de 18 meses no dump, não erro de classificação

Único caso em que a réplica não produz rótulo nenhum (`-`, "sem atividade")
contra um `floating` publicado. A causa está no dado bruto, antes de qualquer
código nosso:

```sql
SELECT DATE_FORMAT(created_at,'%Y-%m') m, COUNT(*) FROM commits
WHERE project_id=107534 AND created_at BETWEEN '2009-06-01' AND '2011-06-30' GROUP BY 1;
-- ... 2009-10: 221 | 2009-11: 87 | 2011-06: 1
```

Nenhum commit entre **2009-12 e 2011-05**, e o buraco não é do recorte de
escopo: incluindo os **466 forks** de scala (`project_commits`, escopo família)
o ano de 2010 continua com zero. Não é falha global do dump — 2010 tem 69.247
commits em 828 projetos. É específico do projeto, e casa com `projects.created_at
= 2011-12-01` para `scala/scala`: o que existe antes disso é histórico
importado, não atividade observada no GitHub. Efeito colateral coerente: o
sticky de scala/2009 sai **0,000** (nenhum dos 25 devs de 2009 aparece em 2010),
que é o que empurra a célula de 2009 para `terminal` — e essa o artigo também
diz `terminal`.

### django/2011: o repositório ainda não estava no GitHub

Não é célula de fronteira — é a maior margem da tabela (−91,8%). O magnetismo
de django em 2011 é **4 novatos** num universo de 6.727; para cruzar a mediana
precisaria de **50**. Fator 12, fora do alcance de qualquer ambiguidade de
limiar. A causa é a mesma de scala, mais visível:

```
projects.created_at de django/django = 2012-04-28
primeiro PR = 2012-04-28   primeira issue = 2012-04-28
eventos por ano: 2011 -> 1771 commits, 0 PRs, 0 issues
                 2012 -> 2122 commits, 613 PRs, 613 issues
```

Django migrou para o GitHub em abril/2012. Todo o histórico de 2005-2011 no
dump é importação de SVN: só commits, sem discussão, sem PR, sem issue. A
comunidade de 2011 aparece com 25 devs; em 2012, com 387. O stickiness alto
(0,84, +335% acima da mediana) confirma o retrato: um núcleo pequeno e fechado
de committers, que é o que a importação preserva. A réplica lê o dado que está
lá. Por que o MSR'14 lê `attractive` na mesma célula do mesmo dump é uma
pergunta sem resposta a partir dos artefatos publicados — e não há leitura de
magnetismo que transforme 4 novatos em 50.

Vale para as duas: os cortes de cobertura pré-migração não são ruído aleatório,
são **censura à esquerda por projeto** — a mesma família de problema do §11
(truncamento à direita), com a diferença de que a data de corte é uma por
projeto, não uma para o dataset. A Tabela 2 do MSR'14 publica rótulos para anos
que caem dentro dessa censura em pelo menos 2 dos 12 projetos.

### O que fica declarado

As 7 continuam impressas pelo `pyramid validate`, com rótulo `conhecida` e
ponteiro para cá — e se qualquer uma voltar a bater, o comando falha por
`OBSOLETA` (§14). Nenhuma foi silenciada, e o `msr14.tab2.concordancia`
(≥ 80%) continua sendo o portão que trava regressão no estágio.
