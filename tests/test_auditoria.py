"""Auditoria dos CSV brutos: repositórios duplicados e issues anteriores ao lançamento."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.coleta_csv import auditoria

COLUNAS = [
    "repo_id", "repo_name", "event_type", "number", "title", "author", "author_login",
    "author_email", "created_at", "state", "sha", "message", "url", "labels", "files",
    "language", "collection_status", "collection_started_at",
]  # fmt: skip


def _issue(repo, numero, autor, data, titulo):
    linha = dict.fromkeys(COLUNAS)
    linha.update(
        repo_id=repo, event_type="issue", number=numero, author_login=autor,
        created_at=data, title=titulo,
    )  # fmt: skip
    return linha


def test_acha_o_par_duplicado_e_as_issues_anteriores_ao_lancamento(tmp_path):
    linhas = []
    for n in range(1, 6):
        # Os repositórios 1 e 2 têm as mesmas 5 issues. O 3 tem outras 5.
        linhas.append(_issue("1", str(n), "ana", f"2012-01-0{n}T00:00:00Z", f"titulo {n}"))
        linhas.append(_issue("2", str(n), "ana", f"2012-01-0{n}T00:00:00Z", f"titulo {n}"))
        linhas.append(_issue("3", str(n), "bob", f"2013-01-0{n}T00:00:00Z", f"outro {n}"))
    linhas.append(_issue("3", "9", "cris", "2008-06-01T00:00:00Z", "migrada"))
    arquivo = tmp_path / "eventos_api.csv"
    pd.DataFrame(linhas, columns=COLUNAS).to_csv(arquivo, sep="|", index=False)

    con = auditoria.conecta(tmp_path / "trabalho", memoria="1GB", threads=1)
    auditoria.cria_api(con, [(arquivo, "api")])
    pares = auditoria.pares_duplicados(con, minimo_em_comum=3)
    assert len(pares) == 1
    assert (pares.loc[0, "repo_a"], pares.loc[0, "repo_b"]) == ("1", "2")
    assert pares.loc[0, "fracao_do_menor"] == 1.0
    assert pares.loc[0, "titulo_igual_pct"] == 100.0

    antes = auditoria.issues_antes_do_lancamento(con)
    assert antes["author_login"].tolist() == ["cris"]


def test_contas_traz_eventos_e_repositorios_das_contas_com_padrao(tmp_path):
    linhas = []
    for repo in ["1", "2"]:
        linhas.append(_issue(repo, "1", "twisted-trac", "2012-01-01T00:00:00Z", "a"))
    linhas.append(_issue("1", "2", "tracy", "2012-01-02T00:00:00Z", "b"))
    linhas.append(_issue("1", "3", "dependabot-preview", "2012-01-03T00:00:00Z", "c"))
    arquivo = tmp_path / "eventos_api.csv"
    pd.DataFrame(linhas, columns=COLUNAS).to_csv(arquivo, sep="|", index=False)
    con = auditoria.conecta(tmp_path / "trabalho", memoria="1GB", threads=1)
    auditoria.cria_todos(con, [(arquivo, "api")])
    t = auditoria.contas(con, maiores=1).set_index("conta")
    assert t.loc["twisted-trac", "eventos"] == 2
    assert t.loc["twisted-trac", "repositorios"] == 2
    assert "dependabot-preview" in t.index  # bot sem [bot]
    assert "tracy" in t.index  # a busca solta pega, a regra de palavra inteira não
