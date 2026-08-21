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

from pyramid import sources
from pyramid.sources.base import (
    EVENT_COLUMNS,
    EVENT_TYPES,
    SCOPE_META_KEYS,
    ActivityDataSource,
)

# Cada adaptador entra pelo loader, pelo nome da pasta em `adapters/`. O loader
# registra o módulo como `pyramid.sources.<nome>`, então o `patch` abaixo
# continua alcançando o `pd.read_sql` de dentro do adaptador.
MSR14Source = sources.load("msr14")

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


_ScopeRow = namedtuple("_ScopeRow", "id label language created_at")


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
        # O segundo escopo vem com language NULL de propósito: atributo que a
        # origem não tem vira None e continua sendo uma chave presente.
        _ScopeRow(25875, "jquery/jquery", "JavaScript", "2010-04-01 12:00:00"),
        _ScopeRow(79163, "mxcl/homebrew", None, None),
    ]
    src = MSR14Source(SETTINGS, _FakeEngine(rows))
    # O SQL do MySQL não roda fora do MySQL: substituímos a ida ao banco pelo
    # fixture cru. O que está sob teste é o parser da fonte. O servidor fica fora.
    with patch("pyramid.sources.msr14.pd.read_sql", return_value=RAW.copy()):
        yield src


@contextmanager
def _ghapi():
    # A coleta mínima mora no teste do adaptador, e é desenhada para cair nas
    # mesmas garantias: 3 eventos limpos de 5 itens crus no primeiro escopo, com
    # um escopo de `language` None no fim.
    from test_ghapi import ghapi_de_teste

    with ghapi_de_teste() as src:
        yield src


# Registro de fontes. Adicionar a fonte nova AQUI é o que a torna testada.
SOURCES = {"MSR14Source": _msr14, "GHAPISource": _ghapi}

# Quantos eventos limpos sobram no primeiro escopo de cada fonte. O fixture cru
# de cada uma traz linha podre de propósito, e este número é o que tem de
# sobreviver. Fonte nova declara o dela aqui.
EVENTOS_LIMPOS = {"MSR14Source": 3, "GHAPISource": 4}


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
    # As linhas podres do fixture não podem ter sobrevivido.
    assert len(df) == EVENTOS_LIMPOS[type(source).__name__]


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


# -- atributos do escopo: o eixo alternativo de agregação --------------------
# Sem estes, trocar a pirâmide de projeto para linguagem exigiria reextrair
# tudo. A extração grava o que scope_meta devolve, e o agregador escolhe depois.


def test_scope_meta_traz_todas_as_chaves(source):
    for sid in source.list_scopes():
        assert set(SCOPE_META_KEYS) <= set(source.scope_meta(sid))


def test_scope_meta_tipos_canonicos(source):
    for sid in source.list_scopes():
        meta = source.scope_meta(sid)
        assert isinstance(meta["label"], str) and meta["label"].strip()
        assert meta["language"] is None or isinstance(meta["language"], str)
        assert meta["created_at"] is None or isinstance(meta["created_at"], pd.Timestamp)


def test_scope_meta_valor_ausente_e_none_e_nao_chave_faltando(source):
    # Escopo sem linguagem registrada na origem. A chave continua lá.
    metas = [source.scope_meta(sid) for sid in source.list_scopes()]
    assert any(m["language"] is None for m in metas)
    assert all("language" in m for m in metas)


def test_scope_meta_label_bate_com_scope_label(source):
    for sid in source.list_scopes():
        assert source.scope_meta(sid)["label"] == source.scope_label(sid)


def test_scope_meta_de_id_desconhecido_nao_quebra(source):
    # Rótulo e atributos são cosméticos para o cálculo: id fora da lista devolve
    # o contrato preenchido com o que dá, sem exceção.
    meta = source.scope_meta(999999)
    assert set(SCOPE_META_KEYS) <= set(meta)
    assert meta["label"] == "999999"
