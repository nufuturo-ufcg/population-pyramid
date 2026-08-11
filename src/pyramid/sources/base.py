"""Contrato de entrada da ferramenta.

O resto do pipeline (classify, snapshots, metrics, ...) consome SÓ o DataFrame
padronizado devolvido por `get_events` e os atributos de `scope_meta`. Nenhum
SQL fora de um adaptador. É isso que permite trocar a origem dos dados sem
tocar no motor de cálculo.

Duas coisas formam o contrato:

1. `get_events(scope_id)`: uma linha por evento, colunas de `EVENT_COLUMNS`.
   Grão de pessoa e de tempo. Responde "quem fez o quê e quando".
2. `scope_meta(scope_id)`: atributos do escopo, chaves de `SCOPE_META_KEYS`.
   Responde "o que é esse escopo". É o que permite agrupar os MESMOS eventos
   por outro eixo: a pirâmide por linguagem agrega os escopos que compartilham
   `language`, sem reextrair nada e sem outro adaptador.

Escopo hoje é projeto. A unidade de análise da saída fica em
`config/settings.yaml`, chave `analysis.unit`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

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
# (docs/replicacao/discrepancias.md, seção 17).
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


# Atributos que toda fonte descreve sobre um escopo. São o eixo alternativo de
# agregação: com eles a mesma extração vira pirâmide por projeto ou por
# linguagem. Valor desconhecido é None; chave faltando é erro de adaptador.
#   label      : str  nome legível ("owner/name")
#   language   : str | None  linguagem principal do escopo
#   created_at : pd.Timestamp | None  nascimento do escopo
SCOPE_META_KEYS = ("label", "language", "created_at")


def validate_scope_meta(meta: dict[str, Any], *, scope_id: int) -> dict[str, Any]:
    """Falha alto se o adaptador não descreveu o escopo. Devolve o próprio dict.

    Chave a mais é livre e passa: adaptador pode expor o que a origem dele tem.
    Chave a menos para o motor calado, agregando por um atributo que metade dos
    escopos não tem.
    """
    if faltando := [k for k in SCOPE_META_KEYS if k not in meta]:
        raise ValueError(f"fonte (scope {scope_id}): scope_meta sem {faltando}")
    if not isinstance(meta["label"], str) or not meta["label"]:
        raise ValueError(f"fonte (scope {scope_id}): label vazio em scope_meta")
    lang = meta["language"]
    if lang is not None and not isinstance(lang, str):
        raise ValueError(
            f"fonte (scope {scope_id}): language é {type(lang).__name__}, esperado str"
        )
    nascimento = meta["created_at"]
    if nascimento is not None and not isinstance(nascimento, pd.Timestamp):
        raise ValueError(
            f"fonte (scope {scope_id}): created_at é {type(nascimento).__name__}, "
            f"esperado pandas.Timestamp"
        )
    return meta


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

    def __init__(self, settings: Mapping[str, Any]) -> None:
        """Recebe o settings.yaml já lido.

        O loader instancia a fonte com esse único argumento. O adaptador lê
        daí as chaves que forem dele (host do banco, token da API, variante da
        taxonomia) e guarda o que precisar.
        """
        self._settings = settings

    @abstractmethod
    def list_scopes(self) -> list[int]:
        """IDs dos escopos que o adaptador expõe, em ordem estável.

        Cada adaptador decide o recorte e o documenta. O `msr14` devolve os 90
        projetos raiz do dump.
        """

    @abstractmethod
    def get_events(self, scope_id: int) -> pd.DataFrame:
        """Eventos de um escopo, com as colunas de EVENT_COLUMNS.

        Deve vir sem nulos em contributor_id/timestamp e sem duplicatas exatas.
        A limpeza é responsabilidade da fonte. O consumidor recebe pronto.
        """

    @abstractmethod
    def scope_meta(self, scope_id: int) -> dict[str, Any]:
        """Atributos do escopo, com as chaves de `SCOPE_META_KEYS`.

        É a pirâmide por linguagem que consome isso. Deixar opcional obrigaria
        a refazer a extração inteira toda vez que o eixo de agregação mudasse.
        Valor que a origem não tem vira None.
        """

    def scope_label(self, scope_id: int) -> str:
        """Rótulo legível pra gráfico/log. Default: o próprio id."""
        return str(scope_id)

    def provenance(self) -> dict[str, Any]:
        """Decisões da fonte que mudam os números, gravadas no manifesto.

        Toda escolha que o adaptador faz e que altera o parquet de saída entra
        aqui: variante de taxonomia, recorte de commit, data de corte do dump.
        Duas execuções com manifestos diferentes nesse dicionário não são
        comparáveis. Default: dicionário vazio, para a fonte sem escolha.
        """
        return {}
