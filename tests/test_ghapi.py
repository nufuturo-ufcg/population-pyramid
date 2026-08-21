"""Adaptador `ghapi`: atribuição de linguagem e política.

O que está sob teste é o tradutor. A rede fica fora: a coleta é montada em
`tmp_path` com o mínimo que exercita cada decisão, e o formato é o mesmo da
coleta de verdade, um arquivo por busca com os repositórios concatenados.

A coleta mínima é desenhada para o teste de contrato também: o primeiro escopo
sai com os eventos limpos que `EVENTOS_LIMPOS` declara lá, e a coleta traz duas
linhas podres de propósito, uma sem conta do GitHub e uma sem data.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import pytest

from pyramid import sources

GHAPISource = sources.load("ghapi")

# Dois repositórios. O `alpha` tem duas linguagens no mapa de bytes, o `beta`
# tem o mapa vazio, que é o repositório sem linguagem detectada. O `beta` existe
# para o contrato: `scope_meta.language` precisa sair `None` em alguma fonte, com
# a chave presente.
ALPHA, BETA = "acme/alpha", "acme/beta"
API = "https://api.github.com/repos"


def _url(repo: str, resto: str) -> str:
    return f"{API}/{repo}/{resto}"


def coleta_minima(raiz: Path) -> Path:
    """Escreve uma coleta completa e pequena. Devolve a raiz."""
    raiz.mkdir(parents=True, exist_ok=True)

    def grava(nome: str, itens: list[dict]) -> None:
        (raiz / nome).write_text("".join(json.dumps(i) + "\n" for i in itens), encoding="utf-8")

    grava(
        "repos.jsonl",
        [
            {
                "id": 100,
                "full_name": ALPHA,
                "language": "Clojure",
                "created_at": "2019-01-01T00:00:00Z",
            },
            {"id": 200, "full_name": BETA, "language": None, "created_at": "2020-01-01T00:00:00Z"},
        ],
    )
    grava(
        "languages.jsonl",
        [
            {"repo_id": 100, "full_name": ALPHA, "languages": {"Clojure": 900, "Java": 100}},
            {"repo_id": 200, "full_name": BETA, "languages": {}},
        ],
    )

    humano = {"id": 1, "login": "ana", "type": "User"}
    outro = {"id": 2, "login": "bia", "type": "User"}
    robo = {"id": 3, "login": "dependabot[bot]", "type": "Bot"}

    grava(
        "commits.jsonl",
        [
            # toca só Clojure
            {
                "sha": "aaa",
                "url": _url(ALPHA, "commits/aaa"),
                "author": humano,
                "commit": {"author": {"date": "2021-03-01T10:00:00Z"}},
            },
            # toca Clojure e Java: vira dois eventos, um em cada escopo
            {
                "sha": "bbb",
                "url": _url(ALPHA, "commits/bbb"),
                "author": outro,
                "commit": {"author": {"date": "2021-04-01T10:00:00Z"}},
            },
            # PODRE: sem conta do GitHub associada ao e-mail do commit
            {
                "sha": "ccc",
                "url": _url(ALPHA, "commits/ccc"),
                "author": None,
                "commit": {"author": {"date": "2021-05-01T10:00:00Z"}},
            },
            # sem caminho no clone (merge): cai no fallback, que é Clojure
            {
                "sha": "ddd",
                "url": _url(BETA, "commits/ddd"),
                "author": humano,
                "commit": {"author": {"date": "2021-06-01T10:00:00Z"}},
            },
            # bot
            {
                "sha": "eee",
                "url": _url(BETA, "commits/eee"),
                "author": robo,
                "commit": {"author": {"date": "2021-07-01T10:00:00Z"}},
            },
        ],
    )
    grava(
        "issues.jsonl",
        [
            # issue de verdade, sem arquivo: cai no fallback
            {
                "id": 11,
                "url": _url(ALPHA, "issues/1"),
                "repository_url": _url(ALPHA, ""),
                "user": humano,
                "created_at": "2021-03-02T10:00:00Z",
            },
            # PODRE: sem data
            {
                "id": 12,
                "url": _url(ALPHA, "issues/2"),
                "repository_url": _url(ALPHA, ""),
                "user": outro,
                "created_at": None,
            },
            # com a chave `pull_request` vira abertura de PR
            {
                "id": 13,
                "url": _url(BETA, "issues/3"),
                "repository_url": _url(BETA, ""),
                "user": humano,
                "created_at": "2021-03-03T10:00:00Z",
                "pull_request": {"url": _url(BETA, "pulls/3")},
            },
        ],
    )
    grava(
        "issue_comments.jsonl",
        [
            {
                "id": 21,
                "url": _url(BETA, "issues/comments/21"),
                "issue_url": _url(BETA, "issues/3"),
                "user": outro,
                "created_at": "2021-03-04T10:00:00Z",
            }
        ],
    )
    grava(
        "commit_comments.jsonl",
        [
            {
                "id": 31,
                "url": _url(BETA, "comments/31"),
                "commit_id": "ddd",
                "path": None,
                "user": humano,
                "created_at": "2021-03-05T10:00:00Z",
            }
        ],
    )
    grava(
        "pull_request_comments.jsonl",
        [
            {
                "id": 41,
                "url": _url(ALPHA, "pulls/comments/41"),
                "pull_request_url": _url(ALPHA, "pulls/9"),
                "path": "src/core.clj",
                "commit_id": "aaa",
                "user": humano,
                "created_at": "2021-03-06T10:00:00Z",
            }
        ],
    )
    grava(
        "issue_events.jsonl",
        [
            {
                "id": 51,
                "url": _url(BETA, "issues/events/51"),
                "event": "closed",
                "actor": outro,
                "created_at": "2021-03-07T10:00:00Z",
            }
        ],
    )

    (raiz / "commit_files.tsv").write_text(
        "repo\tsha\tauthor_date\tauthor_email\tpath\n"
        f"{ALPHA}\taaa\t2021-03-01T10:00:00Z\tana@x\tsrc/core.clj\n"
        f"{ALPHA}\tbbb\t2021-04-01T10:00:00Z\tbia@x\tsrc/core.clj\n"
        f"{ALPHA}\tbbb\t2021-04-01T10:00:00Z\tbia@x\tsrc/Util.java\n"
        f"{ALPHA}\tccc\t2021-05-01T10:00:00Z\tzed@x\tsrc/core.clj\n",
        encoding="utf-8",
    )
    return raiz


@contextmanager
def ghapi_de_teste(politica: dict | None = None):
    """Fonte apontada para uma coleta mínima recém-escrita."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        raiz = coleta_minima(Path(tmp) / "ghapi")
        yield GHAPISource({"language": politica or {}}, raiz=raiz)


@pytest.fixture
def fonte():
    with ghapi_de_teste() as src:
        yield src


# --- escopo é o par (repositório, linguagem) ----------------------------------


def test_repositorio_vira_um_escopo_por_linguagem(fonte):
    rotulos = {fonte.scope_label(s) for s in fonte.list_scopes()}

    assert rotulos == {"acme/alpha [Clojure]", "acme/alpha [Java]", "acme/beta [unknown]"}


def test_commit_que_toca_duas_linguagens_vira_dois_eventos(fonte):
    """O `bbb` toca `src/core.clj` e `src/Util.java`. A pessoa mexeu nas duas."""
    por_escopo = {fonte.scope_label(s): fonte.get_events(s) for s in fonte.list_scopes()}
    clojure = por_escopo["acme/alpha [Clojure]"]
    java = por_escopo["acme/alpha [Java]"]

    assert 2 in set(clojure["contributor_id"])
    assert 2 in set(java["contributor_id"])
    assert len(java) == 1


def test_repositorio_sem_linguagem_detectada_vira_unknown(fonte):
    """Mapa de bytes vazio nao tem elegivel, e o `scope_meta.language` sai None."""
    sid = next(s for s in fonte.list_scopes() if fonte.scope_label(s).endswith("[unknown]"))

    assert fonte.scope_meta(sid)["language"] is None


def test_o_id_do_escopo_e_estavel_entre_instancias():
    """O id sai do repo e do indice da linguagem, sem contador de execucao."""
    with ghapi_de_teste() as a, ghapi_de_teste() as b:
        assert a.list_scopes() == b.list_scopes()


# --- de onde sai a linguagem de cada evento -----------------------------------


def test_evento_sem_arquivo_cai_na_linguagem_do_repositorio(fonte):
    """Abertura de issue nao toca arquivo. No alpha o elegivel e Clojure."""
    sid = next(s for s in fonte.list_scopes() if fonte.scope_label(s).endswith("alpha [Clojure]"))

    assert "issues" in set(fonte.get_events(sid)["event_type"])


def test_comentario_de_review_usa_o_campo_path(fonte):
    sid = next(s for s in fonte.list_scopes() if fonte.scope_label(s).endswith("alpha [Clojure]"))

    assert "pull_request_comments" in set(fonte.get_events(sid)["event_type"])


def test_issue_com_a_chave_pull_request_vira_abertura_de_pr(fonte):
    tipos = set()
    for s in fonte.list_scopes():
        tipos |= set(fonte.get_events(s)["event_type"])

    assert {"issues", "pull_requests"} <= tipos


# --- as chaves da politica ----------------------------------------------------


def _eventos(src):
    return sum(len(src.get_events(s)) for s in src.list_scopes())


def test_min_share_amplia_o_conjunto_elegivel():
    """Java tem 10% dos bytes do alpha. Com corte em 50% ele deixa de ser elegivel."""
    with ghapi_de_teste({"repo_languages": {"policy": "min_share", "min_share": 5.0}}) as src:
        assert "acme/alpha [Java]" in {src.scope_label(s) for s in src.list_scopes()}
    with ghapi_de_teste(
        {"repo_languages": {"policy": "min_share", "min_share": 50.0}, "outside_eligible": "drop"}
    ) as src:
        assert "acme/alpha [Java]" not in {src.scope_label(s) for s in src.list_scopes()}


def test_outside_eligible_drop_descarta_a_cauda():
    """Com `primary`, Java fica fora do elegivel do alpha."""
    with (
        ghapi_de_teste({"outside_eligible": "keep"}) as com,
        ghapi_de_teste({"outside_eligible": "drop"}) as sem,
    ):
        assert _eventos(com) - _eventos(sem) == 1


def test_attribution_repo_languages_ignora_o_caminho():
    """Todo evento passa a herdar a linguagem do repositorio, e Java some."""
    with ghapi_de_teste({"attribution": "repo_languages"}) as src:
        assert "acme/alpha [Java]" not in {src.scope_label(s) for s in src.list_scopes()}


def test_fallback_drop_apaga_quem_nao_tem_arquivo():
    with (
        ghapi_de_teste({"fallback": "repo_languages"}) as com,
        ghapi_de_teste({"fallback": "drop"}) as sem,
    ):
        assert _eventos(sem) < _eventos(com)


def test_bot_sai_por_padrao_e_volta_quando_pedido():
    with (
        ghapi_de_teste({"drop_bots": True}) as sem,
        ghapi_de_teste({"drop_bots": False}) as com,
    ):
        assert _eventos(com) - _eventos(sem) == 1


def test_chave_desconhecida_na_politica_falha_alto():
    with pytest.raises(ValueError, match="chave desconhecida"), ghapi_de_teste({"x": 1}):
        pass


def test_a_politica_inteira_entra_no_provenance(fonte):
    """Duas execucoes com politica diferente nao sao comparaveis, e o manifesto tem de dizer."""
    p = fonte.provenance()

    assert p["language_policy"]["attribution"] == "by_path"
    assert "linguist" in p


# --- ambiguidade de extensao ---------------------------------------------------


def test_extensao_ambigua_e_resolvida_pelo_mapa_de_bytes():
    """`.h` e C, C++ e Objective-C. O mapa do repositorio desempata."""
    gh = sources.load("ghapi").__module__
    import sys

    m = sys.modules[gh]

    assert m._linguagem_no_repo("x.h", {"C": 100, "C++": 900}) == "C++"
    assert m._linguagem_no_repo("x.rs", {"Rust": 10}) == "Rust"
    # `.md` e Markdown e GCC Machine Description, e o mapa de /languages exclui
    # prosa, entao nenhum repositorio normal reivindica o README.
    assert m._linguagem_no_repo("README.md", {"Clojure": 10}) is None
