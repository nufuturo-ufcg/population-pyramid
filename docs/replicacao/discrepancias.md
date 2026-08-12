# Discrepâncias vs. os artigos originais

Registro do que foi investigado quando um checkpoint não bateu, qual leitura foi
escolhida e por quê. Documenta o que foi investigado e o resultado, nunca só
"não bateu". A regra está em `CONTRIBUTING.md`, seção "Os dois documentos vivos".

Checkpoint de referência: **IEICE16 Fig. 5**, snapshot set/2013.
`A=23, B=42, C=18, D=3`, 86 projetos classificados de 90
(4 sem contribuidores no período).

---

## 1. Resultado atual

| | A | B | C | D | classificados | sem contribuidor |
|---|---|---|---|---|---|---|
| IEICE16 Fig.5 | 23 | 42 | 18 | 3 | 86 | 4 |
| Esta replicação | 26 | 40 | 15 | 4 | 85 | 5 |

*(Valores em vigor, conferidos contra `output/validation_report.md` e a seção 38.1. Até
2026-08-08 esta tabela trazia `27/40/14/4` e `L1 = 11`, de uma rodada anterior à
correção da seção 32; o viés e as conclusões abaixo não mudam.)*

Erro L1 = 9 tipos, sobre 85 projetos classificados (contra 86 no artigo). O
viés é sistemático e sempre o mesmo: **sobra projeto em A, falta em C**, ou
seja, classifico newcomer demais. A e C só diferem pelo sinal do NCR, então
bastariam 4 projetos com mais experientes que novos para fechar.

Os 8 projetos que o artigo nomeia individualmente batem **8/8** (seção 3.1a), e os 4
projetos que fechariam o gap custam **1-2 contribuidores cada** (seção 3.1b). O
resíduo vive nos projetos de população 1-3: o gap custa só 1-2 contribuidores
por projeto, pequeno demais para ser falha sistemática do método.

O GATE da seção 9 pede acerto **exato**. Ele não passa. O que segue é o que foi
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

Escolhida: `prose`. Ganha por pouco no L1, mas ganha por muito no argumento:
`issues` mistura PRs com issues de verdade (69.633 de 150.362 linhas são PRs
disfarçados), então contá-la infla a discussão com o que já foi contado como
coding. O ESEM14 seção 3 concorda com a prosa.

### Escopo de commits (ambiguidade 2)

| Escopo | A | B | C | D | classif. | erro |
|---|---|---|---|---|---|---|
| `root` (`commits.project_id`) | 27 | 39 | 14 | 3 | 85 | **11** |
| `family_project_commits` (agrega forks) | 28 | 39 | 14 | 3 | 85 | 12 |

Agregar os forks move ~2% dos contribuidores ativos e **piora**. A seção 7.1 fica
resolvida a favor de `root`. A hipótese de que a contagem estava baixa por não
agregar forks está descartada: o dump já tem contribuidores suficientes.

### Definição de idade (ambiguidade 3): este era o erro grande

| Base | A | B | C | D | erro |
|---|---|---|---|---|---|
| `accumulated_active` (soma dos períodos de atividade) | 41 | 42 | 0 | 0 | 62 |
| `calendar_tenure` (tempo desde a origem) | 27 | 39 | 14 | 3 | **11** |

`accumulated_active` é a leitura literal de *"less than three months of activity
periods"* (p.1308) e é **impossível**: deixa C e D completamente vazios, quando o
artigo tem 21 projetos ali. Quase ninguém acumula 3 meses de atividade contínua,
então todo mundo vira newcomer para sempre. `calendar_tenure` é o que o método
demográfico emprestado exige. Numa pirâmide etária, idade é idade, gap não
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
   projetos que estão perto de zero. Fig.5 mostra vários exatamente aí
   (homebrew e rails são descritos como "próximos do centro").
2. **A versão do GHTorrent.** Nosso dump é o do MSR14 Challenge (cobertura até
   2013-10-06). Os autores publicaram em 2016 e podem ter usado um dump mais
   recente, com backfill dos mesmos projetos.
3. **Empates.** Resolvido, ver seção 6.

## 3.1 Investigação dirigida dos Tipos A-D

Quatro testes. Nenhum derrubou o erro 11, mas o (a) e o (b) juntos mudam o que a
discrepância significa.

**(a) Os 8 projetos nomeados no artigo batem todos os 8.** O IEICE16 rotula
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

**8/8.** Inclusive `rails`, que está a -0.03/-0.07 da origem (o ponto mais
difícil dos oito) e cai no quadrante certo. Todo projeto que o artigo permite
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
set/2013: um único contribuidor decide o quadrante do projeto inteiro. É
ruído de amostra pequena, que qualquer diferença de cobertura do dump (hipótese 2)
produz. Viés sistemático do método fica descartado: a causa é pontual, um único
contribuidor decide cada projeto minúsculo.

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
Tipos A-D é subdeterminado pelo texto em ~±4 de erro L1: "erro 11" e "erro 7"
aqui são a mesma replicação com uma frase ambígua lida de dois jeitos.

**(d) Projeto sem contribuinte: 5 vs 4 do artigo.** Sai de (c). Em `2013-09-15`
são exatamente 4, como no artigo. Nos outros dias, 5.

**Conclusão.** Os três itens da seção 9.1 estão fechados sem mudança de método: a
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
non-coding em t1 e é desenhado na banda "3 months"**; **C6 tem
exatos 6 meses de coding em t2 e cai na banda "6 months"**. Logo as faixas são
`(0,3]`, `(3,6]`, `(6,9]`. O rótulo do eixo é o limite SUPERIOR.

A implementação usava `floor(idade/3)`, que empurra 3 e 6 para a faixa
seguinte. Corrigido para `ceil(idade/3)-1` em `snapshots.py`.

**Efeito nos dados reais: nenhum.** Re-rodados os estágios 3 e 4 sobre os 90
projetos, as 1143 linhas de métricas ficaram idênticas em `new`,
`experienced`, `coding`, `non_coding`, `ccr`, `ncr` e `type`, porque nenhum
contribuidor real cai exatamente sobre um múltiplo de 91,3125 dias. A correção
melhora a fidelidade ao método; o resultado numérico já estava certo.

O mesmo exemplo fixou outras duas decisões, ambas já implementadas assim e
agora cobertas por teste (`tests/test_classify.py`, 25 casos):

- **idade de quem migrou conta a partir de `init_c`.** C3 em t2 tem 6 meses de
  non-coding e 2 de coding, e aparece na banda "3 months": a idade é a do lado
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
a girá-la até o checkpoint bater, que é exatamente o que `CONTRIBUTING.md`
proíbe em "Mudança que mexe em número". A
regra agora é fixa em `metrics._type_of` e é a leitura literal: alto = `valor >
0`, logo zero cai do lado baixo.

Em set/2013 isso afeta 2 projetos, ambos com CCR exatamente 0 por terem
`coding == non_coding`:

| projeto | coding | non_coding | CCR | NCR | tipo |
|---|---|---|---|---|---|
| MiniProfiler | 19 | 19 | 0.00 | +0.69 | B |
| ccv | 2 | 2 | 0.00 | -0.67 | D |

Efeito no resultado: **erro L1 continua 11** (era 11 com os dois fora, é 11 com
os dois dentro). O que muda é a cobertura: 83 → 85 projetos classificados de
86, e some a coluna "empates" do relatório. Ou seja: a regra melhora a
comparabilidade com o artigo sem alterar o erro que ele mede.

---

## 7. Filtro de projeção ">100 contribuidores": 35 medidos vs 36 do artigo (aceito)

O IEICE16 seção 4 restringe a projeção a "projects with more than 100 contributors"
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
contra 4/21/9/2, ou seja, dentro do ruído da classificação de base. O teste
não discrimina. O `n` é o único sinal limpo.

### Por que 34 é ruído de fronteira e não erro de método

> **Correção (2026-08).** Esta seção dizia **35**, com o 35º projeto em 102
> contribuintes. Aquela contagem foi feita com a data errada `2013-03-30`, antes
> de a causa raiz ser corrigida na seção 8. Com `2013-03-31` a janela de atividade de
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
"more than 100 contributors", e `> 100` o exclui. Mas ler a mesma frase como
"pelo menos 100" devolveria 35. A escolha está em `eligible_scopes()` como `>`,
seguindo o texto ao pé da letra, e é a diferença entre 34 e 35 nesta replicação.

O 36º candidato está 3 abaixo do corte. Qualquer alargamento pequeno na
definição de "ativo" (janela de 3 meses um pouco maior, ou uma tabela de evento
a mais no escopo) o empurra para dentro. Não existe limiar "errado" aqui: o
método está certo e os projetos marginais simplesmente não alcançam 100 na
nossa contagem.

**Decisão: aceitar 34, base 2013-03-31, contribuidores ativos, corte `> 100`.**
ABRE e Wilcoxon não dependem do número exato de projetos no filtro, só do
tamanho da amostra, então dois projetos a menos não comprometem o resultado que
o artigo mede. Ver seção 12.2, onde o agregado fecha a ~5% do publicado.
`test_checkpoint_projetos_elegiveis_perto_dos_36` trava o 34 para que a
contagem não volte a deslizar sem que alguém perceba.

### Bug latente encontrado no caminho

A série de snapshots gerava **`2013-03-30`**. O valor correto seria
`2013-03-31`. Contornado na hora ajustando a config para a data errada; a
causa raiz foi corrigida depois. Ver seção 8, que substitui este parágrafo.

---

## 8. Bug de geração da série de snapshots (corrigido)

**Status:** corrigido em 2026-08. Causa raiz confirmada, não contornada.

### Sintoma

`snapshot_dates()` produzia `2011-12-30`, `2012-12-30`, `2013-03-30`: dia 30 em
meses de 31 dias. A config foi inicialmente ajustada para casar essas datas
erradas (seção 7), o que escondeu o problema em vez de resolvê-lo.

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
(jun, set) estavam certas **só porque esses meses acabam mesmo no dia 30**. Foi
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
trimestre civil, que é o que o método pede (IEICE16 seção 4.1: March, June,
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

Tipos A-D em set/2013 seguem **27/40/14/4**, 85 classificados, erro L1 = 11.
Idênticos a antes do fix, como esperado, já que essa data não era afetada.

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
quadrante. O quinto projeto rotulado pelo artigo para 2011 (**jekyll**, no
corpo do texto: "also a terminal project in 2011") **não** bate, e é o item
aberto da **seção 13**. Esta seção documenta os quatro que fecham; ela dizia "4/4"
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

Ambos dão `skip` (não passam em falso) quando o parquet do estágio ainda não
foi gerado. Rodar só eles: `pytest -m checkpoint`.

**Nota de leitura sobre a tabela antiga desta seção.** A versão anterior deste
item trazia contagens do snapshot trimestral `2011-12-31` (homebrew com 1448
ativos, blueprint-css com 1). Elas não contradizem os números acima: magnetismo
e stickiness usam janela **anual** (ano civil de 2011), então homebrew aparece
com 1740 devs ativos no ano contra 1448 no trimestre. São janelas diferentes do
mesmo dado, e a seção 3.1 do ESEM14 é explícita em usar a anual.

`blueprint-css` com stickiness exatamente 0.0000 confirma pelo lado quantitativo
a leitura qualitativa que já estava aqui ("colapsada" na Fig.3): dos 11 devs que
tocaram o projeto em 2011, nenhum voltou em 2012.

**O que continua aberto:** a transição temporal da Fig.3 (jun/2010 → jun/2013),
registrada em `checkpoints.yaml` sob `transitions`. É um checkpoint qualitativo
e depende de `plots.py`. Os quatro pontos são renderizados por inteiro,
**2013 incluído**. Ver seção 11 para por que a censura de out/2013 não afeta a forma
da pirâmide e por que o artigo também não classifica 2013.

---

## 10. "symfony": dois projetos raiz com o mesmo nome (resolvido, sem mudança)

**Status:** investigado, nenhuma alteração no pipeline. A hipótese que motivou a
checagem estava errada no mecanismo, mas a checagem valeu: confirmou por uma
fonte independente que o projeto certo já estava em uso.

### Hipótese testada

Que a lista dos 90 estivesse usando `xphere-forks/symfony` (id 74915), fork do
`symfony/symfony` real que o GHTorrent não marcou (`forked_from` NULL por
engano), no lugar do id 51671, e que trocar fecharia 1 dos 4 projetos do
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

**Os dois estão nos 90**. Não há troca a fazer. `symfony` é a única colisão de
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
contribuidores. Dos dois, só 51671 passa no filtro (668 vs 3). Checado:
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
artigo). Não adotado: os dois sanity checks da seção 1.1.1 concordam no mesmo
conjunto de 90 (`forked_from IS NULL AND id<>108342` e `forked_from IS NULL AND
language IS NOT NULL`: 74915 é PHP, entra nos dois; 108342 tem `language`
NULL, sai dos dois). Remover 74915 daria 89 projetos e contradiria o escopo
declarado pelo artigo. Trocar 1 ponto de L1 por um desvio no escopo é mau
negócio.

### Nuance que isso revelou sobre o resíduo

`symfony/symfony` é Tipo D com **NCR = -0.0295**, o menor |NCR| de todos os 85.
O artigo tem 3 Tipos D e nomeia `rails`; nós temos 4 (`knitr`, `ccv`,
`rails`, `symfony`). Se symfony caísse do outro lado do zero seria B, e a
contagem viraria 3 D / 41 B (L1 = 9).

Isso qualifica a seção 9.1 item 5: **nem todo o resíduo é ruído de amostra pequena.**
Os casos `blueprint-css` (1 contribuidor) e `memcached` (3) são ruído de amostra
pequena. `symfony`, com 668 contribuidores, é um projeto genuinamente sobre a
linha, onde NCR fica a 3 centésimos de zero. Nenhuma decisão de método desempata
isso: o corte em zero é o que os artigos especificam, e a regra de empate já
está fixada (seção 6 deste doc). Fica como fronteira real. Não reabrir sem uma
fonte nova (ex.: o valor exato de NCR do symfony na Fig.5, se for legível).

## 11. Truncamento à direita: 2013 não classificável, 2012 subestimado em ~5%

**Status:** limitação conhecida do dataset, quantificada. Não é bug.

O dataset acaba em **2013-10-06 04:27:14**. Como stickiness do ano Y precisa
olhar Y+1 inteiro, isso tem duas consequências, de gravidade bem diferente:

**2013 não é classificável, e isso é definitivo.** Não há Y+1. O
`attractiveness.py` marca esses anos com `right_censored` e os exclui da
classificação em vez de reportar stickiness 0, que é o modo silencioso de
errar aqui, porque 0 é indistinguível de "ninguém voltou" e jogaria todo
projeto de 2013 no quadrante terminal. O log emite um `WARNING` explícito para
2013 por esse motivo.

**2012 é classificável, mas com stickiness levemente subestimada.** Devs ativos
em 2012 que só voltariam entre 7/out e 31/dez/2013 não aparecem. Isso é
mensurável nos anos completos. Basta contar, nas retenções observadas, quantas
tiveram a primeira reaparição depois de 6/out:

| ano Y | retenções observadas | primeira volta só após 6/out de Y+1 | % |
|---|---|---|---|
| 2010 | 993 | 51 | 5,1% |
| 2011 | 2062 | 117 | 5,7% |
| 2012 | 2301 | 0 | 0,0% (por truncamento) |

Ou seja: a stickiness de 2012 perde da ordem de **5-6% das retenções**, uma
fração pequena. E, crucialmente, a classificação usa o corte na **mediana do
próprio ano**. O nível absoluto fica de fora: um viés que atinge todos os
projetos de forma parecida desloca numerador e mediana juntos e se cancela em
boa parte. O
que ele *pode* virar é desempate errado em projetos que já estejam colados na
mediana; os que estão longe dela não mudam de quadrante por 5%.

### 11.1 Consequência para a Fig.3: renderizar 2013, não classificar 2013

A censura atinge a **métrica anual**, não a **forma da pirâmide**. São coisas
independentes:

- a pirâmide de um ano Y é montada só com eventos até Y: é um retrato de
  estoque, olha para trás. jun/2013 tem 9 meses de dados *do próprio ano*, que
  é tudo que a pirâmide de 2013 precisa;
- stickiness de Y é uma métrica de fluxo que olha para frente, para Y+1. É essa
  que não existe para 2013.

Portanto a Fig.3 é renderizada nos **quatro pontos (2010, 2011, 2012, 2013)**,
com a pirâmide completa em cada um, e **nenhuma classificação formal**
(attractive / fluctuating / stagnant / terminal) é atribuída a 2013.

Isso não é uma acomodação nossa: é exatamente o que o ESEM14 faz. Os autores
trabalhavam com o mesmo dataset e o mesmo corte em out/2013, e no parágrafo do
`jekyll` (seção 5, discussão da Fig.3) a única categoria formal que eles cravam é a
de 2011. Para 2013 descrevem a *forma* e passam a linguagem condicional:

> "Number of discussion and coding contributors continued to increase, and the
> population pyramid becomes balanced shape in 2013. This project classiﬁed as
> terminal project in 2011. However, there are many discussion contributors,
> which is diﬀerent from the case of the blueprint-css. Therefore, **we think
> this project had a possibility to become attractive or ﬂuctuating project in
> near future**."
>
> Onoue et al., ESEM 2014, seção 5 (grifo nosso)

Note a assimetria no próprio texto do artigo: "classified as terminal project
in 2011" (categoria afirmada, ano com Y+1 disponível) contra "had a possibility
to become attractive or fluctuating" (duas categorias em aberto, futuro além do
dataset). Eles descrevem a pirâmide de 2013 como "balanced shape". É um
adjetivo de forma. Os quatro quadrantes formais não entram: 2013 é
right-censored e não recebe classificação, como esta seção já estabeleceu.
Reproduzir isso é ser fiel ao artigo.

O último ano com classificação formal deste lado é, portanto, **2012** (com o
viés de ~5% da tabela acima). O gráfico anota `right-censored` no painel de
2013 em vez de um rótulo de quadrante.

**O que continua proibido:** inventar um 2013 parcial anualizado para forçar um
quadrante. Isso mistura uma janela de 9 meses com janelas de 12 e produz um
número enganosamente comparável, que vai além do que os próprios autores
afirmaram com os mesmos dados.

---

## 12. Projeção coorte-componente (IEICE16 seção 4, Tabelas 3 e 4)

### 12.1 Causa raiz: a pirâmide precisa ser a população *ativa*

A primeira versão da projeção usava, como população de cada banda, todo mundo
que já havia contribuído até o snapshot: o acumulado histórico. O resultado foi
um ABRE mediano de **0.006**, contra os **0.4000** publicados: duas ordens de
grandeza de "acurácia" a mais que o artigo.

O número denunciava o erro. Num acumulado histórico ninguém morre: a cada
trimestre a banda `b` inteira reaparece em `b+1`, a taxa de sobrevivência é
identicamente 1 e a projeção vira o deslocamento puro da última medida. Ela
acerta na mosca **sem ter previsto nada**. E, pior, o baseline (repetir a
última medida) erra, então o método coorte "ganhava" com folga em todas as
células. A conclusão do artigo era reproduzida pelos motivos errados.

A correção é aplicar o mesmo filtro que o resto do pipeline já usava:

> "we regarded that a contributor left the project when he/she did not give any
> contribution for more than three months"
> IEICE16 seção 3.1

`src/pyramid/projection.py` agora filtra `snaps["active"]` antes de montar as
bandas, alinhando a projeção com `metrics.py` e `plots.py`. `tests/test_projection.py`
trava o comportamento por dois lados: `test_populacao_imortal_e_projetada_sem_erro`
fixa a aritmética que produz o acerto falso, e
`test_checkpoint_abre_na_ordem_de_grandeza_do_artigo` reprova qualquer ABRE fora
da faixa publicada. Teria falhado com 0.006.

### 12.2 O que fecha e o que não fecha

Com o filtro correto, `All types / all`:

| | cohort | baseline |
|---|---|---|
| IEICE16 Tabela 3 | 0.4000 | 0.6000 |
| replicação | 0.4208 | 0.5000 |

O `cohort` fica a ~5% do publicado. Algumas células batem de forma quase
literal (Type C / non-coding sai **0.6723 / 1.0000** contra **0.6711 / 1.0000**
do artigo), mas isso é coincidência de amostra pequena. Não conta como
validação: outras divergem bem mais, e duas invertem o sinal da comparação
(ver 12.3).

A conclusão central da seção 4 se sustenta: no agregado, a projeção por coorte erra
menos que o baseline (0.4208 < 0.5000, Wilcoxon p = 0.0073, contra p < 0.00001
no artigo). É o único predicado que `test_checkpoint_coorte_bate_o_baseline_no_agregado`
exige, justamente por não depender do dataset específico.

### 12.3 Divergências que permanecem, não corrigidas

**(a) 34 projetos elegíveis, contra 36 do artigo.** O artigo usa "36 projects that have more
than 100 contributors". Aplicando o corte sobre contribuidores *ativos* no
snapshot base (2013-03-31) chegamos a 34; dois projetos ficam na fronteira dos
100. Não forçamos o número: mexer no corte para chegar a 36 seria ajustar o
método ao resultado. `test_checkpoint_projetos_elegiveis_perto_dos_36` trava 34
para que a contagem não deslize em silêncio.

**(b) `non-coding` inverte o sinal.** No agregado o artigo tem cohort 0.5000 <
baseline 0.6667; nós temos 0.5804 > 0.5000, com Wilcoxon p = 0.1145 (não
significativo). É a única das quatro categorias que anda para o lado errado.

**(c) curto vs. longo prazo inverte.** IEICE16 seção 4 reporta short-term 0.4055 pior
que long-term 0.3333 (p = 0.0460). Nós obtemos short 0.3363 e long 0.4816
(p = 0.1768, n = 135/200): ordem trocada e sem significância. A suspeita é que nossa cauda
longa seja rala demais: com a janela de 2010-2013 e 34 projetos, as bandas
acima de ~4 anos têm poucos contribuintes por coorte, e o ABRE de contagens
pequenas é dominado por ruído de ±1 pessoa. Não investigado a fundo.

**(d) 195 coortes sem denominador (tratado, ver 12.4).**

**Leitura honesta do conjunto:** a mecânica da seção 4 está reproduzida e a tese
central se sustenta, mas (b) e (c) são resultados do artigo que a replicação **não**
reproduz. O dataset não é o mesmo (34 projetos contra 36, coortes diferentes),
o que torna a comparação célula a célula pouco conclusiva nos dois sentidos,
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
  195 células, e o alvo tem gente de verdade em **73.8%** delas.

O ponto: `SR = 0` é uma previsão de extinção. Cravar 0
onde não há denominador afirma "esta coorte vai desaparecer" em 195 lugares
onde o dado não diz nada, e erra em três de cada quatro. O erro é sistemático
numa direção só: infla o ABRE do método coorte e favorece a baseline de graça.
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
projeto a taxa é plana** (5.1 a 6.5) e a fração de alvo povoado idem (69-82%).
Não há concentração em tipo nenhum: a hipótese de que as órfãs explicariam o
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
chegou às medianas: as duas rotas descartavam as mesmas 195 coortes. O que
muda é o registro: 182 linhas que sumiam em silêncio agora existem com
`abre_cohort = nan`, auditáveis. **Isso desqualifica as órfãs como explicação
para 12.3(b) e 12.3(c)**: a inversão do `non-coding` e a de curto/longo prazo
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

| célula | artigo | replicação |
|---|---|---|
| A / all / baseline | 0.5000 | 0.5000 |
| B / moved / baseline | 0.5000 | 0.5000 |
| B / all / cohort | 0.5000 | 0.5000 |
| C / non_coding / cohort | 0.6711 | 0.6723 |
| C / non_coding / baseline | 1.0000 | 1.0000 |
| C / all / baseline | 0.6667 | 0.6607 |
| All types / moved / baseline | 0.5000 | 0.5000 |

Quatro das sete são o valor 0.5000, mediana de coortes que caem em razões de
inteiros pequenos. Casar em 0.5000 é fraco como evidência: é o valor mais
provável de sair por acaso nesse regime. As duas células de C/non_coding e a
de C/all são as únicas coincidências não triviais, e a seção 12.2 já as
classificou como amostra pequena, insuficiente para valer como validação.

**Direção (cohort < baseline?) concorda em 14 de 20 pares.** Das 6 que
discordam, 4 são empate exato na replicação (`c = b`, todas em 0.5000): B/moved,
B/all, C/moved, e o par de B/non_coding. Empate é resolução insuficiente.
Chamar isso de inversão superestimaria o sinal, porque os dois lados
simplesmente não se separaram. As inversões reais, com o cohort de fato pior
que a baseline, são **non_coding em B e no agregado**, e **D/moved**. É
exatamente o 12.3(b), agora localizado: o problema do `non-coding` está
concentrado no Type B (19 dos 34 projetos) e daí sobe para o agregado.

Conclusão operacional: a Tabela 3 **não** é reproduzida célula a célula, e não
deve ser apresentada como tal. O que se sustenta é o predicado agregado da seção 4
(cohort bate baseline, 0.4208 < 0.5000, p = 0.0073) e a direção em 14/20 pares.
`test_checkpoint_abre_na_ordem_de_grandeza_do_artigo` trava a faixa; nenhum
teste trava célula individual, de propósito.

---

## 13. jekyll em 2011: o checkpoint da Fig.2 é 4/5 (aberto)

**Como apareceu.** O `pyramid validate` expôs o caso; nenhum teste dedicado
cobria esse quinto projeto ainda. A seção 9 fechou a Fig.2 com os quatro
projetos que a *legenda* nomeia, um por quadrante, e os dois testes de
checkpoint travam exatamente esses quatro. Mas o
ESEM14 nomeia um quinto projeto no **corpo do texto**, na discussão da Fig.3
(p. 5, coluna 2):

> "Finally, we examine the changes of the jekyll's software population pyramids,
> which was **also a terminal project in 2011**."

Esse "also" liga jekyll aos projetos terminais da Fig.2. É um rótulo publicado,
verificável, e a replicação erra:

| ano | magnetismo | mediana | stickiness | mediana | quadrante |
|---|---|---|---|---|---|
| 2010 | 0.008734 | 0.011827 | 0.1034 | 0.2578 | **terminal** |
| 2011 | 0.009960 | 0.007284 | 0.0519 | 0.1928 | **floating** (artigo: terminal) |
| 2012 | 0.007741 | 0.007117 | 0.1975 | 0.1548 | attractive |
| 2013 | 0.016609 | n/a | n/a | n/a | não classificado (seção 11) |

**Onde exatamente erra: só no eixo do magnetismo.** Na stickiness jekyll é o
5º menor entre 75 elegíveis (0.0519 contra mediana 0.1928). É terminal com
folga enorme nesse eixo. No magnetismo fica no posto 47 de 75, com a mediana no
posto 38: nove posições acima do corte, dentro de uma faixa densa
(0.0094-0.0110 cobre os postos 43-51). Em contagem bruta: jekyll teve 67
novatos em 2011 sobre 6727 novatos do dataset inteiro; para cair em terminal
precisaria de **≤ 49**. São 18 novatos de excesso, ~27%. Não é empate na
fronteira, e não vale tratar como ruído de arredondamento.

**Contrafactual testado e descartado: ancoragem em junho.** Os painéis da Fig.3
são rotulados 2010/06 … 2013/06, então "2011" podia significar a janela
jul/2010-jun/2011 em vez do ano civil. Reprocessei o estágio inteiro com o ano
deslocado seis meses (`/tmp/jun_anchor.py`, ano fiscal jul..jun):

```
DATASET_DIR=$DATASET_DIR .venv/bin/python /tmp/jun_anchor.py
  clojure        stagnant    ok
  homebrew       attractive  ok
  paperclip      floating    ok
  jekyll         floating    MISS (esperado terminal)
  blueprint-css  nan         MISS (esperado terminal; perde elegibilidade)
```

A ancoragem em junho piora o checkpoint de 4/5 para 3/5. Não conserta jekyll e
ainda derruba blueprint-css abaixo do mínimo de devs ativos. O ano civil é a
leitura certa, coerente com `checkpoints.yaml`, que registra a Fig.2 como
snapshot de dez/2011. **A hipótese da janela está descartada; o desvio de
jekyll é real.**

**O que isto provavelmente é.** A direção do erro coincide com a da seção 3.1: lá
sobra projeto no Tipo A e falta no Tipo C, isto é, a replicação **classifica
novato demais**. Aqui o magnetismo (que é literalmente uma contagem de novatos
sobre o total) sai alto demais para jekyll, e é exatamente isso que o empurra
de terminal para floating. São duas métricas independentes apontando o mesmo
viés na mesma direção, o que é evidência melhor do que qualquer uma das duas
sozinha. jekyll é o caso onde esse viés mais aparece porque foi o projeto que
mais cresceu em contribuidores no período (14 → 40 → 29 → 77 → 81 devs/ano):
quanto mais entrante, mais exposto ao critério de "primeira aparição".

Consistente com isso, a **trajetória** da replicação reproduz a narrativa do artigo
adiantada em um ano: terminal → (cresce) → attractive, com o artigo pondo
"terminal" em 2011 e a replicação em 2010. Note que os outros quatro projetos
batem no ano civil de 2011 sem deslocamento nenhum. O desvio é específico de
jekyll, sem offset global de um ano.

**O que foi mudado no repositório:** nada no cálculo. Corrigir isto exige
acertar a definição de novato, que é a seção 3.1 em aberto, e mexer nela para
consertar um projeto seria ajustar o método ao gabarito. O que muda é a
contabilidade honesta:

- o título da seção 9 passa a dizer 4/5, com ponteiro para cá;
- `checkpoints.yaml` ganha jekyll/2011 sob `attractiveness`, e o `validate`
  reporta a falha em vez de ignorá-la;
- `test_checkpoint_jekyll_2011_diverge` trava o valor **medido** (floating), com
  a referência a esta seção, independente do rótulo do artigo. Se um refactor
  futuro fizer jekyll virar terminal, o teste quebra e obriga a reler esta
  seção, que é o comportamento certo, porque nesse dia o checkpoint vira 5/5 e
  este item fecha.

**Fica aberto.** Não há aproximação a fazer aqui: ou a definição de novato muda
e os cinco batem, ou a seção 3.1 permanece como a explicação comum dos dois desvios.

---

## 14. `scope_label` dependia de ordem de chamada (corrigido, sem efeito em número)

### Sintoma

`pyramid validate` reportava `types.examples.*` com "obtido" = `25875`, `78835`,
… (o próprio id do escopo) em vez de `jquery/jquery`, `divio/django-cms`. A
legenda da Fig.5 tinha o mesmo problema quando a figura era gerada sozinha
(`pyramid plot --figure fig5`), com os pontos rotulados por número.

### Causa raiz

`MSR14Source.list_scopes()` construía o dicionário `_labels` como efeito colateral
e `scope_label()` só lia esse dicionário. Quem chamasse `scope_label` sem ter
passado por `list_scopes()` **na mesma instância** caía no `.get(id, str(id))` e
recebia o id de volta. Os estágios do pipeline (`extract`, `classify`,
`snapshots`, `attractiveness`) chamam `list_scopes()` logo no início do `run()`,
então nunca viram o defeito; `metrics.table()` (usada por `validate` e pelo
`plot --figure fig5` fora do pipeline) não chama.

Este é o modo de falha ruim: sem exceção, sem log, só um rótulo plausível.

### Correção

`scope_label()` passou a carregar o mapa sob demanda (`_load_labels()`), com o
cache preservado. `list_scopes()` reusa o mesmo carregamento. Id que realmente
não é raiz continua virando string, e aí o fallback é a resposta certa.

```
grep -n "def scope_label" -A 16 src/pyramid/sources/msr14.py
pyramid validate --report output/validation_report.md   # types.examples.* → nomes
pyramid plot --figure fig5                              # legenda com nomes
```

### Alcance

Nenhum número muda. `type`, `ccr`, `ncr`, quadrante e todas as tabelas são
calculados por `scope_id`; o rótulo é cosmético e entra só na apresentação. O
que muda é que os oito `types.examples.*` do relatório passam a ser verificáveis
por leitura: antes eles batiam por serem comparados contra o gabarito por id,
e o "obtido" impresso não dizia nada a quem lesse.

### Guarda contra reincidência

`validate` compara `types.examples.<id>` contra o tipo (A-D) do artigo e imprime
o rótulo na coluna de referência; se o rótulo regredir para o id, o relatório
mostra a regressão na cara. A regra geral que isto reforça (já aplicada ao
manifesto) é que **artefato nenhum guarda `repr` de objeto ou id cru onde um
nome estável é o esperado**.

## 15. Novato é do dataset (seção 3.1): hipótese testada e descartada

A seção 13 fechou com uma suspeita nomeada: a replicação classificaria "novato demais",
e jekyll/2011 cairia em `attractive` porque o magnetismo sai alto. A única
alavanca real por trás disso é a definição de novato. Ou o numerador do
magnetismo conta *quem estreou no dataset*, ou conta *quem estreou naquele
projeto*. As duas leituras dão o mesmo número na Fig.1 do MSR'14 e divergem em
todo projeto que recebe veterano vindo de outro repositório.

### O que o artigo diz

MSR'14 seção 2, imediatamente antes da definição (p.1, coluna 2):

> However, the definition cannot be applied directly to open source projects,
> **where a contributor can contribute to several projects at the same time.**
> Therefore, we expand original definition to apply to open source projects as
> follows: [...] we calculate the magnetism of a project as **the proportion of
> contributors who made their first contribution in the time period under study
> who contribute to a given project.**

A frase resolve o caso sozinha, e resolve duas vezes:

1. `first contribution in the time period under study` qualifica a **pessoa**;
   `who contribute to a given project` é o filtro de quem, dentre esses,
   conta para o projeto. O projeto entra apenas como recorte sobre essa população.
2. O motivo declarado da expansão é justamente o contribuidor multi-projeto.
   Ler "novato" como "primeira aparição neste repositório" desfaz a expansão:
   voltaria a tratar cada projeto como um mundo fechado, que é a leitura que
   os autores dizem não poder aplicar.

É o que `src/pyramid/attractiveness.py` já faz: o denominador é global (todos
os novatos do ano no dataset) e o numerador é a interseção com o projeto.

```
grep -n "first_year\|newcomers_here\|newcomers_total" -B 2 -A 6 src/pyramid/attractiveness.py
sed -n '78,93p' /tmp/msr14.txt      # pdftotext -layout docs/replicacao/papers/MSR14.pdf
```

### O denominador é sobre a população certa

`activity()` cobre os 90 escopos do dump: a mesma população dos 90 projetos do
MSR'14 (seção 1.1.1). Se um parquet faltasse, o denominador encolheria em silêncio,
por isso a função levanta `FileNotFoundError` em vez de rodar com 89. E as
triplas são únicas, então `newcomers_here` não infla por linha repetida:

```
pyramid attractiveness   # 36335 linhas, 36335 chaves (scope_id, contributor_id, year)
```

### Contrafactual (rodado, não adotado)

Variante **P** = "novato é quem aparece pela primeira vez *neste* projeto",
comparada contra a Tabela 2 do MSR'14 (12 projetos × 8 anos, 55 células com
rótulo publicado). Âncora primeiro: a variante **G** reimplementada bate com
`attractiveness.annual()` em **96/96** células: sem isso a comparação arriscaria
comparar duas reimplementações em vez de duas definições.

| variante | acertos | falhas |
|---|---|---|
| **G**: novato do dataset (atual) | **48/55 (87%)** | 7 |
| P: novato do projeto | 45/55 (82%) | 10 |

P **não corrige nenhuma** das 7 falhas de G. Quebra 3 células que G acertava
(2008 `scala`, 2008 `django-debug-toolbar`, 2008 `jekyll`) e mantém as outras
7 idênticas, jekyll/2011 inclusive.

```
DATASET_DIR=$DATASET_DIR .venv/bin/python scripts/contrafactual_novato.py
```

### A direção do efeito enterra a hipótese da seção 13

P conta **mais** novatos:

```
pares (projeto,pessoa,ano) nos 12 projetos x 8 anos: 3882
novatos sob G: 2906
novatos sob P: 3047  (+4.9%)
```

Se a replicação classifica novato demais, a variante alternativa classificaria
~5% a mais ainda. Não existe leitura de "novato" que empurre jekyll/2011 na
direção do artigo: o eixo está esgotado. A seção 13 continua aberta, mas sem este
suspeito: o resíduo de jekyll não vem da definição de novato, e a próxima
hipótese tem que atacar outra coisa (janela de atividade ou o corte do sticky).

### Guarda contra reincidência

Dois testes em `tests/test_attractiveness.py`:

- `test_exemplo_figura1_do_msr14`: a aritmética publicada (magnetismo 2/3 e
  1/3, sticky 1/1; guarda contra o valor errado 2/1). Trava a armadilha do sticky, mas **não** separa
  G de P: no exemplo dos autores ninguém é veterano do dataset e estreante em
  um projeto.
- `test_novato_e_do_dataset_nao_do_projeto`: separa. Veterano troca de
  projeto: o projeto novo tem magnetismo **0** (1/2 sob P). Sob P este teste falha.

```
.venv/bin/python -m pytest tests/test_attractiveness.py -q   # 11 passed
```

## 16. As 7 células residuais da Tabela 2 do MSR'14 (48/55 = 87%)

A Tabela 2 do MSR'14 virou instrumento permanente de validação (seção 11.1): 12
projetos × 8 anos, 55 células com quadrante publicado, mais as células `-`
(sem atividade) e `*` (devs ≤ 10) que testam a elegibilidade. A replicação bate
**48/55**, e a estrutura `-`/`*` bate **integralmente**. Esta seção fecha as 7
restantes, cada uma com causa nomeada e medida, nenhuma com correção de
conveniência.

### Antes: as duas ambiguidades do limiar, decididas pela própria tabela

O artigo diz apenas "we use the median magnet and sticky values as the
thresholds" (MSR'14 seção 2, p.3). Isso deixa duas coisas em aberto, e as duas
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
| **`>` estrito: "higher than the median" (adotada)** | **48/55** |
| `>=` (empate conta como alto) | 46/55 |

A margem de (a) sobre as alternativas é grande demais para ser sorte, e as duas
escolhas já estavam no código antes deste teste: a tabela apenas confirmou o
que já existia. O `>=` merece nota: ele **corrige** 2 das 7 falhas (xbmc/2007 e
xbmc/2009) e **quebra 4 células que hoje batem** (2005 `rails`, 2005 `xbmc`,
2007 `django`, 2004 `scala`). São 6 empates exatos na tabela, 4 pedindo `>` e
2 pedindo `>=`: a regra de empate do artigo é **irrecuperável por engenharia
reversa**, porque a própria Tabela 2 é inconsistente nela. Fica o `>`: leitura
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

*(scala/2010 fica fora: é ausência de dado. Detalhe abaixo.)*

Das 6, **4 estão a ≤ 5,1% da mediana** e 2 estão *exatamente em cima* dela:

| ano | projeto | artigo | replicação | magnet vs mediana | sticky vs mediana | margem |
|---|---|---|---|---|---|---|
| 2007 | `xbmc/xbmc` | attractive | floating | +83,3% | **+0,0%** | **0,0%** |
| 2009 | `xbmc/xbmc` | attractive | stagnant | **+0,0%** | +198,3% | **0,0%** |
| 2010 | `chriseppstein/compass` | floating | terminal | −4,6% | −40,3% | 4,6% |
| 2010 | `jquery/jquery` | floating | attractive | +143,1% | +5,1% | 5,1% |
| 2011 | `mojombo/jekyll` | terminal | floating | +36,7% | −73,1% | 36,7% |
| 2011 | `django/django` | attractive | stagnant | **−91,8%** | +335,7% | 91,8% |

As duas de margem 0,0% são o projeto que *define* a mediana daquele ano naquele
eixo: sob `>` estrito o projeto mediano nunca é "alto" no eixo em que ele é a
mediana. Isso é o mesmo empate que o artigo resolve para o outro lado em 4
células e para este lado em 2. Nas células longe da
linha (margem > 10%), o acordo é **de 37/37 fora as duas de baixo**: o método
reproduz; o que não reproduz é o desempate.

### scala/2010: buraco de 18 meses no dump

Único caso em que a replicação não produz rótulo nenhum (`-`, "sem atividade")
contra um `floating` publicado. A causa está no dado bruto, antes de qualquer
código nosso:

```sql
SELECT DATE_FORMAT(created_at,'%Y-%m') m, COUNT(*) FROM commits
WHERE project_id=107534 AND created_at BETWEEN '2009-06-01' AND '2011-06-30' GROUP BY 1;
-- ... 2009-10: 221 | 2009-11: 87 | 2011-06: 1
```

Nenhum commit entre **2009-12 e 2011-05**, e o buraco não é do recorte de
escopo: incluindo os **466 forks** de scala (`project_commits`, escopo família)
o ano de 2010 continua com zero. Não é falha global do dump: 2010 tem 69.247
commits em 828 projetos. É específico do projeto, e casa com `projects.created_at
= 2011-12-01` para `scala/scala`: o que existe antes disso é histórico
importado durante a migração. Efeito colateral coerente: o
sticky de scala/2009 sai **0,000** (nenhum dos 25 devs de 2009 aparece em 2010),
que é o que empurra a célula de 2009 para `terminal`, e essa o artigo também
diz `terminal`.

### django/2011: o repositório ainda não estava no GitHub

É a maior margem da tabela (−91,8%), longe da linha da mediana ao contrário
dos casos anteriores. O magnetismo
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
de committers, que é o que a importação preserva. A replicação lê o dado que está
lá. Por que o MSR'14 lê `attractive` na mesma célula do mesmo dump é uma
pergunta sem resposta a partir dos artefatos publicados: não há leitura de
magnetismo que transforme 4 novatos em 50.

Vale para as duas: os cortes de cobertura pré-migração não são ruído aleatório,
são **censura à esquerda por projeto**, a mesma família de problema da seção 11
(truncamento à direita). A diferença é que aqui a data de corte é uma por
projeto; na seção 11 a data de corte é única para o dataset inteiro. A Tabela 2
do MSR'14 publica rótulos para anos que caem dentro dessa censura em pelo menos
2 dos 12 projetos.

### O que fica declarado

As 7 continuam impressas pelo `pyramid validate`, com rótulo `conhecida` e
ponteiro para cá, e se qualquer uma voltar a bater, o comando falha por
`OBSOLETA` (seção 14). Nenhuma foi silenciada, e o `msr14.tab2.concordancia`
(≥ 80%) continua sendo o portão que trava regressão no estágio.

## 17. blueprint-css: pirâmide vazia em 4 snapshots vem do dado

Ao gerar as figuras notei que **blueprint-css (`project.id` 101472)** aparece
com pouquíssimos ou nenhum contribuidor ativo em vários snapshots, enquanto o
MSR'14 comenta sobre 2012 que "the current contributors of this project are
different from the previous contributors". Duas hipóteses concorriam, e as duas
tinham consequência oposta: **(a)** bug de "só pega o último" no
`classify`/`snapshots`: a construção de spans colapsando a história de cada
contribuidor no evento mais recente; ou **(b)** atividade real esparsa. É (b),
e a confirmação veio de fora do dump.

### O sintoma: estoque cresce, fluxo vai a zero

```
uv run python -c "
import pandas as pd
s=pd.read_parquet('output/snapshots/101472.parquet')
print(s.groupby('snapshot').agg(na_piramide=('contributor_id','nunique'), ativos=('active','sum')).to_string())"
```

| snapshot | na_piramide | ativos | | snapshot | na_piramide | ativos |
|---|---|---|---|---|---|---|
| 2010-03-31 | 22 | 1 | | 2012-03-31 | 38 | 2 |
| 2010-06-30 | 22 | 1 | | 2012-06-30 | 38 | **0** |
| 2010-09-30 | 22 | 2 | | 2012-09-30 | 38 | **0** |
| 2010-12-31 | 26 | 4 | | 2012-12-31 | 39 | 1 |
| 2011-03-31 | 26 | 1 | | 2013-03-31 | 39 | **0** |
| 2011-06-30 | 30 | 6 | | 2013-06-30 | 39 | **0** |
| 2011-09-30 | 35 | 7 | | 2013-09-30 | 40 | 1 |
| 2011-12-31 | 36 | 1 | | | | |

`na_piramide` é **estoque** e cresce monotonicamente (22 → 40): ninguém sai,
porque a coorte de um contribuidor é o passado dele. `ativos` é **fluxo**
(`active` = contribuiu nos 3 meses antes de T, `snapshots.py:163`). Como
`plots.py:94` filtra `cut = cut[cut["active"]]` (o mesmo filtro que o
`metrics` usa em CCR/NCR), a figura renderizada em 2012-06-30, 2012-09-30,
2013-03-31 e 2013-06-30 é uma **pirâmide vazia**. Isso é comportamento
declarado; o que estava em aberto era se os zeros eram reais.

### O dado bruto já responde: trimestres inteiros sem evento

```
uv run python -c "
import pandas as pd
e=pd.read_parquet('output/extract/101472.parquet')
e['q']=e.timestamp.dt.to_period('Q')
print(e.groupby('q').agg(eventos=('contributor_id','size'), devs=('contributor_id','nunique')).to_string())"
```

Os quatro snapshots com `ativos=0` caem exatamente sobre os quatro trimestres
sem **nenhum** evento no dump: 2012Q2, 2012Q3, 2013Q1 e 2013Q2. Não há evento
sendo perdido na agregação: não há evento. Dos 514 eventos do projeto, 337
(65%) estão em 2007-2008; depois de 2011Q3 sobram quatro eventos isolados
(2011Q4, 2012Q1 com dois, 2012Q4, 2013Q3).

### Ground truth externo: o repo é o certo e a atividade acabou mesmo

O passo que fecha o caso é não confiar no dump para auditar o dump. Primeiro,
descartar renomeação/transferência (a suspeita do caso `symfony`/`xphere-forks`,
seção 10):

```
curl -sSL -w '\nHTTP %{http_code} | url_efetiva: %{url_effective}\n' \
  'https://api.github.com/repos/joshuaclayton/blueprint-css'
```

`HTTP 200`, `url_effective` idêntica à pedida (a API redirige 301 quando houve
rename ou transfer; não houve), `full_name` = `joshuaclayton/blueprint-css`,
`fork: false`, `archived: true`, 5283 estrelas. **Repositório único, correto,
nunca movido.** O `created_at` no GitHub é `2008-08-07`, posterior ao nosso
primeiro evento (`2007-08-29`): história git importada de antes do GitHub
existir, o que é consistente e não indica dado corrompido.

Depois, os commits reais do `master` no período, paginando a API com
`since=2009-01-01T00:00:00Z&until=2013-10-01T00:00:00Z&per_page=100`:

| trimestre | eventos no nosso extract | commits reais (API) | leitura |
|---|---|---|---|
| 2009Q1 | 13 | 13 | idêntico |
| 2009Q2 | 18 | 18 | idêntico |
| 2009Q3 | 9 | 9 | idêntico |
| 2010Q1 | 5 | 5 | idêntico |
| 2010Q2 | 1 | 1 | idêntico |
| 2010Q3 | 26 | 26 | idêntico |
| 2010Q4 | 6 | 1 | +5 issues/PRs |
| 2011Q2 | 25 | 17 | +8 issues/PRs |
| 2011Q3 | 18 | **0** | só issues/PRs |
| 2011Q4 … 2013Q3 | 1, 2, 1, 1 | **0, 0, 0, 0** | só issues/PRs |

Seis trimestres batem **commit a commit** com a API, o que valida a extração.
E a API não tem **nenhum commit no `master` depois de 2011Q2** até out/2013:
`TOTAL 90` commits em todo 2009-01 → 2013-10. O projeto parou de ser
desenvolvido em meados de 2011; o que sobra em 2012-2013 são issues e PRs
avulsos que o dump registra e que a API de commits, por construção, não vê.
A diferença entre as colunas é o `ActivityDataSource`
contando mais tipos de evento que só commits (seção 1).

### O que isso resolve

A hipótese (a) está descartada: se fosse "só pega o último", os trimestres
densos de 2009-2010 também viriam achatados, e eles batem 6/6 com o ground
truth externo. As pirâmides quase vazias de blueprint-css são **retrato fiel de
um projeto morto**, e o comentário do MSR'14 sobre 2012 é compatível: com 38
pessoas em estoque e 1-2 ativas, a rotatividade é total por aritmética: os
"current contributors" de 2012 são necessariamente outros que os de 2007-2009.

Nenhuma mudança de código. O caso entra como **precedente de método**: quando
um número do dump parecer degenerado, a checagem é contra fonte externa
(API do GitHub), não contra outra tabela do mesmo dump.

### Auditoria do caminho de plotagem: ninguém some entre o dado e a barra

O parágrafo acima só fecha se `plots.py` de fato desenhar **todo** mundo que
`snapshots.py` marcou `active=True`. Um filtro extra, um `groupby` que colapsa,
ou uma escala que corta o topo produziriam a mesma figura vazia por motivo
errado. Auditei `plots.pyramid_frame` (`plots.py:84-107`) linha a linha e testei
o invariante `count(active=True) == soma das barras desenhadas`.

**Leitura do código.** Há exatamente um filtro, `cut = cut[cut["active"]]`
(`plots.py:94`), que é o declarado. Os outros quatro pontos onde dado poderia
sumir em silêncio não somem:

- `pivot_table(..., aggfunc="size")` (`plots.py:99`) tem `dropna=True` por
  default e descartaria categoria ausente, mas o `.reindex(columns=CATEGORIES,
  fill_value=0)` logo abaixo repõe as três colunas, e não há `NaN` em `band`
  nem em `category` para linha nenhuma ser descartada na entrada.
- `aggfunc="size"` conta **linhas** em vez de valores únicos, o que seria
  inflação se houvesse contribuidor repetido no mesmo snapshot. Não há:
  `duplicated(['snapshot', 'contributor_id']).sum() == 0`.
- `piv.reindex(range(0, max+1), fill_value=0)` (`plots.py:106`) **acrescenta**
  bandas vazias no meio da pirâmide, não remove nenhuma.
- `xmax`/`ymax` (`plots.py:254-258`) são o **máximo da linha inteira** de
  painéis, logo sempre ≥ o máximo do painel individual: a escala comum da Fig.3
  nunca corta uma barra ou uma banda alta fora do quadro.

**Teste do invariante.** Comparando o número de `active=True` no parquet de
snapshots com a soma efetivamente desenhada, em todo o dataset e não só no
blueprint-css:

```
uv run python -c "
import pandas as pd, glob, os
from pyramid import plots, snapshots
falhas=[]; n=0; maxv=0
for p in sorted(glob.glob('output/snapshots/*.parquet')):
    pid=os.path.basename(p)[:-8]; s=pd.read_parquet(p)
    if s.empty: continue
    for t in sorted(s.snapshot.unique()):
        esperado=int(s[s.snapshot==t]['active'].sum())
        f=plots.pyramid_frame(s, pd.Timestamp(t))
        des=0 if f.empty else int(f[snapshots.CATEGORIES].to_numpy().sum())
        n+=1; maxv=max(maxv,esperado)
        if esperado!=des: falhas.append((pid,str(t)[:10],esperado,des))
print('pares checados:', n, '| divergencias:', len(falhas), '| maior populacao:', maxv)"
```

`pares checados: 1178 | divergencias: 0 | maior populacao: 1844`.

Bate nos 15 snapshots do blueprint-css (incluindo os quatro de zero e o pico de
7 em 2011-09-30) e nos 1178 pares (projeto, snapshot) do dataset inteiro, até
uma pirâmide de 1844 pessoas. **A figura vazia é o dado, confirmado agora nos
dois sentidos:** os zeros são reais (seção acima, contra a API do GitHub) e o
plot não fabrica zero a partir de dado que existe.

> **Revisado pela seção 18.** Tudo acima continua valendo como fato sobre os dados:
> os zeros de `ativos` são reais e a extração bate 6/6 com a API. O que caiu foi
> a conclusão de que a **figura** devia mostrar esses zeros: a Fig.2 do ESEM14
> desenha o **estoque**, e é a coluna `na_piramide` desta mesma tabela (36 no
> estoque de dez/2011, contra 1 no fluxo `ativos`) que o artigo plota. No artigo,
> a pirâmide de blueprint-css é um corpo velho sobre uma base vazia: essa é a
> leitura "terminal".

---

## 18. A pirâmide do artigo é estoque (corrigido)

`plots.pyramid_frame` filtrava `cut = cut[cut["active"]]`, alinhando a figura à
população que o `metrics` usa em CCR/NCR. O raciocínio era defensável ("a figura
e a tabela têm de contar a mesma gente"), mas está errado quanto ao que o ESEM14
desenha. **A Fig.2 é um retrato de estoque**: todo mundo que já contribuiu até o
snapshot, posicionado pela idade acumulada que alcançou. Quem entrou em 2007 e
parou em 2010 continua na figura de dez/2011.

Isto saiu de duas leituras independentes da
Fig.2, cada uma capaz de derrubar a hipótese sozinha, e as duas apontando para o
mesmo lado.

### Leitura 1: a barra de ~750 do homebrew está na banda errada para `active`

No painel (a), a barra que encosta em ~750 do eixo x não está na base: está
entre metade do segundo e metade do terceiro quarter de idade, isto é, na
**banda 1** (3-6 meses). Contagem nossa em `2011-12-31`, `project.id` 79163:

| banda | `active` (esq/dir) | estoque (esq/dir) |
|---|---|---|
| 0 | 570 / 375 | 570 / 375 |
| **1** | **73** / 43 | **734** / 453 |
| 2 | 25 / 74 | 369 / 344 |

Sob `active` a banda 1 tem 73 pessoas, duas ordens de grandeza abaixo do que a
figura mostra, e a pirâmide vira um pico solitário na base. Sob estoque tem
**734**, que encosta num eixo de 750. A banda 0 é idêntica nos dois regimes, e
isso não é coincidência: quem entrou nos últimos 3 meses é ativo por definição
(o evento de entrada está dentro da janela de `inactivity_months`). Ou seja, o
filtro só começa a morder a partir da banda 1, exatamente onde a discrepância
aparecia.

### Leitura 2: blueprint-css tem corpo de pirâmide na figura

Sob `active`, blueprint-css em dez/2011 é **1 pessoa, 1 barra** (seção 17). Na Fig.2
ele aparece com várias barras, massa entre 2 e 4 anos de idade e base vazia.
Sob estoque são **36 pessoas** em 18 bandas, barra máxima 5. Não há como
confundir os dois desenhos, e só o segundo existe no artigo.

### Efeito nos quatro painéis (dez/2011)

| projeto | `active` total / maior barra | estoque total / maior barra |
|---|---|---|
| mxcl/homebrew | 1448 / 570 | 4801 / **734** |
| thoughtbot/paperclip | 184 / 105 | 889 / 113 |
| clojure/clojure | 21 / 8 | 96 / 18 |
| joshuaclayton/blueprint-css | 1 / 1 | 36 / 5 |

### Um terceiro sintoma que era o mesmo bug

A queixa de que a figura mostrava "um bloco inteiro por ano" em vez de quatro
barras não era problema de plotagem: `band_months: 3` sempre gerou uma barra por
trimestre e `draw_pyramid` sempre desenhou uma barra por banda (o eixo y só
*rotula* de ano em ano, `per_year = 12/bm`). Sob `active` o homebrew era
570-73-25-14 no primeiro ano: a primeira barra engolia visualmente as outras
três. Sob estoque são 570-734-369-207 e as quatro aparecem. Os três sintomas
tinham uma causa só.

### O que mudou, e o que deliberadamente não mudou

`config/settings.yaml` ganhou `plots.pyramid_population` (AMBIGUIDADE 5), default
`stock`, com `active` preservado para reproduzir a leitura antiga. **`metrics`
não foi tocado**: ele filtra `active` por conta própria (`metrics.py:111`) e
continua batendo 48/55 na Tabela 2 do MSR'14 (seção 16). A separação é a mesma que o
`CLAUDE.md` já aplicava ao 2013 right-censored (**forma é estoque, fluxo é
ativo**), agora com confirmação empírica vinda da figura.

`pytest -q`: 110 passed (5 novos em `tests/test_plots.py`, que prendem os dois
regimes, a igualdade da banda 0 e o default `stock` do settings versionado).
`pyramid validate`: 167 checks, 102 ok, 65 conhecidas:
**idêntico ao estado anterior à mudança**, nenhuma divergência nova, o que era o
teste de que a troca não vaza para as métricas.

Fica em aberto o valor exato do eixo do artigo: 734 contra uma leitura visual de
"até 750" é compatível (o eixo é ≥ a maior barra), mas não é igualdade
verificada. Não há tabela numérica da Fig.2 no ESEM14 para conferir contra.

## 19. Sobrecontagem da Fig.2: o mecanismo é o contribuidor de evento único

Investigação aberta pelo pedido de "ver o quanto a regra precisa mexer para
esses caras sumirem" (buraco do blueprint-css) e por "clojure nunca bate o
número 10". Tudo abaixo é medido em `2011-12-31` (a data da Fig.2, ver seção 18),
por `project.id`, com `taxonomy.variant: prose` e `band_days: 90`.

### 19.1 O mecanismo

Idade é tempo de calendário desde o primeiro evento (`age_basis:
calendar_tenure`) e **não para de crescer quando a pessoa some**. Quem fez um
único commit e nunca voltou continua envelhecendo uma banda a cada trimestre,
migrando para o meio da pirâmide. Na janela de 12 meses, esses contribuidores de
evento único são:

| projeto | pop. (janela 12m) | evento único | % |
|---|---|---|---|
| clojure/clojure | 49 | 22 | 45% |
| joshuaclayton/blueprint-css | 13 | 9 | 69% |

E é exatamente onde a replicação estoura o artigo:

* clojure banda 3 (9-12 meses): nossa 10, artigo 7: **7 dos 10 são de evento
  único** (`age_days == idle_days`, um dia só de atividade, entre jan e mar/2011).
* blueprint-css bandas 1 e 2: nossas 4+4, artigo 1+1: **7 dos 8 são de evento
  único**.

Não há bug de extração nem de plotagem envolvido. A causa é a interação entre
idade de calendário e uma população larga demais.

### 19.2 Corte por número mínimo de eventos: refutado

A tentação era exigir ≥2 eventos para entrar na pirâmide. **Não funciona, e a
própria Fig.2 derruba**: a banda 0 do clojure no artigo tem 8 pessoas, que é
exatamente o que contamos com *todo mundo* dentro; com `nev >= 2` a banda 0 cai
para 4 e o erro total contra o artigo sobe de 18 para 28. Ou seja, o artigo
conta sim quem só apareceu uma vez: o problema é ela
continuar envelhecendo depois de sumir.

| clojure, janela 12m | banda 0..7 | erro vs artigo |
|---|---|---|
| todos | 8, 5, 4, 10, 4, 2, 1, 4 | **18** |
| `nev >= 2` | 4, 2, 1, 4, 4, 2, 1, 4 | 28 |
| `nev >= 3` | 1, 0, 0, 4, 3, 2, 1, 4 | 35 |

### 19.3 Os três regimes de população, lado a lado

Vetor do artigo lido em pixel no painel do clojure (lado coding, banda 0 para
cima): `8, 5, 6, 7, 7, 3, 3, 3, 2, 5, 5`, total ~58.

| projeto | regime | total | maior esq | maior dir | banda 0..3 (dir) |
|---|---|---|---|---|---|
| homebrew | `active` 3m | 1448 | 565 | 368 | 368, 124, 75, 56 |
| homebrew | janela 12m | 3882 | **733** | 451 | 368, 451, 336, 380 |
| homebrew | estoque | 4801 | **733** | 451 | 368, 451, 336, 380 |
| paperclip | `active` 3m | 184 | **103** | 24 | 24, 7, 5, 2 |
| paperclip | janela 12m | 524 | 114 | 36 | 24, 36, 31, 22 |
| paperclip | estoque | 889 | 114 | 36 | 24, 36, 31, 22 |
| clojure | `active` 3m | 21 | 1 | 8 | 8, 1, 0, 2 (erro 37) |
| clojure | janela 12m | 49 | 1 | 10 | 8, 5, 4, 10 (erro **18**) |
| clojure | estoque | 96 | 1 | 16 | 8, 5, 4, 10 (erro 45) |
| blueprint-css | `active` 3m | 1 | 0 | 1 | 1, 0, 0, 0 |
| blueprint-css | janela 12m | 13 | 1 | 4 | 1, 4, 4, 0 |
| blueprint-css | estoque | 36 | 1 | 5 | 1, 4, 4, 0 |

Ticks do artigo (lidos da figura, ver `checkpoints.yaml`): homebrew 750,
paperclip 100, clojure 10, blueprint-css 5.

Duas observações que mudam a discussão da seção 18:

1. **Janela 12m e estoque são idênticos nas bandas 0-3 em todos os quatro
   projetos.** Uma janela de inatividade de 12 meses só consegue matar quem já
   tem idade ≥ 4 bandas. Toda a diferença entre os dois regimes está no
   meio/topo da pirâmide.
2. **Nenhum regime ganha em todo tick, e tick é proxy ruim.** `active` 3m é o
   único que fica dentro do tick do paperclip (103 vs 100) e acerta a maior
   barra do clojure (8), mas esvazia o homebrew (565 contra um eixo de 750) e
   reduz blueprint-css a uma pessoa. Janela 12m encosta no homebrew (733 contra
   750), acerta o total do clojure (49 vs ~58) e a estrutura do blueprint-css,
   mas estoura a banda 3 do clojure (10 vs 7) e passa o tick do paperclip (114
   vs 100). Estoque é o pior contra o clojure (erro 45). Comparar *ticks* mede
   uma barra por painel; a comparação banda a banda contra os pixels (seção 20) é o
   critério que decide, e lá 12 meses ganha nos quatro.

Ordem de aderência à Fig.2 medida no único painel com vetor completo lido
(clojure): **janela 12m (18) > `active` 3m (37) > estoque (45)**.

O estado versionado é o do meio: `pyramid_population: active` (a reversão do
seção 18) **com `pyramid_window_months: 12`**. Vale registrar o que isso quer dizer,
porque a nomenclatura engana: "ativo" na pirâmide não é o mesmo "ativo" das
métricas. `metrics` usa `inactivity_months: 3` (que o MSR14 crava) para CCR/NCR;
a pirâmide usa 12 meses (que a medição da figura escolhe, seção 20). Com snapshot em
fim de ano, "janela de 12 meses" lê-se como *quem contribuiu durante o ano do
snapshot*. A pirâmide anual conta a população do ano. A
linha `active` 3m da tabela acima é só a referência de quanto se perderia
casando as duas janelas: o blueprint-css desaba para uma pessoa.

A queixa que motivou a reversão da seção 18 fica parcialmente resolvida: a barra
máxima do clojure cai de 16 (estoque) para 10, e a banda 3 continua sendo o
resíduo aberto: 10 contra 7, sete deles de evento único (19.1). Não há regra de
população que conserte a banda 3 sem estragar a banda 0, que hoje bate exata.

### 19.4 Resíduo que não é população

As bandas 2 e 3 do clojure divergem em qualquer regime (nossas 4 e 10, artigo 6
e 7). Como bandas 0-3 são invariantes ao regime (19.3, obs. 1), isso **é
questão de idade/banda**. População foi descartada como causa. A soma das duas bate exatamente
(14 = 14), o que é compatível tanto com um deslocamento de fronteira quanto com
erro de leitura em pixel de duas barras vizinhas. Varreduras que não mexeram
nisso, todas com o vetor do artigo como alvo:

* `band_days` ∈ {90, 91, 91.3125, 92}: erro 19, 17, 17, 15. É jitter.
* Banda por trimestre civil (`4*ano+trim` de diferença) em vez de dias: erro 17.
  Com deslocamento de −1 trimestre: 29 (destrói a banda 0, que hoje bate exata).
* Origem da idade no primeiro evento de qualquer tipo em vez de `start_ref`:
  **no-op no clojure**, que não tem nenhum contribuidor `moved`.
* Data do snapshot: varredura em toda a série trimestral × 8 janelas confirma
  `2011-12-31` + 12m como mínimo global (19). A data da Fig.2 está correta.

### 19.5 `age_basis: accumulated_active` fica refutado (AMBIGUIDADE)

Rodando o mesmo painel com idade = soma dos períodos de atividade (descontando
os silêncios), a pirâmide do clojure colapsa na base: banda 0 passa de 8 para 32
na janela de 12m, o topo cai da banda 23 para a 20 e o erro contra o artigo vai
de 18 para 63. O artigo desenha pirâmides altas, com massa até 4-5 anos de
idade; idade acumulada não produz isso em nenhuma variante testada
(janelas 3/6/12/18/24/∞, erro 47..108). **`calendar_tenure` fica como leitura
única**, agora por evidência da figura e não só pela analogia demográfica.

### 19.6 clojure não serve para decidir a taxonomia (AMBIGUIDADE 1)

O clojure praticamente não tem discussão no dump. Em todo 2011: 2.669 commits
contra 27 `issue_comments`, **zero** `issue_events` e **zero**
`pull_request_comments` (o projeto usava JIRA/Assembla, não as issues do
GitHub). Por isso o lado non-coding do painel do clojure é quase vazio na
replicação (1, 0, 1, 1 nas bandas 0-3), e é quase vazio no artigo também, o que é
uma confirmação a mais de que o dump é o mesmo.

Consequência prática: tirar `issue_events` da taxonomia (variante `table1`) não
move um único contribuidor no clojure nem no blueprint-css, e move muito nos
outros dois:

| projeto | pop. estoque `prose` | sem `issue_events` | efeito |
|---|---|---|---|
| homebrew | 4801 | 4419 | −8% (maior barra 733 → 579) |
| paperclip | 889 | 807 | −9% (maior barra 114 → 81) |
| clojure | 96 | 96 | 0 |
| blueprint-css | 36 | 36 | 0 |

Como a maior barra do homebrew sem `issue_events` (579) fica bem abaixo do eixo
de 750 do artigo e com `issue_events` encosta (733), a Fig.2 continua apoiando
a leitura `prose`. Registrado como mais um voto. A decisão da AMBIGUIDADE 1
continua com os Tipos A-D.

## 20. Como a Fig.2 do ESEM14 foi medida em pixel (método e limites)

As seções seção 19 e seção 21 decidem coisas contra "o que a figura mostra". Isso só vale
se a leitura da figura for reprodutível, então fica aqui o procedimento inteiro,
com os comandos.

### 20.1 Procedimento

```sh
# Fig.2 está na página 3 do PDF.
pdftoppm -r 200 -f 3 -l 3 -png docs/replicacao/papers/ESEM14.pdf /tmp/fig2
```

Sobre o PNG resultante (200 dpi), por painel:

1. **Calibrar o eixo x** pelas linhas de grade brancas do fundo cinza, cujos
   valores estão impressos: 250/500/750 no homebrew, 50/100 no paperclip, 5/10
   no clojure, 5 no blueprint-css. Duas grades dão a escala px→pessoa e a
   posição do zero. Os mesmos valores estão em
   `config/checkpoints.yaml: esem14_fig2.x_ticks`.
2. **Calibrar o eixo y** pelas linhas de grade horizontais, que no artigo caem
   de ano em ano; a banda é 1/4 da distância entre duas grades (`band_months: 3`).
3. **Ler cada barra** como uma corrida de pixels escuros na linha do centro da
   banda, para a esquerda (non-coding) e para a direita (coding) do zero.

O vetor do clojure lido assim está congelado em
`config/checkpoints.yaml: esem14_fig2.bars_read_clojure`, e é o alvo das
varreduras da seção 19.

### 20.2 Limite conhecido: a borda da barra

A barra desenhada tem contorno preto, e o contorno entra na corrida de pixels.
Isso infla a leitura sistematicamente em ~2%: totais medidos 3946 / 535 / 47 /
13 (homebrew / paperclip / clojure / blueprint-css) contra 3882 / 524 / 49 / 13
da replicação na janela de 12 meses. O erro é para cima e é o mesmo em todos os
painéis, então **diferenças de ±2% não são achado**; o que se usa aqui é a forma
(qual banda tem barra, qual está vazia) e diferenças grandes.

Por isso o teste que mais pesa nas decisões não é o de tamanho, é o **teste do
buraco**: banda vazia na figura tem de estar vazia na replicação. Buraco não tem
borda para inflar, não depende de calibração de escala e não perdoa: o
blueprint-css tem a banda 3 vazia entre barras cheias, e é isso que derruba
tanto o estoque (seção 19.3) quanto `band_days: 91.3125` (seção 21).

### 20.3 Varredura da janela (L1 banda a banda, contra os pixels)

Erro L1 somando todas as bandas dos dois lados, por projeto e por janela de
inatividade da pirâmide (`plots.pyramid_window_months`), em `2011-12-31`:

| janela | 3m | 6m | 9m | **12m** | 18m | 24m | ∞ (estoque) |
|---|---|---|---|---|---|---|---|
| homebrew | 2560 | 1369 | 747 | **328** | 594 | 799 | 855 |
| paperclip | 355 | 203 | 69 | **33** | 181 | 268 | 364 |
| clojure | 26 | 18 | 14 | **10** | 25 | 34 | 49 |
| blueprint-css | 12 | 5 | 1 | 2 | 3 | 4 | 23 |

12 meses é o mínimo nos quatro painéis (no blueprint-css, 9m ganha por 1 pessoa,
dentro do ruído de uma barra unitária, e 9m perde feio nos outros três). É
esta tabela que fixa
`pyramid_window_months: 12`.

## 21. `band_days: 90`: a banda usa mês comercial

`periods.band_months: 3` é literal no artigo ("three months groups", p.1306),
mas "três meses" em dias não é óbvio: 3 × 365.25/12 = 91,3125 dias contra 90 de
mês comercial. A diferença parece decorativa (1,3 dia por banda), mas ela
desloca quem está na fronteira, e a Fig.2 tem gente na fronteira.

Varrendo as duas larguras contra os pixels (seção 20), com a janela em 365,25 dias:

| largura da banda | L1 total (4 painéis) | blueprint-css |
|---|---|---|
| **90,0000 d** | **437** | **0 (exato, banda a banda)** |
| 91,3125 d | 481 | 2 |

90 ganha em todas as janelas testadas (360, 364, 365, 365,25, 366, 370 dias).
No blueprint-css o resultado é categórico: com 90 as seis bandas do artigo batem
uma a uma, **incluindo o buraco na banda 3 e o topo na banda 15**; com 91,3125 o
contribuidor do topo cai uma banda, o buraco some e a replicação desenha três
quadrados grudados, que foi exatamente o sintoma reportado na inspeção visual
("o quarto quadrado está logo acima dos três, sem o espaço vazio"). No paperclip
o mesmo 90 põe o topo na banda 15, que é o que faz o rótulo do eixo bater em
"4 years" como no artigo.

Fica registrado o incômodo, porque ele é real: a **janela** da pirâmide continua
em 365,25 dias (com 360 o blueprint-css desencaixa), enquanto a **banda** usa
mês de 30 dias. O artigo não usa uma convenção só, e unificar por gosto de
simetria quebra a replicação. `band_days` é chave própria em
`config/settings.yaml` justamente para isso ficar explícito em vez de escondido
numa constante.

## 22. Parâmetros de plot por projeto? Não. O resíduo é do homebrew

Hipótese levantada na inspeção visual: os autores podem ter desenhado cada
painel da Fig.2 com parâmetros próprios (largura de banda, janela, definição de
população), o que explicaria os quatro painéis baterem com qualidade diferente.

Teste: com **um único jogo de parâmetros** (`band_days: 90`, janela de 365,25
dias, população = ativo no snapshot, taxonomia `prose`) comparar banda a banda,
lado a lado, contra os pixels medidos em seção 20. Snapshot 2011-12-31.

| painel | bandas | esquerda (non_coding) | direita (moved+coding) |
|---|---|---|---|
| blueprint-css | 16/16 | exato | exato |
| paperclip | 16/16 | ±1 pessoa (b6, b7, b11) | +6 concentrado na b13 |
| clojure | 24/24 | exato | deslocamento local b20↔b21 |
| homebrew | 10/10 | déficit nas bandas velhas | excesso nas bandas novas |

Se cada painel tivesse parâmetros próprios, o erro seria *aleatório entre
painéis*. Não é: três dos quatro batem com o mesmo jogo, e o blueprint-css bate
**banda a banda nos dois lados**, o que é forte demais para coincidência com
parâmetro errado. **Hipótese descartada.**

O que sobra é específico do homebrew, e tem assinatura, não é ruído de escala:

| banda | artigo esq | nós esq | artigo dir | nós dir |
|---|---|---|---|---|
| 3 (velha) | 65,4 | 33 | 0,0 | 8 |
| 6 | 75,5 | 46 | 183,7 | 191 |
| 7 | 219,0 | 216 | 332,2 | 380 |
| 9 (nova) | 739,9 | 733 | 392,6 | 451 |

O artigo põe **mais gente do lado non_coding nas bandas velhas** e **menos do
lado coding nas bandas novas**. Como o lado é decidido por `init_c` (data do
primeiro evento de coding), e não por CCR, o suspeito passa a ser o
**escopo de commit** (`commit_scope`, AMBIGUIDADE 2), que só morde no homebrew
porque é o único dos quatro com volume de commits fora do root. Antecipar um
`init_c` joga a pessoa do lado esquerdo para o direito e, por ser data de
*primeiro* evento, também muda a banda. Direção compatível com o sinal medido.

Próximo passo registrado (não executado): rodar `commit_scope:
family_project_commits` só para medir o L1 do homebrew contra seção 20, e conferir
o efeito colateral nos Tipos A-D antes de tocar no default.

## 23. clojure, bandas 20/21: 3 pessoas trocadas de banda, sem parâmetro que conserte

Sintoma visual: no nosso painel a barra da banda 21 (idade 270-360 d) encosta no
tick 10 do eixo, que é o limite lido do artigo. No artigo essa barra tem ~6 e a
vizinha (banda 20, 360-450 d) tem 7. ~~**O total das duas bate: 14 no artigo, 14
na replicação.** É deslocamento de ~3 pessoas entre bandas adjacentes.
Sobrecontagem fica descartada.~~

> **ERRO, corrigido em seção 25.** O total *não* bate: 14 no artigo contra **15** na
> replicação, e o desvio na banda 21 é de 4 pessoas, não 3. A conta acima somou a
> replicação errado e por isso a seção 23 concluiu "deslocamento puro" cedo demais.
> A leitura correta e o que ela abre está em seção 25.

### Teste 1: geometria (largura da banda × deslocamento de idade)

Varredura de `band_days` ∈ {86, 88, 89, 90, 91, 91.3125, 92} × offset de idade
∈ {0, 5, 10, 15, 20} d, L1 contra os pixels de seção 20:

| band_days | offset | L1 total | homebrew | paperclip | clojure | blueprint |
|---|---|---|---|---|---|---|
| **90** | **0** | **411,3** | 362,7 | 37,7 | 10,7 | **0,2** |
| 89 | 0 | 429,0 | 372,8 | 42,4 | 8,8 | 5,0 |
| 91 | 0 | 430,0 | 373,9 | 43,4 | 12,5 | 0,2 |
| 89 | 10 | 527,1 | 429,9 | 83,5 | **6,7** | 7,0 |

`(90, 0)` é o mínimo global e o único ponto que zera o blueprint-css. O melhor
resultado para o clojure isolado, `(89, 10)` com L1 6,7, quebra o blueprint (7,0)
e piora o homebrew em 67 e o paperclip em 46. **Não existe geometria que arrume
o clojure sem destruir os outros três.** seção 21 fica confirmado por um segundo
caminho.

### Teste 2: regra de população

Hipótese de seção 19 (o contribuidor de evento único infla a base). Testada de frente,
sempre com `band_days: 90`:

| regra | L1 total | homebrew | paperclip | clojure | blueprint | N clojure |
|---|---|---|---|---|---|---|
| **janela 12 m (atual)** | **411,3** | 362,7 | 37,7 | 10,7 | **0,2** | 49 |
| janela 12 m, sem evento único | 1328,8 | 1081,5 | 225,2 | 17,1 | 5,0 | 32 |
| `active` (3 m) | 2848,6 | 2471,1 | 340,1 | 25,5 | 11,9 | 21 |
| `active` ∪ multi-evento | 1378,5 | 1070,6 | 274,3 | 24,5 | 9,1 | 55 |
| janela 12 m e span ≥ 90 d | 3447,9 | 2985,0 | 424,2 | 27,8 | 10,9 | 21 |

**Hipótese descartada, e com folga.** Tirar o contribuidor de evento único
triplica o erro e piora o clojure também (17,1 contra 10,7). O evento único não
é ruído a filtrar: ele é parte da população que o artigo desenha. seção 19 fica
corrigido nesse ponto: o mecanismo lá descrito existe, mas não é o que separa a
replicação do artigo.

### O que sobra

As 11 pessoas da banda 21 têm idades 271, 283, 291, 301, 307, 308, 310, 317, 347,
350 e 356 dias. Nove delas ficam num aperto de 271-317 d, uma leva real de estreantes
do começo de 2011. Para casar com o artigo, três teriam de ser ~10 dias mais
velhas. Nenhuma convenção de calendário testada produz isso sem mover o resto.

Num painel onde 1 pessoa = 1 unidade e o eixo vai a 10, três pessoas na fronteira
é o piso de ruído do menor dos quatro projetos. Fica **aberto e medido** (L1 =
10,7 em 47 pessoas), não fechado como "ok". A barra encostar no tick 10 é
consequência disso, não erro de plotagem: o eixo é o do artigo e a replicação tem
mesmo 11 ali.

## 24. As figuras do IEICE16 (2016): o que dá para checar e o que não dá

Pergunta recorrente: "as figuras do 2016 estão batendo?" A resposta depende da
figura, porque duas das três não têm número nenhum para bater.

| figura | natureza | como é checada | status |
|---|---|---|---|
| Fig. 6 | qualitativa: "Examples… (Note that scales are different.)" | os 6 projetos têm de cair nos Tipos A/B/C certos | ok (`msr14.tab2.concordancia` 48/55 = 87 %) |
| Fig. 7 | qualitativa: "CCR and NCR are close to 0" | homebrew (A) e rails (D) nos quadrantes certos | ok |
| Fig. 8 | **quantitativa**: medido × predito | seção 12, coorte-componente | parcial |

Fig. 6 e 7 são galerias de exemplo com escala por painel; a própria legenda avisa
disso. Não existe eixo comum nem valor impresso, então "bater" ali significa só
que o projeto está no tipo certo, e isso está travado no `validate`.

A Fig. 8 é a única com conteúdo numérico, e é onde a divergência mora:

* **direção** (coorte erra menos que baseline): 15 de 21 casos ok;
* **valor absoluto do ABRE**: 7 de 40 ok, 33 divergentes (seção 12.1).

Ou seja, o resultado *qualitativo* do IEICE16 (a projeção por coorte é melhor
que a ingênua) reproduz; os números absolutos da Tabela 3/4 não. Isso é
consistente com seção 12.1 e não foi contornado: está registrado como divergência
conhecida, não como acerto.

Sobre "o problema pode estar no artigo": é uma possibilidade real e já
materializada em outros pontos (seção 10 `symfony`, seção 13 `jekyll`, seção 16 as 7 células
residuais). O que este repositório não faz é *assumir* isso: cada divergência
sai com o comando que a produziu, para que a hipótese "erro do artigo" seja
verificável em vez de conveniente.

## 25. clojure, banda a banda: onde exatamente a replicação difere do artigo

seção 23 fechou cedo demais e com uma soma errada. Refeita a conta banda a banda,
alinhando o índice do artigo (banda 1 = topo, 24 bandas) ao nosso (banda 0 =
base), com `pyramid_frame` de 2011-12-31:

| nossa banda | idade (d) | artigo (coding) | replicação (coding) | |
|---|---|---|---|---|
| 0 | 0-90 | 8 | 8 | ok |
| 1 | 90-180 | 5 | 5 | ok |
| 2 | 180-270 | 3 | 4 | +1 |
| **3** | **270-360** | **6** | **10** | **+4** |
| **4** | **360-450** | **7** | **4** | **−3** |
| 5 | 450-540 | 3 | 2 | −1 |
| 6 | 540-630 | 1 | 1 | ok |
| 7 | 630-720 | 3 | 4 | +1 |
| 8-10 | 720-990 | 1, 2, 5 | 1, 2, 5 | ok |
| 11-22 | (vazio) | 0 | 0 | ok |
| 23 | 2070-2160 | 1 | 1 | ok |
| **total** | | **45** | **47** | **+2** |

Sete das doze bandas povoadas batem exatamente. O erro está concentrado num par:
a banda 3 sobra 4 pessoas e a banda 4 falta 3. É a banda 3 que encosta no tick 10
e é isso que se vê no painel.

### O que foi descartado agora

**Largura de banda (varredura ampla).** seção 23 varreu só 86-92 d, ancorado em "3
meses ≈ 90 d". Refiz de 60 a 120 d em passos de 0,25. Resultado: o próprio
artigo trava o parâmetro: o painel do clojure tem **24 bandas** e o
contribuidor mais velho tem 2107 d, o que força `w ∈ [87,8; 91,6]`. Dentro dessa
faixa o melhor é `w = 89` (L1 = 8 contra 10 do atual) e a banda 3 continua com 9.
**Nenhuma largura legítima leva a banda 3 de 10 para 6**. A restrição vem da
contagem de bandas do desenho, fora do meu alcance.

**Deslocamento de idade (varredura ampla).** seção 23 varreu offset de 0 a 20 d.
Refiz de −120 a +180. O melhor par é `(w = 89, offset = +10 d)`, L1 = 6, e nele a
banda 3 cai para 8, abaixo do tick, que é o efeito visual pedido. Mas seção 23 já
mediu esse ponto nos outros três painéis: ele **quebra o blueprint-css** (único
painel hoje exato, L1 0,2 → 7,0) e piora o homebrew em 67. Continua valendo:
não existe geometria que conserte o clojure sem estragar os outros.

**Artefato de importação em massa.** Hipótese de que os contribuidores da banda 3
fossem uma leva sintética criada na migração do clojure para o GitHub. Falsa: os
primeiros eventos deles se espalham de 2010-10-11 a 2011-04-03, um por dia, sem
nenhum pico de importação. As idades são reais.

### O que fica aberto (a hipótese mais forte que sobrou)

Dos 11 da banda 3, **6 têm exatamente um evento na vida do projeto** (57490,
64659, 64666, 64676, 64685, 66395: cinco commits e um pull request). No dump do
MSR14 a tabela `users` tem a coluna **`fake`**: o GHTorrent cria uma linha
sintética para autor de commit identificado só por e-mail, sem conta no GitHub.
O pipeline hoje **não olha essa coluna** (`grep -rn "fake" src/pyramid/sources/`
não devolve nada).

Isso interessa porque:

* é um filtro **documentado do dataset**, não um parâmetro ajustável, e por isso
  não cai na armadilha de seção 21/seção 23 de tunar geometria até a figura ceder;
* incide exatamente onde sobra gente (a banda 3), e não onde já bate;
* explicaria o excesso de +2 no total e parte do +4 da banda 3.

Não dá para concluir agora: o container do MySQL está parado e o teste exige uma
query nova em `src/pyramid/sources/msr14.py` (SQL não se escreve fora de lá).
**Atenção ao risco:** tirar os 6 levaria a banda 3 a 4, contra 6 do artigo. Pode
passar do ponto. Só o teste real, nos quatro projetos ao mesmo tempo, decide.

### Estado honesto

A barra do clojure continua encostando no 10 porque a replicação **tem mesmo** 10
pessoas com 270-360 dias de idade em 2011-12-31, e nenhuma convenção de eixo,
largura ou origem de idade testada até aqui muda isso sem quebrar painel que já
está certo. Não vou baixar o tick nem filtrar gente até a barra caber: isso
esconderia a divergência em vez de explicá-la. Fica aberto, com o próximo teste
já nomeado (`users.fake`).

## 27. As travas de projeção quebraram em `ee3ba45` (banda de 90 dias), e ninguém re-travou

### O sintoma

`pyramid validate` no HEAD acusa três FALHA, todas na seção 12.5/seção 12.2:

| trava | esperado | obtido |
|---|---|---|
| `replica_locks.projection_celulas_2pct` | 7/40 | 6/40 |
| `replica_locks.projection_agregado.cohort` | 0.4208 | 0.3894 |
| `replica_locks.projection_agregado.p` | 0.0073 | 0.0124 |

Isso é pior do que um número fora de lugar: são travas de deriva da **própria
replicação**, não valores do artigo. Uma trava de deriva que falha significa que o
código de hoje não reproduz o código de ontem.

### Quem mexeu

`projection.py` **não foi tocado** desde o commit que o criou:

    git log --oneline 315e42d..HEAD -- src/pyramid/projection.py   # vazio

E as travas foram escritas uma única vez, no commit de scaffolding:

    git log --oneline -S"projection_celulas_2pct" -- config/checkpoints.yaml
    # f0d888b scaffolding: layout do repo, deps, dataset e docs de referência

Ou seja: o estágio 6 é o mesmo, a trava é a mesma, e mesmo assim o número mudou.
A projeção conta por banda (`_counts_by_band`, sobre `snaps["band"]`), e a banda
vem do estágio 3. O único commit posterior que mexe em `snapshots.py` é:

    git log --oneline 315e42d..HEAD -- src/pyramid/snapshots.py
    # ee3ba45 snapshots: banda de 90 dias e idle_days por contribuidor

`ee3ba45` trocou o corte da banda de `band_months` (3 × 365.25/12 = 91.3125 d)
para `band_days: 90`. O commit justifica a troca contra os pixels da Fig.2 do
ESEM14 (seção 21) e mede o efeito **na figura**. Não roda a projeção nem confere as
travas da seção 12.5.

### O teste que fecha o caso

Um único parâmetro, todo o resto no HEAD:

    # config/settings.yaml: band_days: 90 -> 91.3125
    uv run pyramid snapshots --force && uv run pyramid metrics --force \
      && uv run pyramid projection --force && uv run pyramid validate --report /tmp/valrep_band9131.md

Resultado: **as quatro travas voltam exatas** (7/40, 14/20, cohort 0.4208,
p 0.0073) e o relatório inteiro fecha em `0 FALHA` (167 checks, conhecida=65,
ok=102). Voltando a 90, reaparecem as três FALHA. Causa isolada, sem ambiguidade.

### O que isso custa, e por que não re-travei sozinho

A banda não é neutra entre os dois artigos. Comparando os dois relatórios, **16
checks mudam de status, todos do estágio 6** (nenhum check de figura muda):

* **90 piora 12**: `direcao.A.non_coding`, `direcao.B.coding`,
  `abre.C.non_coding.cohort` (0.6723 → 0.5492, contra 0.6711 do artigo),
  `abre.C.all.baseline` (0.6607 → 0.5000, contra 0.6667 do artigo),
  `wilcoxon.C.non_coding`, `wilcoxon.C.all`, `wilcoxon.D.moved`,
  `wilcoxon.D.coding`, `wilcoxon.D.all`, e as 3 travas.
* **90 melhora 4**: `direcao.B.all`, `direcao.C.moved`, `All.moved`, e
  `abre.C.all.cohort` (0.3475 → 0.2857, contra 0.2875 do artigo, quase exato).

Repare que os `abre.*` são **valores do artigo**, não travas nossas: 91.3125
ganha em dois deles e perde em um. A hipótese "a trava velha defende a si
mesma" cai por aí. A banda de 91.3125 concorda mais com a Tabela 3 do IEICE16, enquanto a
de 90 concorda mais com a Fig.2 do ESEM14 (seção 21, onde o blueprint-css zera).

É uma ambiguidade real entre dois artigos dos mesmos autores, e as duas saídas
são defensáveis; nenhuma delas é "arredondar pra ficar perto". Fica **aberto**
para decisão, com as opções nomeadas:

1. **Manter 90 e re-travar** a seção 12.5/seção 12.2 nos valores novos, registrando aqui
   que a escolha comprou a Fig.2 ao preço de 12 checks da Tabela 3. A trava
   volta a ser trava, mas o histórico de que já batemos 0.4208 tem de ficar.
2. **Voltar para 91.3125** e assumir o erro L1 da Fig.2 (blueprint-css sai do
   exato). Desfaz seção 21.
3. **Duas bandas** (90 na figura, 91.3125 na projeção). Tecnicamente reproduz
   tudo, mas é exatamente o que a checagem em `snapshots.band_days()` foi
   escrita para impedir, e não tem defesa no texto de nenhum dos dois artigos.
   Só valeria se aparecesse evidência de que os autores cortaram diferente em
   cada paper.

### A lição de processo

`ee3ba45` mediu o efeito da mudança na figura que motivou a mudança, e só nela.
O estágio 6 consome o mesmo parquet e ficou fora do teste. Regra que passa a
valer: **mudou `snapshots.py` ou o bloco `periods:`, roda `validate` inteiro
antes de commitar**. A banda é insumo de tudo que vem depois dela.

### Decisão (2026-08-07): opção 1, manter 90 e re-travar

Escolhida a opção 1. As três travas foram atualizadas em `config/checkpoints.yaml`,
com os valores anteriores preservados em comentário `# antes:` na mesma linha:

| trava | antes (até `315e42d`) | agora (`ee3ba45`) |
|---|---|---|
| `projection_celulas_2pct` | 7/40 | 6/40 |
| `projection_agregado.cohort` | 0.4208 | 0.3894 |
| `projection_agregado.p` | 0.0073 | 0.0124 |
| `projection_direcao_pares` | 14/20 | 14/20 (inalterado) |
| `projection_agregado.baseline` | 0.5000 | 0.5000 (inalterado) |

O desempate **não** foi por proximidade numérica. Nesse quesito as duas bandas
empatam na prática (L1 da Tabela 3: 5,1054 para 90 contra 4,9574 para 91,3125,
3% de diferença em 40 células, dentro do ruído). Foi pela hierarquia de critérios: os projetos nomeados da Fig.2 devem bater
**exatamente**, enquanto a Tabela 3 célula a célula **não é critério de
aceite**. Com 90 o
blueprint-css bate banda a banda; com 91,3125 não.

**O custo, dito sem maquiagem:** o Wilcoxon célula a célula cai de 11/20 para
7/20 pares concordando com o artigo. O predicado agregado, que é o critério,
passa nas duas bandas (cohort 0,3894 < baseline 0,5000, p=0,0124 < 0,05). Se
algum dia o critério de aceite mudar para célula a célula, **esta decisão se
inverte**, e é para isso que a linha do "antes" fica no `checkpoints.yaml`.

Os valores anteriores à troca de banda, válidos até `315e42d`, eram cohort
0.4208, p = 0.0073 e 7 de 40 células dentro de 2%, a ~5% do artigo. A leitura
completa do resultado da projeção está na seção 12.5.

## 28. Fig.2 do ESEM14, diagnóstico painel a painel (banda a banda)

Leitura do usuário sobre a figura gerada, confrontada com os números. Bandas
contadas da base (0 = mais jovem) para cima, banda de 90 dias, corte 2011-12-31.
Coluna "artigo" = leitura em pixel de `/tmp/fig2_medido.json` (±1 pessoa; para o
clojure vale a leitura mais confiável de `bars_read_clojure` no `checkpoints.yaml`).

### homebrew: a massa está certa, a idade não

| banda | artigo esq | nosso non_coding |
|---|---|---|
| 0 | 581 | 565 |
| 1 | 740 | 733 |
| 2 | 365 | 357 |
| 3 | 219 | 216 |
| 4 | 75 | 46 |
| 5 | 58 | 39 |
| 6 | 45 | 37 |
| 7 | 65 | 33 |
| 8 | 33 | 27 |
| 9 | 18 | 18 |

As quatro bandas da base batem dentro de 3%. Da banda 4 para cima somos ~32%
mais finos (200 contra 294 pessoas). **Mas a população total do painel é
praticamente igual: 3882 nossos contra 3810 do artigo, +1,9%.** Massa conservada
com distribuição deslocada para baixo significa uma coisa só: para ~95 pessoas
nossa data de primeira atividade é mais tarde que a dos autores, e elas caem em
bandas jovens demais. A banda 7 (a "terceira de cima para baixo" apontada pelo
usuário) é o pior caso, 33 contra 65, e no artigo ela é um *bump* que quebra a
monotonia das vizinhas (45 → 65 → 33), o que não sai de um processo de entrada
que só decai. Sugere um bloco de gente com âncora de idade diferente da nossa.

### paperclip: some uma pessoa no topo, do lado da discussão

Bandas 0-3 são exatas (103/103, 114/116, 90/91, 40/40). O topo (banda 15) tem
1 pessoa em coding nos dois. A banda 14 tem 1 pessoa em `non_coding` no artigo e
**0 na nossa**, o "cara faltando no penúltimo quarter do ano 4 em discussão".
Uma pessoa cuja atividade mais antiga, para os autores, é de discussão e é ~3
meses anterior à que temos. Mesmo sinal do homebrew, em escala de 1 pessoa.
As dissonâncias dos anos 2 e 3 são as bandas 4-10, onde erramos por ±1 pessoa
em quase todas, dentro do erro da leitura em pixel, mas na mesma direção.

### clojure: o 10 é um empilhamento, não um excesso de gente

Bandas 2, 3, 4: artigo 6/7/7 (total 20), nós 4/10/4 (total 18). O total quase
bate; o que difere é o *espalhamento*. Nosso pico de 10 na banda 3 é o que faz o
painel encostar no tick de 10, coisa que o artigo nunca faz (máximo 8, na base).
Por idade crua a banda 3 tem 11 pessoas e a banda 4 tem 16; o que decide quem
aparece é o filtro de inatividade, e é ele que concentra 10 na banda 3 e deixa
só 4 na banda 4. Ou seja: aqui o suspeito **não** é a âncora de idade, é a
janela de inatividade interagindo com a borda da banda.

### blueprint-css: bate 100%

Confirmado pelo usuário. É o único painel sem gente em `non_coding` no meio da
pirâmide, o que é consistente com a hipótese acima: sem eventos de discussão,
não há âncora de idade para errar.

### O fio comum

Três dos quatro painéis erram na mesma direção: **nossa primeira atividade é
mais tarde que a dos autores**, e o erro aparece onde há discussão. O candidato
com nome é a `AMBIGUIDADE 1` (seção 35): `issue_events` está fora do nosso
`EVENT_COLUMNS`. Se os autores contaram abertura de issue como atividade, todo
mundo que começou comentando/abrindo issue antes de commitar entra mais cedo na
pirâmide, exatamente o padrão observado. **Não testado ainda**: exige SQL novo
em `src/pyramid/sources/` para trazer `issue_events`. É o próximo experimento.

## 31. O eixo estava virado: seções 19 a 30 compararam a Fig.2 de cabeça para baixo

**Erro meu, no medidor, não no pipeline.** A comparação banda a banda contra os
pixels da Fig.2, que sustenta tudo o que foi escrito de seção 19 a seção 30, estava
espelhada no eixo vertical.

Causa exata. Em `/tmp/measure_fig2.py` a lista `YT` guarda os centros das barras
em **y crescente** (homebrew: 286.5 … 485.5) e, em coordenada de imagem, y
cresce para baixo. O laço faz `band=k+1`, então `band=1` é a barra do **topo**
do painel (a coorte mais velha). Já `snapshots.band` é 0-based de **baixo para
cima** (`0 = (0,90]d`, os recém-chegados). O harness comparava `art[b]` contra
`nossa_band[b]`, casando o topo do artigo com a base da replicação.

O mapeamento correto é `art_band = N - nossa_band`, com `N` = número de bandas
do painel.

### 31.1 Efeito na medida

Snapshot `2011-12-31`, população `active`, janela 12m, `band_days: 90`:

| projeto | pop. artigo | pop. replicação | L1 como estava | L1 corrigido | L1/pop |
|---|---|---|---|---|---|
| homebrew | 3810 | 3882 | 6624 | **363** | 9.5% |
| paperclip | 519 | 524 | 997 | **38** | 7.3% |
| clojure | 46 | 49 | 91 | **11** | 23.1% |
| blueprint-css | 13 | 13 | 22 | **0** | 0% |
| **total** | | | **7734** | **411** | |

A replicação da Fig.2 é ~19× melhor do que este log vinha registrando. O
blueprint-css bate **exato**, célula a célula. As populações totais dos quatro
painéis batem dentro de 2%.

Sintoma que deveria ter denunciado o erro antes: a distribuição "do artigo"
saía invertida (topo largo, base estreita), o que não é uma pirâmide. E o
usuário, lendo a figura a olho, afirmou desde cedo que o primeiro ano dos quatro
painéis batia e que o blueprint-css batia inteiro, as duas coisas verdadeiras e
as duas contraditas pelos meus números. **A leitura visual estava certa e a
numérica errada durante toda a investigação.**

### 31.2 O que sobrevive

A varredura de parâmetros foi refeita com a orientação correta e **nenhuma
decisão muda**:

| parâmetro | alternativas | L1 corrigido |
|---|---|---|
| população | `active` / `stock` | **411** / 1512 |
| janela | 6 / 9 / **12** / 15 / 18 / 24 m | 1542 / 782 / **411** / 728 / 971 / 1316 |
| `band_days` | **90** / 91.3125 | **411** / 444 |

Ou seja: seção 18 (population = `active`), seção 19 (janela de 12 meses) e seção 21
(`band_days: 90`, onde o blueprint-css zera) continuam de pé, agora por margem
menor e por motivo confiável. A errata da Tabela 3 (seção 27) não é afetada: ela
depende de `band_days`, cuja escolha se mantém.

### 31.3 O que fica invalidado

Índices de banda e magnitudes de resíduo relatados em **seção 19, seção 22, seção 23, seção 25, seção 28
e seção 29** estão espelhados e superestimados. Concretamente:

- seção 23 ("clojure, bandas 20/21: 3 pessoas trocadas"): as bandas são as 3/4
  contadas de baixo; o resíduo do clojure inteiro é de 11 células.
- seção 28 e seção 29 (tabelas painel a painel): a coluna "artigo" precisa ser lida na
  ordem inversa.
- seção 19 ("sobrecontagem … o mecanismo é o contribuidor de evento único"): a
  sobrecontagem existe, mas vale ~14% no lado *coding* das bandas jovens do
  homebrew, não o fator que estava registrado.
- A conclusão de seção 30 sobre `issue_events`/`union` (seção 28, seção 29) foi tirada contra o
  alvo errado e precisa ser refeita. Ver seção 31.4.

Não foram reescritas: ficam como registro do que se acreditou e quando, que é o
propósito deste log.

### 31.4 O resíduo que sobrou, agora legível

Homebrew concentra 363 dos 411. A assinatura é única e limpa: no **lado coding
das bandas jovens** temos sistematicamente ~14% de gente a mais que o artigo.

| banda (artigo) | artigo, coding | replicação, coding |
|---|---|---|
| 10 (base, 0-90d) | 320 | 368 |
| 9 (90-180d) | 393 | 451 |
| 8 (180-270d) | 294 | 336 |
| 7 (270-360d) | 332 | 380 |

O lado da discussão bate quase exato nas mesmas bandas (581→565, 740→733,
365→357, 219→216). Então não é a régua de idade nem a janela: é **quem conta
como `coding`**. Próximo experimento: a fronteira `coding` × `non_coding` no
`classify.py` contra a taxonomia da Tabela 1 do ESEM14 (`AMBIGUIDADE 3`), medida
contra este alvo agora corrigido.

## 32. `AMBIGUIDADE 3` resolvida por medida: a prosa vence a Tabela 1, e o pull request é código

O ESEM14 se contradiz consigo mesmo na mesma página (p.1307). A coluna
"Separation" da Tabela 1 agrupa as 16 atividades em três blocos e coloca
`issues` como *non-coding* e `issues events` como *excluded*. A prosa da mesma
página lista o non-coding como "commit comments, issue comments, pull request
comments, **issue events**", e nem cita `issues`. As duas leituras dão
exatamente "six development activities", então nenhuma é descartável no papel.

Em paralelo, o ESEM14 seção 3 diz "we analyze the GitHub-wide events depending on
the current status of OSS projects (...) we are also interested in other
contributors who **send issues** and comments", o que puxa a favor da Tabela 1.
E `pull requests` aparece do lado *coding* na Tabela 1, apesar de abrir um PR
não ser um commit; só `pull request comments` cai na discussão.

### O experimento

Extraí o superconjunto de tipos de evento (variante `union`, 7 tipos) para os
4 projetos da Fig.2 e varri as três leituras × o lado do `pull_requests`,
medindo L1 banda-a-banda contra os pixels do artigo (alvo já com o eixo
corrigido da seção 31). Nenhum outro parâmetro mudou: `gap=91.3d`, janela de 12
meses, `population=active`, `band_days=90`, snapshot `2011-12-31`.

Comando: `uv run python /tmp/sweep_tax.py` (o script monta `profile()` +
`pyramid_at()` em memória a partir de `/tmp/union_<pid>.parquet`, sem tocar em
`output/`).

| taxonomia | `pull_requests` | L1 total | homebrew | paperclip | clojure | blueprint-css |
|---|---|---|---|---|---|---|
| **`prose` (ativa)** | **coding** | **411** | 363 | 38 | 11 | **0** |
| `prose` | discussão | 1165 | 1081 | 58 | 13 | 14 |
| `table1` | coding | 647 | 550 | 86 | 11 | 0 |
| `table1` | discussão | 1016 | 904 | 85 | 13 | 14 |
| `union` | coding | 432 | 361 | 60 | 11 | 0 |
| `union` | discussão | 1192 | 1087 | 79 | 13 | 14 |

### Conclusões

1. **`pull_requests` é `coding`, e isso não é opinião.** Mover o PR para a
   discussão piora L1 em *todas* as três leituras (411→1165, 647→1016,
   432→1192). O argumento decisivo é o blueprint-css: ele bate 100% com o
   artigo (L1=0) e **só** com `PR=coding`. Qualquer outro arranjo o quebra
   (L1=14). Um painel que fecha exato serve de âncora; ele trava a fronteira.
2. **A prosa vence a Tabela 1.** Contar `issues` como atividade (variante
   `table1`) piora L1 de 411 para 647. A hipótese era que `issues` traria gente
   para o lado da discussão do homebrew. Traz, mas na banda errada. `union`
   (contar os dois) também piora (432). Mantida `taxonomy.variant: prose`.
3. `AMBIGUIDADE 3` sai de "aberta" para **fechada por evidência**: as duas
   leituras eram defensáveis no texto, mas só uma reproduz a figura.

### O que sobra: a assinatura do erro do homebrew

Com a taxonomia agora travada, 363 dos 411 de erro estão no homebrew, e o
resíduo tem forma:

| | artigo | nosso | saldo |
|---|---|---|---|
| discussão (esquerda) | 2200 | 2071 | **−129** |
| código (direita) | 1611 | 1811 | **+200** |

O excesso de `coding` está concentrado nas **4 bandas mais novas** (0-360 dias:
+48, +58, +42, +48 = 196 dos 200). A falta de `non_coding` está no **miolo**
(bandas 3, 5 e 6: −32, −19, −30). Como os dois desvios vivem em faixas de idade
diferentes, **não é uma troca de lado**: se fosse relabel, o excesso de um lado
apareceria na mesma banda da falta do outro.

Isso aponta para a **âncora de idade** (`start_ref`), não para a fronteira de
categoria nem para a população. Hoje quem tem commit conta idade a partir do
primeiro evento de *código* (`init_c`); quem só discute conta a partir do
primeiro evento de discussão (`init_d`). Se o artigo ancorasse todo mundo no
primeiro evento de qualquer tipo, os coders ficariam mais velhos e sairiam das
bandas jovens, que é exatamente a direção do resíduo. Não testado ainda;
próximo experimento.

## 33. O resíduo do homebrew não é idade: é categoria. Três hipóteses refutadas

A seção 32 fechou a fronteira de categoria e deixou `L1=411`, dos quais **363 são só o
homebrew**. Lá a assinatura era `-129` na discussão e `+200` no código, com 196 do
excesso concentrado nas 4 bandas mais novas. Concluí na seção 32 que isso "aponta para a
âncora de idade". **Estava errado, e a medida mostrou o erro.**

### 33.1 A âncora de idade não pode consertar isso, por construção

Hoje `start_ref` é `init_c` para quem tem código e `init_d` para quem só discute.
Testei a alternativa óbvia: `start_ref = min(init_c, init_d)` para todo mundo
(primeiro evento de qualquer tipo), sem tocar em mais nada.

| âncora | L1 total | homebrew | paperclip | clojure | blueprint-css |
|---|---|---|---|---|---|
| `categoria` (atual) | **411** | 363 | 38 | 11 | **0** |
| `primeiro evento` | 439 | 368 | 58 | 11 | 2 |

Piora, e quebra o blueprint-css. Mas o dado que importa não é o L1: é que o saldo do
homebrew ficou **idêntico** nas duas rodadas (`disc=-129`, `cod=+200`). Isso não é
coincidência: é aritmética. A âncora move gente **entre bandas**, nunca **entre
lados**. Nenhum ajuste de idade, janela ou banda pode consertar o homebrew.
O problema é *quem* é contado como codificador, não *que idade* ele tem.

Registrado para não voltar a varrer o espaço de parâmetros de idade atrás disso.

### 33.2 A conta fechada

Com o eixo corrigido da seção 31, o homebrew em 31/12/2011 dá:

| | nosso | artigo | saldo |
|---|---|---|---|
| lado do código | 1811 | 1611 | **+200** |
| lado da discussão | 2071 | 2200 | **−129** |
| total | 3882 | 3811 | +71 |

Ou seja: **129 pessoas que chamamos de codificador o artigo chama de discussão**, e
sobram **71 pessoas que o artigo não tem de jeito nenhum**. Os dois números são
exatos, não aproximados. São o alvo de qualquer hipótese futura.

Candidatos naturais: 674 contribuidores vivos estão do lado do código **só** por
terem aberto pull request, sem nenhum commit (601 deles nas 4 bandas mais novas,
onde mora o excesso de +196). O tamanho bate com a forma do erro, mas nenhuma regra
testada até agora recorta 129 desses 674.

### 33.3 Duas regras de recorte testadas e refutadas

**(a) Autoria do PR (`pr.user_id` x `pull_request_history.actor_id`).** O GHTorrent
às vezes grava em `pull_requests.user_id` o dono do fork, não quem abriu o PR. Se
fosse o caso, trocar pela coluna do histórico mudaria a lista de codificadores.
Não é o caso:

| projeto | PRs | linhas em que as colunas divergem | autores distintos (`user_id` / `actor_id`) |
|---|---|---|---|
| homebrew | 13.171 | 49 | 4293 / 4293 |
| paperclip | 383 | 0 | 278 / 278 |
| clojure | 42 | 0 | 42 / 42 |
| blueprint-css | 16 | 0 | 16 / 16 |

49 linhas em 13.171 e a mesma contagem de autores distintos. A query de
`src/pyramid/sources/msr14.py` fica como está.

**(b) Só PR mergeado conta como código.** Hipótese razoável: um PR recusado não
virou código no projeto. Dos 674, **661 nunca tiveram um único PR mergeado**.
Aplicar a regra tiraria 661 do lado do código (alvo: 129), levando o homebrew de
`+200` para `−461`. Refutada com folga.

### 33.4 O que sobra

O `family_project_commits` (tarefa #8, ainda aberta) **anda na direção errada** para
este resíduo: ele só adiciona commits, ou seja, empurra gente *para dentro* do lado
do código, quando precisamos tirar 200. Continua valendo por outros motivos, mas não
é candidato aqui.

Sem hipótese testável no momento. O resíduo do homebrew fica declarado e quantificado
em `docs/replicacao/figuras/esem14_fig2.md`; os outros três painéis seguem com
`L1 = 38 / 11 / 0`.

## 34. Mais três hipóteses para o resíduo do homebrew, todas refutadas

Continuação da seção 33. O alvo continua sendo `-129` na discussão, `+200` no código,
`+71` de população. Nenhuma regra única testada recorta isso.

| hipótese | L1 total | homebrew | por que cai |
|---|---|---|---|
| `PR=código` (config ativa) | **411** | 363 | (referência) |
| `'moved'` no lado da discussão | 806 | 712 | são 481, precisa de 129 |
| `PR=EXCLUÍDO` (nem código nem discussão) | 1115 | 1038 | tira 475 do código, precisa de 200 |
| `PR=discussão` (seção 32) | 1165 | 1081 | tira 474 |

**34.1 `PR` excluído.** A seção 32 testou o pull request como código e como discussão,
nunca como *fora da conta*. Valia testar porque é a única regra que mexe nos dois
saldos ao mesmo tempo: quem tem PR + conversa migra para a discussão, e quem só tem
PR some da pirâmide. A população de fato cai de 3882 para 3835 (alvo 3811), mas o
lado do código desaba 475. Os 674 da seção 33 quase todos têm outra atividade, então
migram em vez de sumir.

**34.2 `moved` na discussão.** Quem discutiu antes de codificar hoje conta no lado do
código. Passar para a discussão anda na direção certa e erra a magnitude: são 481 no
homebrew (42 no paperclip), contra os 129 necessários. Piora o paperclip de 38 para
82 e o blueprint-css de 0 para 2.

**34.3 Limiar de 2 eventos de código.** Esta merecia atenção porque `200 = 129 + 71`
exatamente: se um único PR não bastasse para alguém ser "coding contributor", quem
tivesse 1 PR + conversa iria para a discussão (+129) e quem tivesse só o PR sumiria
(−71). A aritmética fecha, os dados não: são **589** com exatamente um evento de
código no homebrew (484 com outra atividade, 105 sem). A identidade `200 = 129 + 71`
é coincidência.

### 34.4 Hipótese não testável com o que temos

Sobra a possibilidade de o artigo ter usado **um dump anterior do GHTorrent**. O
GHTorrent recompleta o passado a cada coleta, então um dump de 2014 conhece mais
atividade de 2011 do que um dump de 2013 conhecia. Isso explicaria de uma vez a
população maior e o excesso concentrado nas faixas mais novas, gente que só aparece
no recorte mais recente. Não dá para verificar sem o dump antigo, que não temos, e
por isso **não entra como conclusão**: fica como observação.

### 34.5 Encerramento

Seis hipóteses testadas e refutadas entre seção 33 e seção 34, com o painel do blueprint-css
(`L1=0`) servindo de trava em todas. O resíduo do homebrew fica **declarado, medido e
sem hipótese em aberto**. Os quatro painéis encerram em `363 / 38 / 11 / 0`.

## 35. Definição de novato e os parâmetros da Tabela 2 (MSR14)

A grade da Tabela 2 do MSR14 tem **12 projetos × 8 anos (2004-2011) = 96 células**:
55 com letra (quadrante) e 41 estruturais (`-` projeto não existia / `*` não
elegível). A configuração atual acerta **48/55 letras e 41/41 estruturais**. Tudo
abaixo sai de:

```
uv run python scripts/sweep_msr14_tab2.py [--min-devs N] [--tie baixo|alto]
                                          [--sticky project|dataset] [--errors]
uv run python scripts/sweep_msr14_tab2.py --novato     # varre as definições A a D
```

### 35.1 Quatro definições de novato, nenhuma melhora

| variante | novato é… | letras | estrutura |
|---|---|---|---|
| **A (atual)** | 1º evento de **código**, estreia no dataset | **48/55** | 41/41 |
| B | 1º evento de **qualquer tipo** | 48/55 | 41/41 |
| C | novato *e* atividade = qualquer evento | 43/55 | 41/41 |
| D | novato **local**: estreia *neste* projeto (seção 15) | 45/55 | 41/41 |

A e B empatam, e não por acaso: no dataset inteiro elas divergem em **9 das 254**
células com quadrante, e **nenhuma das 9 cai dentro da grade** (são projetos fora
dos 12, mais `mojombo/jekyll 2012`, ano fora do recorte da tabela).

A razão é estrutural e vale registrar porque enterra uma família inteira de
hipóteses: **magnetismo e stickiness são razões comparadas à mediana da mesma
população**. Redefinir novato globalmente mexe no numerador de todo mundo na mesma
direção, a mediana anda junto, e o lado do eixo em que o projeto cai não muda. Só
redefinições que mexem nos projetos de forma **desigual**, como C e D, que trocam a
base por projeto, chegam a mover a grade, e movem para pior.

`mojombo/jekyll 2011` (artigo `terminal`, obtido `floating`) sobrevive a A, B, C e D:
não é questão de definição de novato.

### 35.2 `min_active_devs`: ótimo agudo em 10

| limiar | 5 | **10** | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|---|
| letras | 40/55 | **48/55** | 29/55 | 21/55 | 16/55 | 12/55 |

O valor publicado ("more than 10") é confirmado por medição, não adotado por
obediência: é um pico, não um platô, e a estrutura (41/41) só fecha de 10 para cima.
Tirar `jekyll/2011` da grade por limiar exigiria ≥25, que custa 32 letras. Refutada.

### 35.3 Desempate na mediana: a convenção atual ganha 6 a 2

Com `n` ímpar de elegíveis, o projeto do meio **é** a mediana e empata. Isso ocorre em
**8 células com letra** da grade. O artigo coloca **6 delas no lado baixo** e 2 no alto
As 2 exceções são a mesma linha, `xbmc/xbmc` (2007 e 2009). Inverter a regra
globalmente (`--tie alto`) troca 6 acertos por 2: **48 → 46**. A convenção atual
(empate → lado baixo) fica confirmada por contagem. Que as duas exceções sejam o
mesmo projeto aponta para o valor do `xbmc` estar marginalmente acima da mediana nos
dados do artigo, não para uma regra diferente. Ver seção 35.5.

### 35.4 `stickiness_scope`

`--sticky dataset` (retenção medida no dataset inteiro, não no projeto) cai para
**42/55**. Escopo por projeto confirmado.

### 35.5 As 7 células residuais

```
xbmc/xbmc 2007            artigo attractive / obtido floating     (empate exato)
xbmc/xbmc 2009            artigo attractive / obtido stagnant     (empate exato)
django/django 2011        artigo attractive / obtido stagnant
jquery/jquery 2010        artigo floating   / obtido attractive
chriseppstein/compass 2010 artigo floating  / obtido terminal
scala/scala 2010          artigo floating   / obtido (lacuna)
mojombo/jekyll 2011       artigo terminal   / obtido floating
```

Duas são empates exatos (seção 35.3): cara ou coroa, não regra. Uma é **lacuna de dados**:
`scala/scala` tem **zero eventos de código em 2010** no nosso dump (10 devs em 2007,
25 em 2009, nada em 2010, 20 em 2011), então não há limiar nem parâmetro que
produza letra ali. As quatro restantes exigem correções **contraditórias** no mesmo
eixo: `django` e `jquery` precisam de magnetismo puxado em direções opostas. Não
existe correção sistemática única.

O padrão é o mesmo da seção 34.4: buracos e diferenças de cobertura compatíveis com **outro
vintage do dump do GHTorrent**, que recompleta o passado a cada coleta. Segue como
observação, não como conclusão.

### 35.6 Encerramento

Sete hipóteses testadas neste bloco (4 definições de novato, limiar, desempate,
escopo de stickiness). Nenhuma melhora a grade; três delas (limiar 10, empate para
baixo, escopo por projeto) passam a ser **escolhas medidas em vez de herdadas**. O
resíduo de 7 células fica declarado, com 3 explicadas (2 empates + 1 lacuna) e 4 sem
correção sistemática possível.

## 36. `commit_scope`: as três leituras de "commit do projeto", medidas nos 4 painéis

A seção 21/seção 22 deixaram em aberto a suspeita mais razoável sobre o resíduo do homebrew:
`commit_scope=root` conta só os commits registrados **no** projeto raiz, e o homebrew
é justamente o painel com mais fork. Como o fork carrega uma cópia do histórico da
mãe em `project_commits`, há três leituras plausíveis:

- **`root`** (config atual): commits cujo `project_id` é o do projeto;
- **`family_project_commits`**: união via `project_commits` sobre a família (raiz + forks);
- **`family_project_id`**: união via `commits.project_id` sobre a família.

Comando (banco de pé, `docker start msr14`; roda em `output/` de scratch, não toca o
cache do repo):

```
uv run python scripts/sweep_commit_scope.py --json /tmp/sweep_scope.json
```

Distância: por painel, `L1 = Σ_bandas |replicação − artigo|`, dois lados somados, contra
`esem14_fig2.bars_read_px` (leitura em pixel, seção 20) no snapshot `2011-12-31`.

| painel | `root` | `family_project_commits` | `family_project_id` |
|---|---|---|---|
| homebrew | **362.7** (9.5%) | 460.7 (12.1%) | 456.7 (12.0%) |
| paperclip | **37.7** (7.3%) | 45.3 (8.7%) | 45.3 (8.7%) |
| clojure | **10.7** (23.1%) | 10.7 (23.1%) | 10.7 (23.1%) |
| blueprint-css | **0.2** (1.5%) | 1.2 (9.3%) | 1.2 (9.3%) |
| média rel | **10.3%** | 13.3% | 13.3% |

População (replicação/artigo): homebrew `3882 / 3986 / 3987` contra 3810; paperclip
`524 / 536 / 536` contra 519; clojure `49` nos três contra 46; blueprint-css
`13 / 14 / 14` contra 13. Contagem de bandas idêntica nos três escopos, em todos os
painéis (10/16/24/16). O escopo **não** mexe na banda a mais da seção 30.

### 36.1 Por que cai

O sinal está errado. O resíduo do homebrew é **excesso** de gente (+71 em `root`), e
os escopos de família só somam: +104 e +105 pessoas, das quais quase tudo cai no lado
do código (`L1_coding` 233 → 328 / 316). Trazer o histórico do fork faz exatamente o
que se esperaria: promove a discussão a código e cria contribuidor onde não havia.
Isso é o oposto do que o alvo pede. Não existe ajuste de escopo que subtraia.

O `blueprint-css` volta a servir de trava, como nas seções 33 e 34: é o painel que a replicação
acerta (`L1=0.19`, dentro do ±1 pessoa/barra da leitura em pixel), e os dois escopos
de família o quebram, inventando 1 pessoa no lado do código. Uma regra que estraga o
painel exato para piorar os outros três não é candidata.

O `clojure` é insensível aos três escopos (`L1=10.66` idêntico, até a casa decimal):
o resíduo dele é forma dentro das bandas 20/21 (seção 23, seção 25), não cobertura de commit.

### 36.2 `family_project_commits` x `family_project_id`

Empate técnico, e a diferença é instrutiva: 1 pessoa de população, mas 8 pessoas
trocam de lado (`L1_non_coding` 132.4 → 140.4, `L1_coding` 328.3 → 316.3). São
commits que aparecem em `project_commits` da família sem que `commits.project_id`
aponte para ela. Diferença real entre as duas tabelas, irrelevante para a decisão.

### 36.3 Decisão

`commit_scope` fica em **`root`** em `config/settings.yaml`, agora como escolha
**medida** e não herdada. É o melhor dos três em todos os quatro painéis, e o único
que preserva a trava do blueprint-css. Oitava hipótese testada para o resíduo do
homebrew (seção 33, seção 34, seção 36), oitava refutada. Os painéis seguem em `363 / 38 / 11 / 0`.

## 37. O extract não era determinístico: 1 parquet em 90 mudava de md5 entre importações do dump

### 37.1 Como apareceu

Teste de instalação do zero (banco recém-importado do dump, `make clean && make run-all`),
comparando os 362 artefatos contra a execução anterior por md5:

```
361/362 parquets md5-idênticos; difere: output/extract/79163.parquet
```

Os JSON de manifesto e os PDF diferem por timestamp/metadata de data embutidos,
o que é esperado e irrelevante. O parquet, não: é dado.

### 37.2 O que era

Não é diferença de dado. É diferença de **ordem das linhas**:

```
uv run python -c "import pandas as pd; \
a=pd.read_parquet('/tmp/ref_antes/output_ref/extract/79163.parquet'); \
b=pd.read_parquet('output/extract/79163.parquet'); \
print(a.shape, b.shape, a.equals(b), \
a.sort_values(list(a.columns)).reset_index(drop=True).equals( \
b.sort_values(list(b.columns)).reset_index(drop=True)))"
# (250243, 4) (250243, 4) False True
```

Mesmas 250 243 linhas, mesmo conteúdo, 3 066 linhas em posição diferente, todas no
bloco `pull_request_comments`. Causa: as queries de `sources/msr14.py` não têm
`ORDER BY`, então o InnoDB devolve as linhas na ordem física da tabela, que depende de
como o dump foi importado. Dois bancos com os mesmos dados podem devolver ordens
diferentes. `79163` (`mxcl/homebrew`) é o único dos 90 grande o bastante para o plano
de execução variar.

### 37.3 Por que não contaminou nenhum resultado

Todos os estágios a jusante (classify, snapshots, metrics, attractiveness, projection,
plots, validate) agregam ou reordenam, e são invariantes à ordem de entrada. Confirmado
por md5: com a ordenação canônica ligada, os parquets de `extract` mudam (ordem nova) e
**todo o resto do pipeline continua bit-a-bit idêntico**. Nenhum número deste relatório
jamais dependeu disso.

### 37.4 Correção

Ordem canônica por `(scope_id, contributor_id, timestamp, event_type)` com
`kind="mergesort"` (estável) antes de escrever o parquet, em `extract.py`, fora do SQL,
para respeitar a regra de que SQL só existe em `src/pyramid/sources/`, e para valer para
qualquer fonte futura, não só a MSR14.

O critério de aceite do projeto é reprodutibilidade exata; um artefato cujo md5 muda
entre execuções corretas quebra qualquer verificação por hash, mesmo sem alterar um
número sequer. Era uma armadilha esperando quem tentasse conferir a replicação por
checksum.

### 37.5 Desfecho do teste de instalação do zero

Sequência completa, sem nenhum artefato pré-existente e sem o banco do usuário:
dump baixado do Zenodo → `scripts/prepare_dataset.sh` (bind mount read-only) →
container MariaDB novo (`DATASET_SOURCE=local`, porta 3307) → sanity check dos 90
projetos por `COUNT(*)` → `make clean && make run-all` → `make validate`.

```
90 projetos raiz confirmados no banco recém-importado
run-all: 8 estágios, 0 falhas (extract 90/90, classify 90/90, snapshots 90/90,
         metrics 90/90, attractiveness, projection, plots 8 figuras + tabelas)
validate: 167 checks (87 gate, 80 informativos): ok=97, conhecida=70, falha=0
```

`output/validation_report.md` do run do zero é **idêntico linha a linha** ao da execução
de referência, com uma única diferença: a linha de timestamp de geração do próprio
relatório. Com a correção de seção 37.4, os 362 artefatos passaram a bater por md5 (fora
JSON de manifesto e metadata de PDF, que carregam data de geração).

---

## 38. Onde mora o resíduo dos Tipos A-D: 4 projetos grandes, A↔C

### 38.1 O resíduo não é difuso

Somado, o desvio dos Tipos A-D em 2013-09-30 é pequeno (L1=9 em 85 projetos) e
parece ruído espalhado. Decompondo pelo corte de elegibilidade do próprio artigo
(>100 contribuidores, o subconjunto da Fig.7/Tab.3), ele se concentra:

| subconjunto | replicação A/B/C/D | artigo | L1 |
|---|---|---|---|
| todos | 26/40/15/4 (n=85) | 23/42/18/3 (n=86) | 9 |
| **elegíveis (>100 contrib.)** | **8/19/5/2 (n=34)** | **4/21/9/2 (n=36)** | **10** |
| não elegíveis | 18/21/10/2 (n=51) | 19/21/9/1 (n=50) | 3 |

O L1 total (9) é *menor* que o do subconjunto elegível (10) porque os erros se
cancelam entre os dois grupos, e o agregado escondia o problema. Lido direito: os
projetos pequenos batem quase de graça e **4 projetos grandes que classificamos
como A o artigo classifica como C**. B e D estão certos (as 2 unidades de B são
os 2 projetos que faltam na elegibilidade, seção 34).

### 38.2 Não é empate na fronteira

Se fosse arredondamento/desempate, os candidatos a virar C estariam colados no
NCR=0. Não estão. NCR dos elegíveis, ordenado:

```
C do artigo e nossos:  -0.47 -0.45 -0.36 -0.34 -0.25
nossos A:              +0.08 +0.10 +0.23 +0.32 +0.33 +0.36 +0.51 +0.63
```

Há um vão vazio entre −0.25 e +0.08. Mover 4 projetos exige virar gente com NCR
até ≈+0.33 (ex.: 140 novatos vs 95 experientes), ou seja, reclassificar ~25-30%
dos novatos como experientes. Isso é diferença de definição, não de precisão.

### 38.3 Janela de morte por silêncio: REFUTADA (e confirma os 3 meses)

Hipótese: o artigo mediria a Fig.5 com janela de vivo maior que 3 meses (há
precedente: a Fig.2 do ESEM14 só encaixa com 12 meses, seção 19), o que engordaria o
lado experiente e justamente nos projetos grandes. Varredura com todo o resto
fixo (`/tmp/sweep_janela.py`, multiplicando `periods.inactivity_months`):

```
janela |     TODOS   n  L1 | ELEGÍVEIS  n  L1
    3m | 26/40/15/4  85   9 |  8/19/5/2 34  10   <- em vigor
    6m |  3/2/34/49  88 122 | 0/0/11/23 34  48
   12m |  1/0/31/57  89 131 |  0/0/7/27 34  52
   24m |  0/0/35/55  90 134 |  0/0/7/27 34  52
  sem  | 0/0/34/56  90 134 |  0/0/7/27 34  52
ARTIGO | 23/42/18/3  86   0 |  4/21/9/2 36   0
```

Refutada com folga: qualquer janela acima de 3 meses colapsa tudo em C+D e
destrói os 65 projetos novato-dominantes (A+B) que o artigo tem. **Isso é prova
positiva de que a Fig.5 usa a janela de 3 meses**. A janela de 12 meses da Fig.2
do ESEM14 é local daquela figura e não se propaga.

### 38.4 Elegibilidade por população viva: REFUTADA

Hipótese: ">100 contributors" seria sobre a população viva no snapshot, não sobre
o histórico. Isso derrubaria justamente 4 dos nossos A (50, 54, 67 e 100 vivos).
Medido: 30 projetos, 5/17/6/2, L1=8. Melhora pouco, erra o n (30 vs 36) e não
fecha A. Fica o critério histórico.

### 38.5 Situação

Aberto e localizado: **4 projetos grandes, eixo A↔C, sob uma definição de
"newcomer" mais generosa que a nossa no artigo**. Já refutados como causa:
`age_basis` (seção 3, seção 19.5), largura de banda (seção 21), janela de vivo (38.3),
elegibilidade (38.4), desempate no zero (seção 35.3). O que sobra são leituras que o
artigo não fixa em lugar nenhum do texto, e nenhuma delas é testável contra os
dados publicados: a Fig.5 dá só o espalhamento, não a lista de projetos por tipo.
Sem essa lista, mais varredura vira ajuste de curva. **Encerrado como ambiguidade
declarada, não como bug.**

### 38.6 Correção de rota nas docstrings

`classify.py` e `snapshots.py` documentavam a idade como "SOMA dos períodos de
atividade", que é exatamente a leitura **refutada** em seção 3 (`accumulated_active`,
L1=62, C e D vazios), enquanto o pipeline roda `calendar_tenure`. Docstring
descrevendo o contrário do código é o pior tipo de dívida num repo cujo produto é
reprodutibilidade. Corrigidas para descrever a regra em vigor e apontar a
alternativa refutada.
