"""Contrato genérico de ActivityDataSource (seção 8).

Este arquivo não sabe o que é MySQL. Ele pega cada fonte registrada em
`SOURCES`, alimenta com um fixture sintético pequeno e cobra o mesmo formato
canônico de todas. Quando entrar a `GitHubAPISource`, o trabalho é acrescentar
uma linha em `SOURCES`. Se a fonte nova devolver `contributor_id` como string,
ou um `event_type` fora do enum, ou data no futuro, quebra aqui e não três
estágios adiante, na forma de uma pirâmide torta que ninguém sabe explicar.

O fixture inclui de propósito duas linhas podres (contribuidor NULL e data
zerada do dump) para provar que a limpeza é responsabilidade da fonte.
"""

from __future__ import annotations

from collections import namedtuple
from contextlib import contextmanager
from unittest.mock import patch

import pandas as pd
import pytest

from pyramid.sources.base import EVENT_COLUMNS, EVENT_TYPES, ActivityDataSource
from pyramid.sources.msr14 import MSR14Source

SCOPES = [25875, 79163]

# Como o dump devolve: sem scope_id, com sujeira, colunas cruas.
RAW = pd.DataFrame(
    {
        "event_type": ["commits", "commits", "issues", "issues", "commits"],
        "contributor_id": [1.0, 2.0, None, 2.0, 1.0],
        "ts": [
            "2012-03-01 10:00:00",
            "2012-04-02 11:30:00",
            "2012-05-03 09:00:00",
            "0000-00-00 00:00:00",
            "2013-01-04 08:15:00",
        ],
    }
)

SETTINGS = {
    "projects": {"exclude_ids": [], "expected_count": len(SCOPES)},
    "commit_scope": "root",
    "taxonomy": {
        "variant": "v1",
        "variants": {"v1": {"coding": ["commits"], "non_coding": ["issues"]}},
    },
}


_LabelRow = namedtuple("_LabelRow", "id label")


class _FakeEngine:
    """Só precisa saber abrir e fechar uma conexão; o SQL é interceptado."""

    def __init__(self, labels):
        self.labels = labels

    @contextmanager
    def connect(self):
        labels = self.labels

        class Cx:
            def execute(self, _sql):
                return self

            def fetchall(self):
                return labels

        yield Cx()


@contextmanager
def _msr14():
    rows = [
        _LabelRow(25875, "jquery/jquery"),
        _LabelRow(79163, "mxcl/homebrew"),
    ]
    src = MSR14Source(SETTINGS, _FakeEngine(rows))
    # O SQL do MySQL não roda fora do MySQL: substituímos a ida ao banco pelo
    # fixture cru. O que está sob teste é o parser da fonte. O servidor fica fora.
    with patch("pyramid.sources.msr14.pd.read_sql", return_value=RAW.copy()):
        yield src


# Registro de fontes. Adicionar a fonte nova AQUI é o que a torna testada.
SOURCES = {"MSR14Source": _msr14}


@pytest.fixture(params=list(SOURCES), ids=list(SOURCES))
def source(request):
    with SOURCES[request.param]() as src:
        yield src


def test_list_scopes_devolve_ids_unicos(source: ActivityDataSource):
    ids = source.list_scopes()
    assert isinstance(ids, list) and ids
    assert all(isinstance(i, int) for i in ids)
    assert len(set(ids)) == len(ids)


def test_colunas_exatas_e_na_ordem(source):
    df = source.get_events(source.list_scopes()[0])
    assert list(df.columns) == EVENT_COLUMNS


def test_dtypes_canonicos(source):
    df = source.get_events(source.list_scopes()[0])
    assert pd.api.types.is_integer_dtype(df["contributor_id"])
    assert pd.api.types.is_datetime64_any_dtype(df["timestamp"])
    assert pd.api.types.is_integer_dtype(df["scope_id"])


def test_sem_nulos_a_limpeza_e_da_fonte(source):
    df = source.get_events(source.list_scopes()[0])
    assert not df[["contributor_id", "timestamp"]].isna().any().any()
    # As duas linhas podres do fixture não podem ter sobrevivido.
    assert len(df) == 3


def test_event_type_dentro_do_enum(source):
    df = source.get_events(source.list_scopes()[0])
    assert set(df["event_type"]) <= EVENT_TYPES


def test_scope_id_e_o_pedido(source):
    sid = source.list_scopes()[-1]
    df = source.get_events(sid)
    assert set(df["scope_id"]) == {sid}


def test_sem_timestamp_no_futuro(source):
    df = source.get_events(source.list_scopes()[0])
    assert df["timestamp"].max() <= pd.Timestamp.now()


def test_sem_duplicata_exata(source):
    df = source.get_events(source.list_scopes()[0])
    assert not df.duplicated().any()


def test_get_events_e_idempotente(source):
    sid = source.list_scopes()[0]
    pd.testing.assert_frame_equal(source.get_events(sid), source.get_events(sid))


def test_scope_label_sempre_string_nao_vazia(source):
    for sid in source.list_scopes():
        rotulo = source.scope_label(sid)
        assert isinstance(rotulo, str) and rotulo.strip()
