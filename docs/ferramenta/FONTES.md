# A entrada: contrato de adaptador

O pipeline não sabe de onde vêm os dados. Ele recebe eventos de atividade num
formato fechado e trabalha só sobre esse formato. Quem traduz o vocabulário da
origem é o adaptador.

Cada adaptador é uma pasta em `adapters/<nome>/`, com o `source.py` e os
scripts de preparação daquele dataset. Hoje existe um: `adapters/msr14/`, que
lê o dump MySQL do GHTorrent e traz junto o `prepare_dataset.sh` e o
`docker-compose.yml` do banco. O contrato está em `src/pyramid/sources/base.py`
e o carregador em `src/pyramid/sources/__init__.py`.

Qual adaptador roda vem de `config/settings.yaml`:

```yaml
input:
  adapter: msr14
```

O carregador procura `adapters/<nome>/source.py` e a variável `SOURCE` daquele
arquivo, apontando para a classe. Nome errado falha na hora, com a lista do que
existe.

## O formato canônico de evento

Um evento é uma linha. A fonte entrega um `DataFrame` com estas quatro colunas,
nesta ordem (`EVENT_COLUMNS`):

| coluna | tipo | o que é |
|---|---|---|
| `scope_id` | int64 | unidade de análise. Hoje o `project.id` do dump. |
| `contributor_id` | int64 | pessoa. Hoje o `users.id` do dump. |
| `event_type` | str | um dos sete valores de `EVENT_TYPES`. |
| `timestamp` | datetime64[ns] | quando o evento aconteceu. |

`EVENT_TYPES` é um enum fechado: `commits`, `pull_requests`, `commit_comments`,
`issue_comments`, `pull_request_comments`, `issue_events`, `issues`. A grafia
segue o nome da tabela no dump, no plural, para não invalidar os parquets já
extraídos. Quem separa esses sete tipos em coding, discussion e moved é o
estágio `classify`, por uma variante de taxonomia escolhida em
`config/settings.yaml`. A fonte só diz qual evento aconteceu. A taxonomia fica
fora dela.

Sete tipos, contra os seis que a spec lista na seção 8. O sétimo é `issues`
(abrir uma issue), que existe porque a variante `table1` da taxonomia conta
abertura de issue como não-coding, enquanto a variante `prose` a exclui. Ver
`docs/replicacao/discrepancias.md`, seção 17.

## Os atributos do escopo

`get_events` responde quem fez o quê e quando. `scope_meta(scope_id)` responde o
que é aquele escopo, com as chaves de `SCOPE_META_KEYS`:

| chave | tipo | o que é |
|---|---|---|
| `label` | str | nome legível, `owner/name` no MSR14. |
| `language` | str \| None | linguagem principal do escopo. |
| `created_at` | pd.Timestamp \| None | nascimento do escopo. |

Chave a mais passa: o adaptador expõe o que a origem dele tem. Chave a menos é
erro, e `validate_scope_meta` recusa.

Esses atributos existem para o eixo alternativo de agregação. A pirâmide por
linguagem soma os escopos que compartilham `language`, lendo os mesmos parquets
do `extract`, sem reextrair nada e sem adaptador novo. Por isso `scope_meta` é
método abstrato: adaptador que não descreve o escopo trava o eixo por linguagem
para sempre.

O `extract` grava esses atributos na entrada de cada escopo em
`output/extract/_manifest.json`, ao lado das contagens. `extract.scope_meta()`
devolve o dicionário de volta com o banco desligado, e `extract.labels()` sai
dele. `created_at` vira string ISO na gravação, porque o manifesto é JSON.
Manifesto vazio cai no adaptador, pelo contrato público.

A unidade de análise da saída fica em `config/settings.yaml`:

```yaml
analysis:
  unit: project
```

`project` dá uma pirâmide por escopo do adaptador. `language` soma os escopos
que compartilham `scope_meta.language`, e é o que responde "quem escreve
Clojure" sobre os N repositórios da linguagem. Quem agrupa é
`src/pyramid/units.py`, e nenhum adaptador muda para isso: o eixo sai do
`scope_meta` que a fonte já entrega.

A soma acontece no `extract`, antes do `classify`. Quem mexe em cinco
repositórios da mesma linguagem é uma pessoa só, nascida no evento mais antigo
entre os cinco.

Valor sem agregador para o `extract` na hora, com a lista do que existe
(`config.analysis_unit()`).

Dois estágios declaram em quais unidades valem, na constante `UNIDADES`:
`attractiveness` e `projection` rodam só com `project`, porque comparam cada
escopo com a mediana da amostra ou com um limiar calibrado contra ela. O
`run-all` pula quem não vale na unidade configurada.

## O que a fonte garante

`validate_canonical_schema()` roda em cima do que a fonte devolve e recusa:

- coluna a mais, a menos ou fora de ordem;
- `contributor_id` que não seja inteiro, `timestamp` que não seja datetime;
- nulo em qualquer coluna;
- `event_type` fora do enum;
- timestamp no futuro.

Limpeza é responsabilidade da fonte. Nulo e duplicata exata saem antes de o
`DataFrame` cruzar a fronteira. O consumidor recebe pronto e não faz `dropna`.

## Escrever um adaptador novo

Crie `adapters/<nome>/source.py`, herde `ActivityDataSource`, implemente três
métodos e exponha a classe em `SOURCE`:

```python
class MinhaFonte(ActivityDataSource):
    def list_scopes(self) -> list[int]:
        """IDs das unidades de análise."""

    def get_events(self, scope_id: int) -> pd.DataFrame:
        """Eventos do escopo, já limpos, nas colunas de EVENT_COLUMNS."""

    def scope_meta(self, scope_id: int) -> dict[str, Any]:
        """label, language e created_at do escopo. Passe por validate_scope_meta."""

    def scope_label(self, scope_id: int) -> str:
        """Rótulo legível para gráfico e log. O default é o próprio id."""


SOURCE = MinhaFonte
```

Depois aponte `input.adapter` para `<nome>` no settings.yaml. O script que sobe
ou baixa aquele dataset mora na mesma pasta, e `make check ADAPTER=<nome>` roda
o `adapters/<nome>/prepare_dataset.sh`.

Regras que valem para qualquer adaptador:

1. SQL só dentro de `adapters/`. O hook `sql-so-em-adaptadores` recusa o
   commit que escrever `SELECT` fora daqui.
2. Devolva o `DataFrame` por `validate_canonical_schema(df, scope_id=...)`.
   O teste de contrato (`tests/test_sources_contract.py`) cobra as mesmas
   garantias de qualquer implementação da ABC, uma por teste.
3. `scope_id` é numérico e estável. O escopo nunca é o nome: `symfony` aparece
   duas vezes nos 90 projetos do MSR14.
4. Nada de estado global. A fonte recebe o `settings()` no construtor.

Trocar a fonte é trocar uma linha do settings.yaml. `source()` em
`src/pyramid/extract.py` é o único ponto do pipeline que instancia uma
implementação concreta, e ele pergunta ao carregador. Do `classify` em diante
ninguém sabe de onde o evento veio.

## O que a troca de fonte não muda

Os números do perfil de replicação dependem do dump MSR14. Rodar o pipeline
sobre outra fonte gera pirâmides válidas e faz `pyramid validate` divergir de
`config/checkpoints.yaml`, que trava contra os valores dos artigos de Onoue et
al. Comparação com esses artigos exige o dump original.
