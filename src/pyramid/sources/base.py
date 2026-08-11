"""Interface de fonte de dados de atividade.

O resto do pipeline (classify, snapshots, metrics, ...) consome SÓ o DataFrame
padronizado devolvido por `get_events`. Nenhum SQL fora deste pacote. Isso é o
que permite, no futuro, plugar um `GitHubAPISource` onde `scope` = linguagem
(agregando N repositórios) em vez de projeto, sem tocar em mais nada.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

# Colunas obrigatórias do DataFrame de eventos:
#   contributor_id : int64 (users.id, ou equivalente na fonte)
#   event_type     : str (um de EVENT_TYPES)
#   timestamp      : datetime64[ns]
#   scope_id       : int64 (projeto hoje; linguagem no futuro)
EVENT_COLUMNS = ["scope_id", "contributor_id", "event_type", "timestamp"]

# Enum fechado. Quem traduz o vocabulário da origem (nomes de tabela do MySQL
# hoje, campos de GraphQL amanhã) para cá é o parser da fonte. De `classify` em
# diante ninguém sabe de onde veio.
#
# São 7 tipos. A spec, na seção 8, lista 6. O sétimo é `issues` (abrir uma
# issue), que existe porque a variante `table1` da taxonomia (IEICE16 Tabela 1)
# conta abertura de issue como não-coding, enquanto a variante `prose` a exclui.
# Os nomes ficam no plural, como no dump, para não invalidar os parquets já
# extraídos. O contrato exige que o conjunto seja fechado. A grafia fica livre
# (docs/discrepancias.md, seção 17).
EVENT_TYPES = frozenset(
    [
        "commits",
        "pull_requests",
        "commit_comments",
        "issue_comments",
        "pull_request_comments",
        "issue_events",
        "issues",
    ]
)


def validate_canonical_schema(df: pd.DataFrame, *, scope_id: int | None = None) -> pd.DataFrame:
    """Falha alto se o DataFrame não é o formato canônico. Devolve o próprio df.

    Roda no fim de todo `get_events()`. A alternativa seria confiar que quem
    escreveu o parser lembrou do contrato. Ela troca um erro aqui por uma
    pirâmide errada três estágios adiante, que ninguém identifica como problema
    de parser.
    """
    onde = f"fonte (scope {scope_id})" if scope_id is not None else "fonte"

    if list(df.columns) != EVENT_COLUMNS:
        raise ValueError(f"{onde}: colunas {list(df.columns)}, esperado {EVENT_COLUMNS}")

    if df.empty:  # escopo sem atividade é legítimo; nada mais a conferir
        return df

    if not pd.api.types.is_integer_dtype(df["contributor_id"]):
        raise ValueError(f"{onde}: contributor_id é {df['contributor_id'].dtype}, esperado inteiro")

    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        raise ValueError(f"{onde}: timestamp é {df['timestamp'].dtype}, esperado datetime")

    nulos = df[["contributor_id", "timestamp"]].isna().sum()
    if nulos.any():
        raise ValueError(f"{onde}: nulos em {nulos[nulos > 0].to_dict()}; limpeza é da fonte")

    fora = sorted(set(df["event_type"].unique()) - EVENT_TYPES)
    if fora:
        raise ValueError(f"{onde}: event_type fora do enum: {fora}")

    # Data no futuro sai de defeito de parser: fuso trocado, epoch zerado.
    ts = df["timestamp"]
    agora = pd.Timestamp.now(tz=ts.dt.tz) if ts.dt.tz else pd.Timestamp.now()
    if futuros := int((ts > agora).sum()):
        raise ValueError(f"{onde}: {futuros} timestamps no futuro (máx {ts.max()})")

    return df


class ActivityDataSource(ABC):
    """Fonte de eventos de atividade de desenvolvimento."""

    @abstractmethod
    def list_scopes(self) -> list[int]:
        """IDs das unidades de análise. Hoje: os 90 projetos raiz."""

    @abstractmethod
    def get_events(self, scope_id: int) -> pd.DataFrame:
        """Eventos de um escopo, com as colunas de EVENT_COLUMNS.

        Deve vir sem nulos em contributor_id/timestamp e sem duplicatas exatas.
        A limpeza é responsabilidade da fonte. O consumidor recebe pronto.
        """

    def scope_label(self, scope_id: int) -> str:
        """Rótulo legível pra gráfico/log. Default: o próprio id."""
        return str(scope_id)
