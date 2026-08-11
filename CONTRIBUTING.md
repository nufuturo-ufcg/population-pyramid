# Como contribuir

Este repositório reproduz números publicados. O critério de aceite é
reprodutibilidade exata. Toda mudança que mexe em número precisa dizer qual
número mudou e por quê.

Leia o README antes. Leia `INSTRUCOES_CLAUDE_CODE.MD` antes de mexer em
qualquer estágio do pipeline: é a fonte da verdade e vence sobre qualquer
outra doc em caso de conflito.

## Ambiente

Requer Python 3.12 e [uv](https://docs.astral.sh/uv/). Docker só é necessário
nos modos `local` e `download` de `DATASET_SOURCE`.

```bash
make setup DATASET_DIR=/caminho/absoluto
```

`make setup` cria o `.env`, instala as dependências e instala os hooks de git.
São três tipos de hook: `pre-commit`, `commit-msg` e `pre-push`. Se você clonou
sem rodar `setup`, `make hooks` instala só eles. Sem hook instalado, a CI vira
o primeiro lugar onde você descobre um problema que o hook pegaria em dois
segundos.

## Comandos

```bash
make lint       # ruff check
make fmt        # ruff format
make types      # mypy em src/
make test       # pytest
make qa         # hooks do prek em todos os arquivos, mais os testes
make check      # valida a fonte de dados antes de rodar o pipeline
make run-all    # pipeline inteiro
make validate   # compara a saída com config/checkpoints.yaml
```

`make qa` roda o mesmo conjunto que a CI roda.

Experimento que não deve sujar `output/` vai com `--rotulo`:

```bash
uv run pyramid run-all --rotulo minha-hipotese
```

Os entregáveis caem em `output/runs/<carimbo>-minha-hipotese/`, com `_run.json`
registrando comando e commit. Só o `git diff` da saída canônica conta como
mudança de número publicado, e a seção "Mudança que mexe em número" continua
valendo para ele.

## O que os hooks barram

| hook | quando | o que recusa |
|---|---|---|
| `ruff-check`, `ruff-format` | pre-commit | lint e formatação fora do padrão |
| `mypy` | pre-commit | `src/` sem anotação de tipo ou com tipo errado |
| `sql-so-em-adaptadores` | pre-commit | `SELECT`/`FROM`/`JOIN` fora de `adapters/` e `src/pyramid/sources/` |
| `check-added-large-files` | pre-commit | arquivo acima de 2 MB |
| `sem-assinatura-de-assistente` | commit-msg | coautoria de assistente, assunto acima de 72 caracteres, corpo colado no assunto |
| `pytest` | pre-push | suíte quebrada |

Nenhum commit deste repositório leva `Co-authored-by` de assistente nem linha
de propaganda de ferramenta. A autoria do commit é de quem assina.

## Testes

146 testes, 2 s de suíte inteira. Rodam sem dump e sem banco.

Quatro categorias:

- **Contrato de fonte** (`test_sources_contract.py`, `test_sources.py`): a
  query certa é a query que o artigo pede. Roda contra fake engine.
- **Unidade de cálculo** (`test_classify.py`, `test_snapshots.py`,
  `test_validate.py`, `test_attractiveness.py`, `test_plots.py`): fórmula,
  arredondamento, borda de banda etária, censura de 2013.
- **Checkpoint** (`@pytest.mark.checkpoint` em `test_projection.py` e
  `test_attractiveness.py`): a saída do pipeline vive na ordem de grandeza da
  célula publicada. Estes dão `skip` quando o parquet do estágio não existe,
  que é o caso de um clone limpo.
- **Hooks** (`test_hooks.py`): o hook de SQL e o de mensagem de commit dão o
  mesmo veredito com caminho relativo e com caminho absoluto, pegam `SELECT` de
  verdade e deixam passar a palavra `select` em prosa. Este arquivo guarda SQL
  de exemplo, então está nomeado como isento dentro do próprio hook.

```bash
uv run pytest -q                      # tudo
uv run pytest -m checkpoint           # só os de ordem de grandeza
uv run pytest -m "not checkpoint"     # só os que nunca precisam do pipeline
```

Teste de checkpoint existe porque a pirâmide acumulada saiu com ABRE de 0.006
contra o intervalo publicado de [0.18, 1.0] e nada no repositório reclamou. A
faixa é frouxa de propósito. O dataset tem 34 projetos elegíveis contra 36 do
artigo, então a comparação célula a célula não fecha. O que não pode acontecer
é o erro sumir.

## O que a CI cobre

`.github/workflows/ci.yml` e `.gitlab-ci.yml` rodam os mesmos comandos: ruff,
mypy, prek e pytest.

O dump de 423 MB não entra na CI. Isso deixa de fora a validação contra
`config/checkpoints.yaml`, que exige o pipeline rodado por inteiro. Rode
`make run-all && make validate` na sua máquina antes de abrir merge request que
toque em qualquer estágio, e cole a linha de diferença do
`output/validation_report.md` na descrição.

## Mudança que mexe em número

1. Rode o pipeline antes e depois. Guarde os dois `validation_report.md`.
2. Se o número mudou, decida entre bug e ambiguidade do artigo.
3. Bug vira correção com teste que falha sem ela.
4. Ambiguidade vira entrada em `docs/replicacao/discrepancias.md`, com o comando ou a
   query exata que produziu o número, além do valor obtido.
5. Se o valor esperado mudou de vez, atualize `config/checkpoints.yaml` no
   mesmo commit da correção, nunca antes.

Arredondar para ficar perto está proibido.

## Escrita

Vale para doc, comentário, docstring e mensagem de commit.

- Sem travessão (`—` e `–`). Use ponto, vírgula, dois-pontos ou parênteses.
- Sem o símbolo `§`. Escreva "seção 12.3".
- Sem estrutura antitética ("é X, não Y", "não é X, é Y", "mais A do que B"
  como retórica). Afirme direto o que é. Se a alternativa descartada importa,
  ela vira frase própria, com o motivo de ter caído.
- Documento curto. Cada linha carrega um fato.
- "Replicação", nunca "réplica".

Ruim: "O desvio não é difuso, está em 4 projetos grandes."
Bom: "O desvio se concentra em 4 projetos grandes."

## Commits

Assunto no imperativo, até 72 caracteres, linha em branco antes do corpo.
O corpo explica o motivo. O diff já mostra o que mudou.

```
corrige banda etária no limite superior

A borda usava `>=` nos dois lados e contava o contribuidor em duas
bandas. Tabela 2 do IEICE16 voltou a bater.
```

## Layout

| caminho | o que é |
|---|---|
| `src/pyramid/sources/` | único lugar onde pode haver SQL |
| `src/pyramid/` | estágios do pipeline, um módulo por estágio |
| `config/` | `settings.yaml` (parâmetros) e `checkpoints.yaml` (valores esperados) |
| `docs/replicacao/discrepancias.md` | log de ambiguidade investigada |
| `output/` | saída do pipeline, fora do versionamento |
| `scripts/` | investigação pontual e hooks de git |

## Regras que não se renegociam

- Nunca mover, copiar ou apagar nada dentro de `DATASET_DIR`.
- Nunca usar `information_schema.table_rows` para sanity check. Use `COUNT(*)`.
- Nunca escrever SQL fora de `src/pyramid/sources/`.
- Escopo sempre por `project.id`. O nome `symfony` aparece duas vezes nos 90.
- 2013 renderiza pirâmide e fica sem quadrante. Ver `docs/replicacao/discrepancias.md`,
  seção 11.1.
