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
                "parents": [{"sha": "000"}],
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
                "number": 1,
                "url": _url(ALPHA, "issues/1"),
                "repository_url": _url(ALPHA, ""),
                "user": humano,
                "created_at": "2021-03-02T10:00:00Z",
                "labels": [{"name": "bug"}],
                "assignees": [],
            },
            # PODRE: sem data
            {
                "id": 12,
                "number": 2,
                "url": _url(ALPHA, "issues/2"),
                "repository_url": _url(ALPHA, ""),
                "user": outro,
                "created_at": None,
            },
            # com a chave `pull_request` vira abertura de PR
            {
                "id": 13,
                "number": 3,
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
                "position": None,
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


# --- coleta que traz /pulls num arquivo à parte -------------------------------
#
# A coleta grande é feita por outra pessoa, que pode listar `/pulls` em vez de
# tirar os PRs do `/issues`. Item de `/pulls` traz `issue_url`, igual a
# comentário de issue, e sem tratamento próprio a abertura de PR entraria como
# comentário. Isso troca `coding` por `non_coding` e inverte o CCR do escopo.


def _item_de_pulls(numero: int, user: dict, quando: str) -> dict:
    """Forma real de `GET /pulls`, com os campos que decidem a classificação."""
    return {
        "id": 900 + numero,
        "number": numero,
        "url": _url(ALPHA, f"pulls/{numero}"),
        "issue_url": _url(ALPHA, f"issues/{numero}"),
        "head": {"ref": "feat"},
        "base": {"ref": "main"},
        "user": user,
        "created_at": quando,
    }


def _com_pulls(raiz: Path, itens: list[dict]) -> Path:
    (raiz / "pulls.jsonl").write_text(
        "".join(json.dumps(i) + "\n" for i in itens), encoding="utf-8"
    )
    return raiz


def test_arquivo_de_pulls_vira_abertura_de_pr(tmp_path):
    raiz = _com_pulls(
        coleta_minima(tmp_path / "ghapi"),
        [_item_de_pulls(9, {"id": 7, "login": "carl", "type": "User"}, "2021-08-01T10:00:00Z")],
    )
    src = GHAPISource({}, raiz=raiz)
    por_tipo = {
        t
        for s in src.list_scopes()
        for t in src.get_events(s).loc[src.get_events(s)["contributor_id"] == 7, "event_type"]
    }

    assert por_tipo == {"pull_requests"}


def test_o_mesmo_pr_nas_duas_listagens_nao_conta_duas_vezes(tmp_path):
    """`/issues` e `/pulls` descrevem o PR com o mesmo autor e a mesma data.

    Conferido nos PRs 2949, 2950 e 2951 do clj-kondo: `user.id` e `created_at`
    batem nas duas listagens. A linha canônica sai idêntica, e a limpeza de
    duplicata exata que o contrato já exige resolve sozinha.
    """
    humano = {"id": 1, "login": "ana", "type": "User"}
    sem = GHAPISource({}, raiz=coleta_minima(tmp_path / "a"))
    # O PR 3 do `beta` já existe na coleta mínima, dentro de issues.jsonl.
    duplicado = _item_de_pulls(3, humano, "2021-03-03T10:00:00Z")
    duplicado["url"] = _url(BETA, "pulls/3")
    duplicado["issue_url"] = _url(BETA, "issues/3")
    com = GHAPISource({}, raiz=_com_pulls(coleta_minima(tmp_path / "b"), [duplicado]))

    assert _eventos(com) == _eventos(sem)


# --- a coleta vem concatenada por busca, com os repositórios embaralhados ------
#
# A coleta grande grava um arquivo por busca com os itens de todos os
# repositórios juntos, em qualquer ordem. O repositório de cada evento sai do
# campo `url`, que as sete formas trazem, então nome de arquivo, nome de pasta e
# ordem de linha não entram na conta.


def test_repositorio_sai_do_url_nas_sete_formas():
    import sys

    m = sys.modules[GHAPISource.__module__]
    formas = {
        "commits": {"url": _url(ALPHA, "commits/aaa")},
        "issues": {"url": _url(BETA, "issues/1")},
        "pull_requests": {"url": _url(ALPHA, "pulls/9")},
        "issue_comments": {"url": _url(BETA, "issues/comments/21")},
        "commit_comments": {"url": _url(ALPHA, "comments/31")},
        "pull_request_comments": {"url": _url(BETA, "pulls/comments/41")},
        "issue_events": {"url": _url(ALPHA, "issues/events/51")},
    }
    achados = {busca: m._repo_do_item(item) for busca, item in formas.items()}

    assert set(achados.values()) == {ALPHA, BETA}
    assert achados["pull_requests"] == ALPHA
    assert achados["issue_events"] == ALPHA


def test_ordem_das_linhas_nao_muda_o_resultado(tmp_path):
    """Embaralhar os itens dentro de cada arquivo tem de dar a mesma tabela."""
    import random

    direto = GHAPISource({}, raiz=coleta_minima(tmp_path / "a"))
    embaralhado_raiz = coleta_minima(tmp_path / "b")
    rng = random.Random(0)
    for arquivo in embaralhado_raiz.glob("*.jsonl"):
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
        rng.shuffle(linhas)
        arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    embaralhado = GHAPISource({}, raiz=embaralhado_raiz)

    assert direto.list_scopes() == embaralhado.list_scopes()
    for sid in direto.list_scopes():
        a = direto.get_events(sid).sort_values(list(direto.get_events(sid).columns))
        b = embaralhado.get_events(sid).sort_values(list(a.columns))
        assert a.reset_index(drop=True).equals(b.reset_index(drop=True))


def test_um_arquivo_so_com_tudo_dentro_da_o_mesmo_resultado(tmp_path):
    """Todos os eventos, de todos os tipos e repositórios, num arquivo só.

    A classificação é por item, então separar por busca, separar por repositório
    ou jogar tudo junto tem de dar a mesma tabela. Classificar pelo primeiro item
    e aplicar o veredito ao arquivo inteiro leria tudo depois da primeira linha
    com o tipo errado.
    """
    por_busca = coleta_minima(tmp_path / "a")
    tudo_junto = tmp_path / "b"
    tudo_junto.mkdir()
    for nome in ["repos.jsonl", "languages.jsonl", "commit_files.tsv"]:
        conteudo = (por_busca / nome).read_text(encoding="utf-8")
        (tudo_junto / nome).write_text(conteudo, encoding="utf-8")
    misturado = []
    for arquivo in sorted(por_busca.glob("*.jsonl")):
        if arquivo.name in {"repos.jsonl", "languages.jsonl"}:
            continue
        misturado += arquivo.read_text(encoding="utf-8").splitlines()
    (tudo_junto / "eventos.jsonl").write_text("\n".join(misturado) + "\n", encoding="utf-8")

    esperado = GHAPISource({}, raiz=por_busca)
    obtido = GHAPISource({}, raiz=tudo_junto)

    assert obtido.list_scopes() == esperado.list_scopes()
    for sid in esperado.list_scopes():
        colunas = list(esperado.get_events(sid).columns)
        a = esperado.get_events(sid).sort_values(colunas).reset_index(drop=True)
        b = obtido.get_events(sid).sort_values(colunas).reset_index(drop=True)
        assert a.equals(b)


def test_um_arquivo_por_repositorio_da_o_mesmo_resultado(tmp_path):
    """A coleta pode separar por repositório em vez de por busca."""
    por_busca = coleta_minima(tmp_path / "a")
    por_repo = tmp_path / "b"
    por_repo.mkdir()
    for nome in ["repos.jsonl", "languages.jsonl", "commit_files.tsv"]:
        conteudo = (por_busca / nome).read_text(encoding="utf-8")
        (por_repo / nome).write_text(conteudo, encoding="utf-8")
    for arquivo in sorted(por_busca.glob("*.jsonl")):
        if arquivo.name in {"repos.jsonl", "languages.jsonl"}:
            continue
        conteudo = arquivo.read_text(encoding="utf-8")
        (por_repo / f"{arquivo.stem}-parte.jsonl").write_text(conteudo, encoding="utf-8")

    assert (
        GHAPISource({}, raiz=por_repo).list_scopes()
        == GHAPISource({}, raiz=por_busca).list_scopes()
    )


def test_item_de_forma_desconhecida_nao_derruba_a_coleta(tmp_path):
    """Lixo no meio do arquivo sai contado, e o resto da coleta continua."""
    raiz = coleta_minima(tmp_path / "a")
    with (raiz / "commits.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"algo": "que nao e evento"}) + "\n")

    assert (
        GHAPISource({}, raiz=raiz).list_scopes()
        == GHAPISource({}, raiz=coleta_minima(tmp_path / "b")).list_scopes()
    )


# --- a coleta chega no formato que quem coletou escolheu ----------------------


def _eventos_da(raiz: Path) -> list[Path]:
    return [f for f in raiz.glob("*.jsonl") if f.name not in {"repos.jsonl", "languages.jsonl"}]


def _para_array(raiz: Path) -> None:
    for f in _eventos_da(raiz):
        itens = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        f.with_suffix(".json").write_text(json.dumps(itens), encoding="utf-8")
        f.unlink()


def _para_envelope(raiz: Path) -> None:
    """Envelope com contagem junto, como a API de busca devolve."""
    for f in _eventos_da(raiz):
        itens = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        f.with_suffix(".json").write_text(
            json.dumps({"total_count": len(itens), "items": itens}), encoding="utf-8"
        )
        f.unlink()


def _para_ndjson(raiz: Path) -> None:
    for f in _eventos_da(raiz):
        f.rename(f.with_suffix(".ndjson"))


def _para_gzip(raiz: Path) -> None:
    import gzip
    import shutil

    for f in _eventos_da(raiz):
        with f.open("rb") as entrada, gzip.open(f"{f}.gz", "wb") as saida:
            shutil.copyfileobj(entrada, saida)
        f.unlink()


def _para_subpastas(raiz: Path) -> None:
    for f in _eventos_da(raiz):
        pasta = raiz / f.stem
        pasta.mkdir(exist_ok=True)
        f.rename(pasta / "pagina1.jsonl")


def _numa_linha_so(raiz: Path) -> None:
    for f in _eventos_da(raiz):
        itens = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        f.write_text(json.dumps(itens), encoding="utf-8")


@pytest.mark.parametrize(
    "transforma",
    [_para_array, _para_envelope, _para_ndjson, _para_gzip, _para_subpastas, _numa_linha_so],
    ids=["array", "envelope", "ndjson", "gzip", "subpastas", "array numa linha"],
)
def test_o_formato_de_entrega_nao_muda_o_resultado(tmp_path, transforma):
    """Quem coleta escolhe o formato, e a tabela final tem de sair igual.

    O envelope é o caso delicado: desembrulhar por existir valor de lista pegaria
    o campo errado, porque item de commit tem `parents` e item de issue tem
    `labels`. O que separa envelope de evento é o campo `url`.
    """
    esperado = GHAPISource({}, raiz=coleta_minima(tmp_path / "a"))
    outra = coleta_minima(tmp_path / "b")
    transforma(outra)
    obtido = GHAPISource({}, raiz=outra)

    assert obtido.list_scopes() == esperado.list_scopes()
    for sid in esperado.list_scopes():
        colunas = list(esperado.get_events(sid).columns)
        a = esperado.get_events(sid).sort_values(colunas).reset_index(drop=True)
        b = obtido.get_events(sid).sort_values(colunas).reset_index(drop=True)
        assert a.equals(b)
