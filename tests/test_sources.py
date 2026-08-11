"""Contrato da fonte de dados.

O que se trava aqui é o que quebrou em silêncio: `scope_label` só funcionava
depois de `list_scopes` ter sido chamado na mesma instância, e sem isso devolvia
o id como se fosse o nome (docs/replicacao/discrepancias.md seção 14). Um teste que passe pelo
pipeline inteiro não pega isso: o pipeline sempre chama `list_scopes` primeiro.
"""

from __future__ import annotations

from collections import namedtuple
from contextlib import contextmanager

import pytest

from pyramid.sources.msr14 import MSR14Source

Row = namedtuple("Row", "id label")

SETTINGS = {
    "projects": {"exclude_ids": [], "expected_count": 3},
    "commit_scope": "project",
    "taxonomy": {
        "variant": "v1",
        "variants": {"v1": {"coding": ["commits"], "non_coding": ["issues"]}},
    },
}

ROWS = [Row(25875, "jquery/jquery"), Row(78835, "divio/django-cms"), Row(79163, "mxcl/homebrew")]


class FakeEngine:
    """Conta idas ao banco: é isso que a memoização promete evitar."""

    def __init__(self, rows):
        self.rows = rows
        self.queries = 0

    @contextmanager
    def connect(self):
        engine = self

        class Cx:
            def execute(self, _sql):
                engine.queries += 1
                return self

            def fetchall(self):
                return engine.rows

        yield Cx()


@pytest.fixture
def source():
    return MSR14Source(SETTINGS, FakeEngine(ROWS))


def test_scope_label_sem_list_scopes_antes(source):
    # O caso que falhava: primeira chamada da instância é scope_label.
    assert source.scope_label(25875) == "jquery/jquery"
    assert source.scope_label(79163) == "mxcl/homebrew"


def test_scope_label_nao_regride_para_id(source):
    for r in ROWS:
        got = source.scope_label(r.id)
        assert got == r.label
        assert got != str(r.id)


def test_id_desconhecido_vira_string(source):
    # Fallback legítimo: escopo que não é raiz. Não é o bug.
    assert source.scope_label(999999) == "999999"


def test_mapa_carrega_uma_vez_so(source):
    source.scope_label(25875)
    source.scope_label(78835)
    source.list_scopes()
    assert source.engine.queries == 1


def test_list_scopes_ainda_confere_a_contagem():
    src = MSR14Source(SETTINGS, FakeEngine(ROWS[:2]))
    with pytest.raises(RuntimeError, match="esperava 3 projetos raiz"):
        src.list_scopes()


def test_scope_label_nao_depende_da_guarda_de_contagem():
    # Rótulo é cosmético: não deve explodir num banco parcial, só list_scopes deve.
    src = MSR14Source(SETTINGS, FakeEngine(ROWS[:2]))
    assert src.scope_label(25875) == "jquery/jquery"
