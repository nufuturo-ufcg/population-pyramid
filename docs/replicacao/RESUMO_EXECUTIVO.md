# Estado do projeto

Retrato de 2026-08-21. Reescrito por completo a cada sessão. O histórico mora em
[`discrepancias.md`](discrepancias.md), que cresce por acréscimo.

O repositório tem duas frentes.

- **Replicação MSR14.** Caso de aceite. Reproduz Onoue et al. sobre o dump do
  GHTorrent e trava o resultado contra `config/checkpoints.yaml`.
- **Pirâmide por linguagem.** Estudo novo. Soma os repositórios de uma
  linguagem numa população só, sobre dados coletados da API do GitHub.

O motor é o mesmo nas duas. O que muda é o adaptador e a unidade de análise.

## Replicação: o placar

```
uv run pyramid validate
167 checks (87 gate, 80 informativos): conhecida=70, ok=97
Sem divergência não declarada.
```

Tipos A-D no snapshot de 2013-09-30, contra a Fig.5 do IEICE16:

| | A | B | C | D | classificados |
|---|---|---|---|---|---|
| artigo | 23 | 42 | 18 | 3 | 86 de 90 |
| replicação | 26 | 40 | 15 | 4 | 85 de 90 |

Erro L1 de 9 tipos. O viés é sistemático e sempre o mesmo: sobra projeto em A,
falta em C. A replicação classifica newcomer demais.

As 70 divergências declaradas se concentram em quatro lugares:

| onde | quantas | o que é |
|---|---|---|
| `projection.abre` | 34 | célula a célula da Tabela 3, 6 de 40 dentro de 2 p.p. |
| `projection.wilcoxon` | 13 | o artigo acha 16 células significativas, a replicação acha 5 |
| `msr14.tab2` | 7 | 48 das 55 células da Tabela 2 batem (87%) |
| `projection.direcao` | 6 | 14 dos 20 pares batem na direção |

Cada uma tem seção própria no `discrepancias.md`, com o comando que produziu o
número. Nenhuma está em aberto sem explicação.

Os artigos admitem mais de uma leitura em seis pontos, numerados no
`settings.yaml`. Todos foram fechados por medição, com o número no
`discrepancias.md` e no comentário da própria chave:

| # | ambiguidade | chave | resolvida em |
|---|---|---|---|
| 1 | taxonomia de evento | `taxonomy.variant` | `prose` |
| 2 | escopo de commit | `commit_scope` | `root` |
| 3 | o que é a idade | `periods.age_basis` | `calendar_tenure` |
| 4 | quem conta na stickiness | `attractiveness.stickiness_scope` | `project` |
| 5 | que população a pirâmide desenha | `plots.pyramid_population` | `active` |
| 6 | identidade do contribuidor | `identity_merge` | `none` |

Duas calibrações saíram de medição em pixel contra a figura impressa, sem
ambiguidade de texto: a banda de 90 dias e a janela da população por artigo.

## Pirâmide por linguagem: o que existe

O adaptador `ghapi` traduz JSON cru da API do GitHub para evento canônico.
Escopo é o par (repositório, linguagem), e `analysis.unit: language` soma os
escopos que compartilham a linguagem.

A soma acontece no `extract`, antes do `classify`. Quem mexe em cinco
repositórios da mesma linguagem é uma pessoa só, nascida no evento mais antigo
entre os cinco.

Amostra de desenvolvimento: `clj-kondo`, `edamame` e `medley`, 34.753 itens
coletados, 27.215 eventos canônicos, 9 escopos (repositório, linguagem) e 6
linguagens. 38 pessoas aparecem em mais de um repositório, de 746 pares para 708
pessoas.

Pirâmide de Clojure em 2026-06-30: CCR +0,652, NCR -0,652, tipo C, com os três
repositórios somados.

## O achado que muda como o resultado se lê

O lado não-código da pirâmide por linguagem é **inteiramente herdado** do
repositório onde a conversa aconteceu.

Evento sem arquivo (abertura de issue e de PR, comentário de issue, issue event,
e o commit que só toca prosa) recebe a linguagem principal do repositório. Com
`language.fallback: unknown` ou `drop`, o lado não-código de Clojure vai de 8
contribuidores para zero, e o CCR salta de 0,652 para 1,000.

Sem a herança esse lado não existe. Quem publicar CCR por linguagem precisa
declarar isso.

Reproduz com `GHAPI_DIR=data/ghapi uv run python scripts/sweep_language_policy.py`.
O mesmo comando mede as outras chaves: `drop_bots: false` leva o CCR de Clojure
para 0,522, e `attribution: repo_languages` apaga a linguagem Shell da amostra.

## O que está travado, e por quê

`attractiveness` e `projection` recusam `analysis.unit: language`, e declaram o
motivo em `UNIDADES`. Magnetismo compara cada escopo com a mediana anual dos
elegíveis, e a mediana de 90 projetos não quer dizer o mesmo que a de N
linguagens. A projeção tem limiar de 100 contribuidores calibrado contra os 36
projetos da Tabela 3, e toda linguagem passa desse corte. `run-all` pula os dois
em vez de falhar.

Figura que reproduz artigo só sai para a fonte declarada em
`output.adapter_da_replicacao`. A composição de cada painel tem projeto e data
fixos do dump MSR14. Para outro dataset essa figura não existe, e a fonte nova
recebe uma pirâmide por escopo.

## Pendente

A coleta grande está sendo feita por outra pessoa. Quando chegar:

```
GHAPI_DIR=/caminho/da/coleta uv run python adapters/ghapi/coleta.py --completar
```

O `--completar` descobre os repositórios pelo campo `url` dos próprios eventos e
busca o que a coleta de evento não produz: `GET /repos`, `GET /languages` e o
clone parcial que dá os caminhos de arquivo.

Depois é trocar `input.adapter` e `analysis.unit` no `settings.yaml`, ajustar a
janela de `snapshots` para o período da coleta, e rodar.

Não há gabarito publicado para pirâmide por linguagem. O que trava o resultado
são os invariantes de soma em `tests/test_units.py`: a soma de eventos fecha, o
contribuidor único não passa da soma dos membros, e quem está em N repositórios
nasce no evento mais antigo entre eles.
