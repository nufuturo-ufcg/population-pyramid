# pyramid-replication

Replicação das pirâmides de contribuidores de Onoue et al. sobre o dataset MSR14
(dump GHTorrent de out/2013, 90 projetos):

- **ESEM14**: Onoue et al., *"Investigating and Projecting Population Structures
  in Open Source Software Projects"*: bandas etárias, magnetismo/stickiness,
  quadrantes Atrativo / Flutuante / Estagnado / Terminal.
- **IEICE16**: versão estendida, com Tipos A-D, projeção cohort-component,
  ABRE/MRE/MER + Wilcoxon.

PDFs de referência em `docs/replicacao/papers/`.

## Nunca viu isso antes

`docs/ferramenta/COMO_FUNCIONA.md`: o que a ferramenta faz e por quê, sem código e sem
fórmula. Comece por aí.

## Antes de mexer

Leitura obrigatória, nesta ordem:

1. `INSTRUCOES_CLAUDE_CODE.MD`: spec de implementação. É a fonte da verdade e
   vence sobre qualquer outra doc em caso de conflito.
2. `docs/replicacao/discrepancias.md`: log vivo das ambiguidades investigadas. Toda entrada
   cita o comando/query exato usado, além do número obtido.
3. `docs/replicacao/RESUMO_EXECUTIVO.md`: estado atual do projeto, incluindo o que bate
   com os artigos, o que não bate, e por quê.

## Dados

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
make test                                  # testes (146, ~2 s, sem banco)
make qa                                    # o que a CI roda: prek + testes
```

Estágios individuais, na ordem: `extract` → `classify` → `snapshots` →
`metrics` → `attractiveness` → `project` → `plots` → `validate`.
Cada estágio é retomável e grava checkpoint; ver seção 7.3 da spec.

Figuras e tabelas exigidas (seção 6 da spec) saem em `output/plots/`, com
`_manifest.json` declarando o que foi gerado com sucesso.

Rodar o mesmo estágio duas vezes gera os mesmos bytes. PNG, PDF, CSV e
parquet saem idênticos e o `git status` fica limpo. A única exceção é o campo
`updated_at` dentro de cada `_manifest.json`, que registra a hora da execução.
Comparação por checksum entre duas rodadas ignora esse campo.

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
- SQL só dentro de `src/pyramid/sources/`.
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
MSR14 tem licença própria e nunca entra neste repositório: ver seção Dados.
