# A entrada: contrato de fonte

O pipeline não sabe de onde vêm os dados. Ele recebe eventos de atividade num
formato fechado e trabalha só sobre esse formato. Quem traduz o vocabulário da
origem é a fonte.

Hoje existe uma fonte: `MSR14Source`, que lê o dump MySQL do GHTorrent
(`src/pyramid/sources/msr14.py`). O contrato está em
`src/pyramid/sources/base.py`.

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
`config/settings.yaml`. A fonte não participa dessa decisão: ela só diz qual
evento aconteceu.

Sete tipos, contra os seis que a spec lista na seção 8. O sétimo é `issues`
(abrir uma issue), que existe porque a variante `table1` da taxonomia conta
abertura de issue como não-coding, enquanto a variante `prose` a exclui. Ver
`docs/replicacao/discrepancias.md`, seção 17.

## O que a fonte garante

`validate_canonical_schema()` roda em cima do que a fonte devolve e recusa:

- coluna a mais, a menos ou fora de ordem;
- `contributor_id` que não seja inteiro, `timestamp` que não seja datetime;
- nulo em qualquer coluna;
- `event_type` fora do enum;
- timestamp no futuro.

Limpeza é responsabilidade da fonte. Nulo e duplicata exata saem antes de o
`DataFrame` cruzar a fronteira. O consumidor recebe pronto e não faz `dropna`.

## Escrever uma fonte nova

Herde `ActivityDataSource` e implemente três métodos:

```python
class MinhaFonte(ActivityDataSource):
    def list_scopes(self) -> list[int]:
        """IDs das unidades de análise."""

    def get_events(self, scope_id: int) -> pd.DataFrame:
        """Eventos do escopo, já limpos, nas colunas de EVENT_COLUMNS."""

    def scope_label(self, scope_id: int) -> str:
        """Rótulo legível para gráfico e log. O default é o próprio id."""
```

Regras que valem para qualquer fonte:

1. SQL só dentro de `src/pyramid/sources/`. O hook `sql-so-em-sources` recusa o
   commit que escrever `SELECT` fora daqui.
2. Devolva o `DataFrame` por `validate_canonical_schema(df, scope_id=...)`.
   O teste de contrato (`tests/test_sources_contract.py`) cobra as mesmas
   garantias de qualquer implementação da ABC, uma por teste.
3. `scope_id` é numérico e estável. O escopo nunca é o nome: `symfony` aparece
   duas vezes nos 90 projetos do MSR14.
4. Nada de estado global. A fonte recebe o `settings()` no construtor.

Trocar a fonte hoje é editar `source()` em `src/pyramid/extract.py`, o único
ponto do pipeline que instancia uma implementação concreta. Do `classify` em
diante ninguém sabe de onde o evento veio.

## O que a troca de fonte não muda

Os números de replicação dependem do dump MSR14. Rodar o pipeline sobre outra
fonte gera pirâmides válidas e faz `pyramid validate` divergir de
`config/checkpoints.yaml`, que trava contra os valores dos artigos de Onoue et
al. Comparação com os artigos exige o dump original.
