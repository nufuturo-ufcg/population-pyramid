# Clojure Repository Mining Pipeline

Pipeline para mineração e análise de repositórios Clojure no GitHub.

## Estrutura

```
├── .env                          # Token do GitHub (não committar)
├── requirements.txt              # Dependências Python
├── setup.sh                      # Configuração do ambiente
├── run.sh                        # Executa pipeline completo
├── etapa_1_coleta.py             # Etapa 1: Filtragem de repositórios
├── etapa_2_eventos.py            # Etapa 2: Coleta de eventos
├── repositorios_clojure_alvo.csv # Saída Etapa 1
├── eventos_repositorios.csv      # Saída Etapa 2
└── reports/
    └── etapa_2_eventos_progresso.json
```

## Pré-requisitos

- Python 3.10+
- Token do GitHub com permissão de leitura

## Configuração

1. Crie o arquivo `.env` na raiz do projeto:

```
GITHUB_TOKEN=seu_token_aqui
```

2. Execute o setup:

```bash
chmod +x setup.sh run.sh
./setup.sh
```

## Execução

### Pipeline completo

```bash
./run.sh
```

### Etapas individualmente

```bash
source venv/bin/activate

# Etapa 1: Filtra repositórios Clojure do GitHub
python etapa_1_coleta.py

# Etapa 2: Coleta issues, PRs e commits com código Clojure
python etapa_2_eventos.py
```

## Etapas

### Etapa 1 — Filtragem de Repositórios

Busca repositórios Clojure no GitHub e aplica filtros metodológicos:
- Mínimo de estrelas, watchers, commits e contribuidores
- Proporção mínima de código Clojure
- Análise estrutural (descarta repositórios de documentação/mídia)

**Saída:** `repositorios_clojure_alvo.csv`

### Etapa 2 — Coleta de Eventos

Para cada repositório aprovado na Etapa 1, coleta:
- **Issues** — todas, sem filtro
- **Pull Requests** — apenas os que modificam arquivos `.clj`, `.cljs`, `.cljc`, `.edn`, `.bb`, `.cljx`
- **Commits** — apenas os que modificam arquivos Clojure

**Saída:** `eventos_repositorios.csv`

**Resumabilidade:** O progresso é salvo em `reports/etapa_2_eventos_progresso.json`. Repositórios concluídos são pulados em execuções futuras.

## Dependências

- `requests` — HTTP client
- `python-dotenv` — Variáveis de ambiente
