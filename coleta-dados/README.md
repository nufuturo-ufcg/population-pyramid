# Repository Mining Pipeline

Pipeline para mineração e análise de repositórios no GitHub. Suporta múltiplas linguagens via parâmetro `--language`.

## Estrutura

```
├── .env                              # Token do GitHub (não committar)
├── requirements.txt                  # Dependências Python
├── setup.sh                          # Configuração do ambiente
├── run.sh                            # Executa pipeline completo
├── scripts/
│   ├── common.py                     # Infraestrutura compartilhada + registro de linguagens
│   ├── etapa_1_coleta.py             # Etapa 1: Filtragem de repositórios
│   ├── etapa_2A_eventos.py           # Etapa 2A: Coleta via GitHub REST API
│   ├── etapa_2B_eventos.py           # Etapa 2B: Commits via git clone
│   ├── etapa_2_orchestrator.py       # Orquestrador (roda 2A + 2B em paralelo)
│   ├── contar_repos.py               # Contagem de repositórios
│   └── contar_eventos.py             # Contagem de eventos
└── runs/
    └── <run_name>/
        ├── repositorios_<lang>_alvo.csv
        ├── eventos_api.csv           # Saída etapa_2A
        ├── eventos_git.csv           # Saída etapa_2B
        ├── eventos_repositorios.csv  # Merge dos dois
        └── reports/
            ├── etapa_2A_progresso.json
            └── etapa_2B_progresso.json
```

## Pré-requisitos

- Python 3.10+
- Token do GitHub com permissão de leitura

## Configuração

1. Crie o arquivo `.env` na raiz do projeto:

```
GITHUB_TOKEN=seu_token_aqui
```

Para múltiplos tokens (rotação automática em caso de rate limit), adicione um por linha:

```
GITHUB_TOKEN=token_primeiro
GITHUB_TOKEN=token_segundo
GITHUB_TOKEN=token_terceiro
```

Com um único token, o pipeline faz sleep quando atinge rate limit. Na etapa 1, com dois ou mais tokens, o pipeline rotaciona automaticamente para o próximo token ao atingir o limite. Na etapa 2A, com dois ou mais tokens, a coleta roda em paralelo, uma thread por token (ver "Etapa 2 — Coleta de Eventos" abaixo).

2. Execute o setup:

```bash
chmod +x setup.sh run.sh
./setup.sh
```

## Linguagens suportadas

A etapa 2 aceita o parâmetro `--language` para definir a linguagem-alvo. As linguagens disponíveis estão registradas em `scripts/common.py` (`LANGUAGE_CONFIGS`).

| Linguagem | Extensões | Uso |
|-----------|-----------|-----|
| `clojure` | `.clj`, `.cljs`, `.cljc`, `.edn`, `.bb`, `.cljx` | `--language clojure` |
| `elixir` | `.ex`, `.exs`, `.erl`, `.hrl` | `--language elixir` |

Para adicionar uma linguagem nova, edite `LANGUAGE_CONFIGS` em `common.py`.

## Execução

### Pipeline completo

```bash
./run.sh <NOME_DA_RUN> --language <linguagem>
```

Exemplo:

```bash
./run.sh my-run --language elixir
```

### Com limite de repositórios

Para testar com poucos repositórios antes de rodar em todos:

```bash
./run.sh my-run --language elixir --limit 10
```

O `--limit N` emite ordem para as duas etapas:
- **Etapa 1**: para após escrever N repositórios válidos em `repositorios_<lang>_alvo.csv` (repos inválidos não contam)
- **Etapa 2**: processa no máximo N repositórios novos para coleta de eventos (repos já coletados são pulados sem contar)

### Etapas individualmente

```bash
source venv/bin/activate

# Etapa 1: Filtra repositórios do GitHub (com limite)
python scripts/etapa_1_coleta.py runs/my-run --limit 10

# Etapa 2A: Coleta eventos via GitHub REST API
python scripts/etapa_2A_eventos.py runs/my-run --language elixir --limit 10

# Etapa 2B: Coleta commits via git clone
python scripts/etapa_2B_eventos.py runs/my-run --language elixir --limit 10

# Orchestrator: roda 2A + 2B em paralelo
python scripts/etapa_2_orchestrator.py runs/my-run --language elixir --limit 10
```

## Etapas

### Etapa 1 — Filtragem de Repositórios

Busca repositórios no GitHub e aplica filtros metodológicos:
- Mínimo de estrelas, watchers, commits e contribuidores
- Proporção mínima de código da linguagem-alvo
- Análise estrutural (descarta repositórios de documentação/mídia)

**Saída:** `repositorios_<lang>_alvo.csv`

### Etapa 2 — Coleta de Eventos

Para cada repositório aprovado na Etapa 1, coleta 7 tipos de evento:

| Tipo | Fonte | Token necessário? | Descrição |
|------|-------|--------------------|-----------|
| `issue` | API REST | Sim | Issues do repositório |
| `pr` | API REST | Sim | Pull requests que modificam arquivos da linguagem |
| `commit_comment` | API REST | Sim | Comentários em commits |
| `pr_comment` | API REST | Sim | Comentários em pull requests |
| `issue_comment` | API REST | Sim | Comentários em issues |
| `issue_event` | API REST | Sim | Eventos de issues (labels, assigns, etc.) |
| `commit` | git clone | Não | Commits do repositório |

A etapa 2 é dividida em dois scripts paralelos:
- **etapa_2A**: coleta os 6 tipos via GitHub REST API
- **etapa_2B**: coleta commits via git clone (mais eficiente para histórico completo)

Dentro da etapa_2A, quando há mais de um token configurado no `.env`, os repositórios são distribuídos entre threads, uma por token. Cada thread mantém o mesmo token do início ao fim da execução e não rotaciona para outro: se o token de uma thread atingir seu próprio limite de requisições, só aquela thread aguarda o reset, as demais continuam coletando. Com N tokens, o teto agregado de requisições por hora passa a ser N vezes o limite de um único token (5.000/h por token). Com 0 ou 1 token, a etapa_2A roda sequencial, um repositório por vez, como antes.

**Saída:** `eventos_repositorios.csv` (merge dos dois CSVs)

Ambos os CSVs (`eventos_api.csv` e `eventos_git.csv`) compartilham o mesmo schema:

```
repo_id|repo_name|event_type|number|title|author|author_login|author_email|created_at|state|sha|message|url|labels|files|language|collection_status|collection_started_at
```

Na etapa_2A, `author_login` é preenchido com o login do GitHub e `author_email` fica vazio. Na etapa_2B, `author_login` fica vazio e `author_email` é extraído do clone local (sem requisições HTTP).

**Resumibilidade:** O progresso é salvo em `reports/etapa_2A_progresso.json` e `reports/etapa_2B_progresso.json`. Repositórios concluídos são pulados em execuções futuras.

Com a etapa_2A paralela, a ordem das linhas em `eventos_api.csv` segue a ordem de conclusão dos repositórios, não a ordem de entrada em `repositorios_<lang>_alvo.csv`. Quem precisar de ordem estável deve ordenar por `repo_id` ou `created_at` na leitura.

## Dependências

- `requests` — HTTP client
- `python-dotenv` — Variáveis de ambiente
