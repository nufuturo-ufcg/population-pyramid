# pyramid-replication

Replicação das pirâmides de contribuidores de Onoue et al. sobre o dataset MSR14
(dump GHTorrent de out/2013, 90 projetos):

- **ESEM14** — Onoue et al., *"Investigating and Projecting Population Structures
  in Open Source Software Projects"*: bandas etárias, magnetismo/stickiness,
  quadrantes Atrativo / Flutuante / Estagnado / Terminal.
- **IEICE16** — versão estendida: Tipos A–D, projeção cohort-component,
  ABRE/MRE/MER + Wilcoxon.

PDFs de referência em `docs/papers/`.

## Antes de mexer

Leitura obrigatória, nesta ordem:

1. `INSTRUCOES_CLAUDE_CODE.MD` — spec de implementação. É a fonte da verdade e
   vence sobre qualquer outra doc em caso de conflito.
2. `docs/discrepancias.md` — log vivo das ambiguidades investigadas. Toda entrada
   cita o comando/query exato usado, não só o número.
3. `docs/RESUMO_EXECUTIVO.md` — estado atual: o que bate com os artigos, o que
   não bate e por quê.

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

```bash
make setup DATASET_DIR=/caminho/absoluto   # cria .env e instala deps (uv)
make check                                 # valida a fonte de dados
make run-all                               # pipeline inteiro
make validate                              # compara com config/checkpoints.yaml
make test                                  # testes unitários
```

Estágios individuais, na ordem: `extract` → `classify` → `snapshots` →
`metrics` → `attractiveness` → `project` → `plots` → `validate`.
Cada estágio é retomável e grava checkpoint; ver §7.3 da spec.

Figuras e tabelas exigidas (§6 da spec) saem em `output/plots/`, com
`_manifest.json` declarando o que foi gerado com sucesso.

## Regras que já custaram caro

- Escopo é sempre por `project.id`, **nunca** por `name` — `symfony` aparece
  duas vezes nos 90.
- Nunca usar `information_schema.table_rows` para sanity check; só `COUNT(*)`.
- SQL só dentro de `src/pyramid/sources/`.
- **2013 é right-censored** (o dump acaba em out/2013): renderiza pirâmide, mas
  **não recebe quadrante**. Forma é estoque (olha pra trás, não sofre censura);
  stickiness é fluxo (precisa de Y+1, que não existe). O ESEM14 faz o mesmo com
  o mesmo corte — ver `discrepancias.md` §11.1. Não anualizar 9 meses para
  forçar classificação.
- Reprodutibilidade exata é o critério de aceite: número que não bate é bug ou
  ambiguidade, nunca "arredondar pra ficar perto".
