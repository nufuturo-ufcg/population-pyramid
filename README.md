# pyramid

Ferramenta que desenha pirâmides demográficas de população de software. Ela
recebe eventos de atividade num formato canônico, monta a pirâmide de cada
escopo em cada data pedida, calcula as métricas de população e gera as figuras
e tabelas.

De onde vêm os eventos é problema de um adaptador, uma pasta em `adapters/`.
Hoje existe `adapters/msr14`, que lê o dump MySQL do GHTorrent. Outro dataset
entra como outra pasta, sem tocar no motor de cálculo.

O método vem de dois artigos de Onoue et al., e os dois estão implementados por
inteiro:

- **ESEM14**, *"Investigating and Projecting Population Structures in Open
  Source Software Projects"*: bandas etárias, magnetismo/stickiness,
  quadrantes Atrativo / Flutuante / Estagnado / Terminal.
- **IEICE16**: versão estendida, com Tipos A-D, projeção cohort-component,
  ABRE/MRE/MER + Wilcoxon.

Rodar a ferramenta sobre o dump MSR14 reproduz os números publicados nos dois.
Essa replicação é o teste de aceite da implementação e está documentada em
`docs/replicacao/`, com os PDFs de referência em `docs/replicacao/papers/`.

## Nunca viu isso antes

`docs/ferramenta/COMO_FUNCIONA.md`: o que a ferramenta faz e por quê, sem código
e sem fórmula. Comece por aí. `docs/README.md` mapeia todos os documentos e diz
quando cada um muda.

## Antes de mexer

Leitura obrigatória, nesta ordem:

1. `CONTRIBUTING.md`: as regras de trabalho no repo. Vence sobre qualquer
   outra doc em caso de conflito.
2. `docs/ferramenta/FONTES.md`: contrato de entrada e como escrever um
   adaptador novo.
3. `docs/replicacao/discrepancias.md`: log vivo das ambiguidades investigadas.
   Toda entrada cita o comando/query exato usado, além do número obtido.
4. `docs/replicacao/RESUMO_EXECUTIVO.md`: o que bate com os artigos, o que não
   bate, e por quê.

## Entrada

Um evento é `scope_id`, `contributor_id`, `event_type`, `timestamp`. O
adaptador entrega esse `DataFrame` e descreve cada escopo (rótulo, linguagem,
data de criação). O contrato inteiro, com as garantias que a fonte precisa
cumprir, está em `docs/ferramenta/FONTES.md`.

Qual adaptador roda e qual é a unidade de análise saem de `config/settings.yaml`:

```yaml
input:
  adapter: msr14
analysis:
  unit: project
```

`project` é a unidade aceita hoje. Os atributos de escopo já viajam no
manifesto do `extract` para que o eixo por linguagem entre depois como outro
valor de `analysis.unit`, sobre os mesmos parquets e sem adaptador novo.

## Dados do adaptador msr14

O dump tem 423 MB e **nunca entra no repo**. `DATASET_DIR` é a cópia de trabalho
do usuário: o pipeline monta o dump por bind mount **read-only** e não escreve,
move nem apaga nada lá dentro.

Três modos, via `DATASET_SOURCE` no `.env` (ver `.env.example`):

| modo | o que faz |
|---|---|
| `existing_db` | banco já rodando e importado; o pipeline só conecta (default) |
| `local` | pasta com o dump já extraído; o compose sobe o banco e importa |
| `download` | baixa o zip do Zenodo, extrai e importa |

## Uso

Requer Python 3.12 e [uv](https://docs.astral.sh/uv/). Docker só entra nos
modos `local` e `download`.

```bash
make setup DATASET_DIR=/caminho/absoluto   # .env, deps (uv) e hooks de git
make check                                 # valida a fonte de dados
make run-all                               # pipeline inteiro
make validate                              # compara com config/checkpoints.yaml
make test                                  # testes (173, ~2 s, sem banco)
make qa                                    # o que a CI roda: prek + testes
```

`make help` lista todos os alvos e `uv run pyramid --help` lista todos os
comandos, com as flags de cada um. Os dois são a referência completa.

`make check ADAPTER=<nome>` roda o `prepare_dataset.sh` daquele adaptador.

Estágios individuais, na ordem: `extract` → `classify` → `snapshots` →
`metrics` → `attractiveness` → `projection` → `plots`, depois `validate`.
Cada estágio é retomável e grava checkpoint; ver `CONTRIBUTING.md`, seção
"Contrato de estágio".

Figuras e tabelas exigidas (`docs/replicacao/METODO.md`, seção 7) saem em
`output/plots/`, com
`_manifest.json` declarando o que foi gerado com sucesso.

Rodar o mesmo estágio duas vezes gera os mesmos bytes. PNG, PDF, CSV e
parquet saem idênticos e o `git status` fica limpo. A única exceção é o campo
`updated_at` dentro de cada `_manifest.json`, que registra a hora da execução.
Comparação por checksum entre duas rodadas ignora esse campo.

### Janela de tempo

`--inicio` e `--fim` cortam a série de snapshots e valem para a execução
inteira. Vêm antes do subcomando:

```bash
uv run pyramid --inicio 2011-01-01 --fim 2012-12-31 run-all
uv run pyramid --inicio 2010-01-01 snapshots
```

Sem as duas, vale a janela de `config/settings.yaml`, que é a dos artigos. A
leitura do banco continua inteira: a janela corta a série depois, então o mesmo
`extract` serve a qualquer recorte.

Janela pedida na CLI reancora as datas das figuras no fim da série e registra o
deslocamento no log. Começo depois do fim aborta, e janela que não cobre três
fins de trimestre também: a projeção precisa de três âncoras.

### Execução isolada

Para experimentar sem sujar a saída canônica, `run-all`, `plot` e `validate`
aceitam `--run` e `--rotulo`:

```bash
uv run pyramid plot --figure pyramid-grid-types --rotulo hipotese-x
uv run pyramid validate --rotulo hipotese-x
```

Os entregáveis (figuras, tabelas, relatório) vão para
`output/runs/<AAAAMMDD-HHMMSS>-<rotulo>/`, e `output/runs/latest` aponta para a
última. Cada pasta leva um `_run.json` com comando, commit, `DATASET_SOURCE` e
horário, o bastante para saber de onde a figura veio.

Os parquets de estágio continuam em `output/<estágio>/` mesmo com `--run`. Eles
são a entrada do estágio seguinte, lida por caminho fixo, e movê-los quebraria
a cadeia. A execução isolada guarda os entregáveis.

## Vai codificar aqui

`CONTRIBUTING.md`: ambiente, hooks, o que a CI cobre, o que fazer quando uma
mudança mexe em número publicado, formato de commit e regras de escrita.

Qualidade roda em quatro camadas: `ruff` (lint e formato), `mypy` (tipos em
`src/`), `prek` (hooks de git) e `pytest`. A CI está em
`.github/workflows/ci.yml` e em `.gitlab-ci.yml`, com os mesmos comandos nos
dois. Nenhum commit leva coautoria de assistente: o hook de `commit-msg`
recusa.

## Regras que já custaram caro

- Escopo é sempre por `project.id`. Não use `name`: `symfony` aparece
  duas vezes nos 90.
- Nunca usar `information_schema.table_rows` para sanity check. Use sempre `COUNT(*)`.
- SQL só dentro de `adapters/` e de `src/pyramid/sources/`.
- **2013 é right-censored** (o dump acaba em out/2013): **renderiza pirâmide e
  fica sem quadrante**. Forma é estoque, olha para trás e escapa da censura.
  Stickiness é fluxo e exige Y+1, que o dump não tem. O ESEM14 faz o mesmo com
  o mesmo corte. Ver docs/replicacao/discrepancias.md, seção 11.1. Não anualizar 9 meses
  para forçar classificação.
- Reprodutibilidade exata é o critério de aceite. Número que não bate se resolve
  como bug ou como ambiguidade declarada. Arredondar para ficar perto está
  proibido.

## Licença

Código, configuração e documentação escrita: MIT, ver `LICENSE`.

Os PDFs em `docs/replicacao/papers/` e os recortes em
`docs/replicacao/figuras/artigo/` são dos autores e das editoras (IEICE, ACM).
Estão aqui como referência de estudo e seguem os direitos originais. O dataset
MSR14 tem licença própria e nunca entra neste repositório: ver seção Dados do
adaptador msr14.
