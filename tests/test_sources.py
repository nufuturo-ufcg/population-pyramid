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

from pyramid import sources

# O adaptador mora em `adapters/msr14/source.py` e entra pelo loader, do mesmo
# jeito que o pipeline carrega. Importar o arquivo por caminho fixo aqui faria
# o teste passar com um loader quebrado.
MSR14Source = sources.load("msr14")

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


# ---------------------------------------------------------------------------
# Escopo de commit: o JOIN que multiplicava evento
# ---------------------------------------------------------------------------
# `project_commits` tem uma linha por (projeto, commit). O commit que existe na
# raiz e num fork casava uma vez por projeto da família, e o mesmo commit virava
# dois eventos. Nos 90 raízes do dump isso inflava 8,1 % dos commits, em 85
# projetos. O teste roda a consulta de verdade num SQLite de brinquedo: fixar só
# o texto do SQL deixaria passar qualquer reescrita que trouxesse o bug de volta.
# Raiz 1 com fork 2, e o projeto 3 de fora para provar que a família não vaza.
# O commit 10 está na raiz e no fork (a duplicata), o 11 nasceu no fork (é assim
# que chega contribuição de fora, via pull request) e o 12 só na raiz. Os commits
# 10 e 12 são do mesmo autor, e o 12 cai no mesmo dia do 11.
#
# As tabelas são montadas pelo SQLAlchemy, sem SQL escrito aqui: a regra do repo
# é que texto de SQL mora em `adapters/`, e o hook `sql-so-em-adaptadores` cobra.
PROJETOS = [
    {"id": 1, "forked_from": None},
    {"id": 2, "forked_from": 1},
    {"id": 3, "forked_from": None},
]
COMMITS = [
    {"id": 10, "author_id": 100, "created_at": "2013-01-01", "project_id": 1},
    {"id": 11, "author_id": 101, "created_at": "2013-01-02", "project_id": 2},
    {"id": 12, "author_id": 100, "created_at": "2013-01-02", "project_id": 1},
    {"id": 99, "author_id": 999, "created_at": "2013-01-03", "project_id": 3},
]
PROJECT_COMMITS = [
    {"project_id": 1, "commit_id": 10},
    {"project_id": 2, "commit_id": 10},
    {"project_id": 2, "commit_id": 11},
    {"project_id": 1, "commit_id": 12},
    {"project_id": 3, "commit_id": 99},
]


def _banco_de_familia():
    import sqlalchemy as sa

    md = sa.MetaData()
    inteiro = sa.Integer
    projects = sa.Table("projects", md, sa.Column("id", inteiro), sa.Column("forked_from", inteiro))
    commits = sa.Table(
        "commits",
        md,
        sa.Column("id", inteiro),
        sa.Column("author_id", inteiro),
        sa.Column("created_at", sa.Text),
        sa.Column("project_id", inteiro),
    )
    project_commits = sa.Table(
        "project_commits", md, sa.Column("project_id", inteiro), sa.Column("commit_id", inteiro)
    )

    eng = sa.create_engine("sqlite://")
    md.create_all(eng)
    with eng.begin() as cx:
        cx.execute(projects.insert(), PROJETOS)
        cx.execute(commits.insert(), COMMITS)
        cx.execute(project_commits.insert(), PROJECT_COMMITS)
    return eng


def _commits_da_familia(variante: str, sid: int) -> list[tuple]:
    import sys

    import sqlalchemy as sa

    sql = sys.modules[MSR14Source.__module__]._COMMIT_SCOPE_SQL[variante]
    with _banco_de_familia().connect() as cx:
        return [tuple(r) for r in cx.execute(sa.text(sql), {"sid": sid}).fetchall()]


def test_commit_da_familia_nao_conta_duas_vezes():
    linhas = _commits_da_familia("family_project_commits", 1)
    assert len(linhas) == 3
    assert sorted(linhas) == [
        (100, "2013-01-01"),  # commit 10, na raiz e no fork, uma vez só
        (100, "2013-01-02"),  # commit 12, mesmo autor e mesma data do 11
        (101, "2013-01-02"),  # commit 11, só no fork
    ]


def test_familia_nao_colapsa_commits_distintos_do_mesmo_autor():
    """O DISTINCT é do commit, não do par (autor, data).

    Os commits 10 e 12 são do autor 100, e o 12 cai no mesmo dia do 11. Colapsar
    por (autor, data) apagaria atividade real em vez de duplicata.
    """
    linhas = _commits_da_familia("family_project_commits", 1)
    assert sum(1 for autor, _ in linhas if autor == 100) == 2


def test_escopo_raiz_nao_alcanca_commit_que_veio_de_fork():
    """Contraste medido na seção 39.3: `root` perde a contribuição externa.

    O commit 11 foi registrado no fork e chega ao projeto por `project_commits`,
    que é como pull request entra no GitHub. A leitura em vigor não o vê.
    """
    raiz = _commits_da_familia("root", 1)
    familia = _commits_da_familia("family_project_commits", 1)
    assert len(raiz) == 2
    assert len(familia) == 3
    assert (101, "2013-01-02") not in raiz
