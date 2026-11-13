"""Os motores de carga devolvem os mesmos eventos que `carrega_eventos`, num caso pequeno.

Linguagem Zig (extensão .zig). Repositórios:

  1  elegível, criado em 2020. Tem o commit X, também presente em 3.
  2  elegível, criado em 2021. Cópia de histórico: repete o commit Y de 1.
  3  inelegível (10% de Zig), criado em 2019. Tem X, mais antigo que o de 1: o de 1 sai.
  4  elegível. Issue de 2015 vem antes do primeiro commit .zig do repositório: sai.

Os arquivos de eventos têm as 18 colunas da coleta. O layout `misto` junta api e git num
arquivo só, como `eventos_repositorios.csv`.
"""

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import carga_compacta  # noqa: E402
import carga_fonte  # noqa: E402
import carga_pandas  # noqa: E402
import figuras_linguagem_bruta as fb  # noqa: E402
from pyramid import vitalidade  # noqa: E402

COLUNAS = [
    "repo_id", "repo_name", "event_type", "number", "title", "author", "author_login",
    "author_email", "created_at", "state", "sha", "message", "url", "labels", "files",
    "language", "collection_status", "collection_started_at",
]  # fmt: skip


def _linha(repo, tipo, autor, data, arquivos=None, linguagem=None, login=False):
    linha = dict.fromkeys(COLUNAS)
    linha.update(repo_id=repo, event_type=tipo, created_at=data, files=arquivos, language=linguagem)
    linha["author_login" if login else "author"] = autor
    linha["message"] = "texto com | barra e\nquebra de linha"
    return linha


GIT = [
    _linha("1", "commit", "ana", "2022-03-01T10:00:00+02:00", "a.zig;b.c"),
    _linha("3", "commit", "ana", "2022-03-01T10:00:00+02:00", "a.zig;b.c"),
    _linha("1", "commit", "bob", "2022-05-01T10:00:00Z", "src/main.ZIG"),
    _linha("2", "commit", "bob", "2022-05-01T10:00:00Z", "src/main.ZIG"),
    _linha("1", "commit", "123", "2023-01-01T08:00:00Z", "m.zig"),
    _linha("1", "commit", "ghost", "2023-01-02T08:00:00Z", "m.zig"),
    _linha("1", "commit", "dep[bot]", "2023-01-03T08:00:00Z", "m.zig"),
    _linha("1", "commit", "ana", "2023-02-01T08:00:00Z", "readme.md"),
    _linha("1", "commit", None, "2023-02-01T08:00:00Z", "m.zig"),
    _linha("1", "commit", "ana", "texto-que-nao-e-data", "n.zig"),
    _linha("1", "commit", "ana", "2999-01-01T00:00:00Z", "n.zig"),
    _linha("1", "commit", "ana", "2005-01-01T00:00:00Z", "n.zig"),
    _linha("4", "commit", "cris", "2019-06-01T00:00:00Z", "k.zig"),
    _linha("1", "commit", "bob", "2023-06-01T00:00:00Z", "w.zig; ;v.zig"),
    _linha("1", "commit", "dee", "2023-07-01T00:00:00Z", "t.zig"),
    _linha("1", "commit", "dee", "2023-07-20T00:00:00Z", "t.zig"),
    _linha("1", "commit", "dee", "2025-05-20T00:00:00Z", "t.zig"),
]  # fmt: skip
API = [
    _linha("1", "issue", "ana", "2022-04-01T00:00:00Z", None, None, True),
    _linha("1", "issue_comment", "bob", "2022-04-02T00:00:00Z", None, "Zig", True),
    _linha("1", "issue_comment", "bob", "2022-04-03T00:00:00Z", None, "Rust", True),
    _linha("1", "pr", None, "2022-04-04T00:00:00Z", None, "Zig", True),
    _linha("4", "issue", "cris", "2015-01-01T00:00:00Z", None, "Zig", True),
    _linha("4", "pr_comment", "cris", "2020-01-01T00:00:00Z", None, "Zig", True),
    _linha("1", "evento_desconhecido", "ana", "2022-04-05T00:00:00Z", None, "Zig", True),
    _linha("3", "issue", "ana", "2022-04-06T00:00:00Z", None, "Zig", True),
    _linha("1", "issue", "None", "2022-04-07T00:00:00Z", None, "Zig", True),
]  # fmt: skip


def _escreve(pasta: Path, layout: str, alvos_partidos: bool) -> None:
    pasta.mkdir()
    zig = json.dumps({"Zig": 90, "C": 10})
    pouco = json.dumps({"Zig": 10, "C": 90})
    alvo = pd.DataFrame(
        {
            "repo_id": ["1", "2", "3", "4"],
            "mainLanguage": ["Zig", "Zig", "C", "Zig"],
            "createdAt": [
                "2020-01-01T00:00:00",
                "2021-01-01T00:00:00",
                "2019-01-01T00:00:00",
                "2018-01-01T00:00:00",
            ],
            "languages": [zig, zig, pouco, zig],
        }
    )
    if alvos_partidos:
        alvo.iloc[:2].to_csv(pasta / "repositorios_zig_alvo.csv", index=False)
        alvo.iloc[2:].to_csv(pasta / "outro_alvo.csv", index=False)
    else:
        alvo.to_csv(pasta / "repositorios_zig_alvo.csv", index=False)
    api, git = pd.DataFrame(API, columns=COLUNAS), pd.DataFrame(GIT, columns=COLUNAS)
    if layout == "misto":
        pd.concat([api, git]).to_csv(pasta / "eventos_zig.csv", sep="|", index=False)
    else:
        api.to_csv(pasta / "eventos_api.csv", sep="|", index=False)
        git.to_csv(pasta / "eventos_git.csv", sep="|", index=False)


@pytest.fixture
def zig(tmp_path, monkeypatch):
    monkeypatch.setattr(fb.LING, "atual", fb.LINGUAGENS["zig"], raising=False)
    monkeypatch.setattr(fb.CFG, "saida", tmp_path / "saida", raising=False)
    return tmp_path


def _original(tmp_path, monkeypatch) -> pd.DataFrame:
    """Os eventos de `carrega_eventos`, sobre os mesmos dados no layout separado."""
    pasta = tmp_path / "original"
    _escreve(pasta, "separado", False)
    monkeypatch.setattr(fb.CFG, "dados", pasta, raising=False)
    return fb.carrega_eventos(2)[["contributor_id", "event_type", "timestamp"]]


def _fonte(tmp_path, layout, alvos_partidos) -> carga_fonte.Fonte:
    pasta = tmp_path / f"{layout}-{alvos_partidos}"
    _escreve(pasta, layout, alvos_partidos)
    if alvos_partidos:
        eventos = [str(p) for p in sorted(pasta.glob("eventos_*.csv"))]
        alvos = [str(pasta / "repositorios_zig_alvo.csv"), str(pasta / "outro_alvo.csv")]
        return carga_fonte.resolve_fonte("zig", eventos=eventos, alvos=alvos)
    return carga_fonte.resolve_fonte("zig", dados=str(pasta))


def _sem_ids(ev: pd.DataFrame) -> dict:
    """O que as métricas leem, sem o id da pessoa: períodos e pessoa-ano, ordenados."""
    fim = ev["timestamp"].max()
    ev = ev.assign(event_type=ev["event_type"].astype(str))
    periodos = vitalidade.periodos(ev).drop(columns="contributor_id")
    pa = vitalidade.pessoa_ano(ev, fim).drop(columns="contributor_id")
    return {
        "periodos": periodos.sort_values(list(periodos.columns)).reset_index(drop=True),
        "pessoa_ano": pa.sort_values(list(pa.columns)).reset_index(drop=True),
        "anual": vitalidade.tabela_anual(vitalidade.pessoa_ano(ev, fim), fim),
    }


@pytest.mark.parametrize("layout", ["separado", "misto"])
@pytest.mark.parametrize("alvos_partidos", [False, True])
def test_motor_pandas_igual_a_carrega_eventos(zig, monkeypatch, layout, alvos_partidos):
    original = _original(zig, monkeypatch)
    fonte = _fonte(zig, layout, alvos_partidos)
    monkeypatch.setattr(carga_pandas, "PEDACO", 3)  # o resultado não depende de onde o pedaço corta
    novo = carga_compacta.carrega(fonte, "pandas")
    novo["event_type"] = novo["event_type"].astype(str)
    pd.testing.assert_frame_equal(novo, original, check_dtype=False)

    # O caso exercita as regras de verdade: não passa por não ter nada a descartar.
    estatisticas = fb.ESTATISTICAS_CARGA["zig"]
    assert estatisticas["commits_duplicados_descartados"] == 2
    assert estatisticas["eventos_antes_do_piso_descartados"] == 1
    assert estatisticas["eventos_fantasma_descartados"] == 1
    assert estatisticas["eventos_bot_descartados"] == 1
    assert estatisticas["eventos_data_ilegivel_descartados"] == 1
    assert estatisticas["eventos_futuro_descartados"] == 1
    assert estatisticas["eventos_antes_2008_descartados"] == 1


@pytest.mark.parametrize("layout", ["separado", "misto"])
@pytest.mark.parametrize("alvos_partidos", [False, True])
def test_motor_duckdb_da_as_mesmas_metricas(zig, monkeypatch, layout, alvos_partidos):
    original = _original(zig, monkeypatch)
    esperado_estatisticas = dict(fb.ESTATISTICAS_CARGA["zig"])
    fonte = _fonte(zig, layout, alvos_partidos)
    novo = carga_compacta.carrega(fonte, "duckdb", trabalho=zig / "trabalho", threads=2)
    esperado, obtido = _sem_ids(vitalidade.compacta(original)), _sem_ids(novo)
    for chave in esperado:
        pd.testing.assert_frame_equal(obtido[chave], esperado[chave], check_dtype=False)
    # E as mesmas contagens de cada filtro.
    assert fb.ESTATISTICAS_CARGA["zig"] == esperado_estatisticas


def test_origem_bate_com_os_eventos_da_carga(zig, monkeypatch):
    original = _original(zig, monkeypatch)
    fonte = _fonte(zig, "separado", False)
    pasta = zig / "origem"
    carga_compacta.carrega(fonte, "duckdb", trabalho=zig / "trabalho", threads=2, origem=pasta)
    pessoas = pd.read_parquet(pasta / "pessoas.parquet")
    assert len(pessoas) == original["contributor_id"].nunique()
    assert pessoas["primeiro"].min() == original["timestamp"].min()
    assert (pessoas["eventos"] >= 1).all()
    assert (pessoas["codou"] == (pessoas["eventos_de_codigo"] > 0)).all()
    assert (pessoas["commits"] <= pessoas["eventos_de_codigo"]).all()
    assert (pessoas["ocasioes"] >= 1).all()
    assert (pessoas["ocasioes"] <= pessoas["eventos"]).all()
    # A segunda ocasião existe só para quem tem mais de uma, e não vem antes do primeiro evento.
    assert (pessoas["segunda_ocasiao"].notna() == (pessoas["ocasioes"] > 1)).all()
    voltaram = pessoas[pessoas["ocasioes"] > 1]
    assert (voltaram["segunda_ocasiao"] >= voltaram["primeiro"]).all()
    assert pd.read_parquet(pasta / "repos.parquet")["codigo"].is_unique
    meses = pd.read_parquet(pasta / "meses.parquet")
    assert set(meses["grupo"]) <= {"codigo", "discussao"}
    tipos = pd.read_parquet(pasta / "tipos_por_ano.parquet")
    assert tipos["eventos"].sum() == len(original)
    assert tipos["primeiro"].min() == original["timestamp"].min()
    final = pd.read_parquet(pasta / "tipos_final.parquet")
    assert final["eventos"].sum() == len(original)
    assert (final["eventos_residentes"] <= final["eventos"]).all()


def test_repos_excluidos_saem_da_carga(zig, monkeypatch):
    _original(zig, monkeypatch)
    fonte = _fonte(zig, "separado", False)
    todos = carga_compacta.carrega(fonte, "duckdb", trabalho=zig / "trabalho", threads=2)
    sem = carga_compacta.carrega(
        fonte, "duckdb", trabalho=zig / "trabalho", threads=2, repos_excluidos=("1",)
    )
    assert len(sem) < len(todos)


def test_completos_do_duckdb_iguais_a_carrega_eventos(zig, monkeypatch):
    """O pipeline do motor recebe do duckdb os mesmos eventos, repositório por repositório."""
    pasta = zig / "original"
    _escreve(pasta, "separado", False)
    monkeypatch.setattr(fb.CFG, "dados", pasta, raising=False)
    original = fb.carrega_eventos(2)
    fonte = _fonte(zig, "separado", False)
    novo = carga_compacta.carrega(
        fonte, "duckdb", trabalho=zig / "trabalho", threads=2, completos=True
    )
    colunas = ["repo_id", "event_type", "timestamp"]
    esperado = original[colunas].astype(str).sort_values(colunas).reset_index(drop=True)
    obtido = novo[colunas].astype(str).sort_values(colunas).reset_index(drop=True)
    pd.testing.assert_frame_equal(obtido, esperado)
    assert novo["contributor_id"].nunique() == original["contributor_id"].nunique()
    assert novo.groupby("repo_id")["scope_id"].nunique().eq(1).all()


def test_fonte_acha_papel_e_alvos(zig):
    separado = _fonte(zig, "separado", False)
    assert [a.papel for a in separado.eventos] == ["api", "git"]
    misto = _fonte(zig, "misto", False)
    assert [a.papel for a in misto.eventos] == ["misto"]
    assert len(_fonte(zig, "misto", True).alvos) == 2


def test_fonte_com_arquivo_que_nao_existe_diz_qual(zig):
    with pytest.raises(SystemExit, match="não existe"):
        carga_fonte.resolve_fonte(
            "zig", eventos=[str(zig / "nada.csv")], alvos=[str(zig / "x.csv")]
        )


def test_motor_desconhecido_falha_alto(zig):
    with pytest.raises(SystemExit):
        carga_compacta.carrega(_fonte(zig, "separado", False), "motor_que_nao_existe")


def test_acoes_ignoradas_tiram_quem_so_foi_marcado(zig):
    fonte = _fonte(zig, "separado", False)
    marcada = _linha("1", "issue_event", "eve", "2022-04-08T00:00:00Z", None, "Zig", True)
    marcada["message"] = "mentioned"
    api = zig / "separado-False" / "eventos_api.csv"
    pd.DataFrame([marcada], columns=COLUNAS).to_csv(
        api, sep="|", index=False, header=False, mode="a"
    )

    com = carga_compacta.carrega(fonte, "duckdb", trabalho=zig / "t1", threads=2)
    sem = carga_compacta.carrega(
        fonte, "duckdb", trabalho=zig / "t2", threads=2, acoes_ignoradas=("mentioned",)
    )
    assert sem["contributor_id"].nunique() == com["contributor_id"].nunique() - 1
    with pytest.raises(SystemExit):
        carga_compacta.carrega(fonte, "pandas", acoes_ignoradas=("mentioned",))


def test_fundir_identidades_junta_commit_e_login(zig):
    fonte = _fonte(zig, "separado", False)
    pasta = zig / "separado-False"
    commit = _linha("1", "commit", "Eva Lima", "2023-03-01T00:00:00Z", "e.zig")
    commit["author_email"] = "123+eva@users.noreply.github.com"
    issue = _linha("1", "issue", "eva", "2023-03-02T00:00:00Z", None, "Zig", True)
    pd.DataFrame([commit], columns=COLUNAS).to_csv(
        pasta / "eventos_git.csv", sep="|", index=False, header=False, mode="a"
    )
    pd.DataFrame([issue], columns=COLUNAS).to_csv(
        pasta / "eventos_api.csv", sep="|", index=False, header=False, mode="a"
    )

    def pessoas(trabalho, **opcoes):
        ev = carga_compacta.carrega(fonte, "duckdb", trabalho=zig / trabalho, threads=2, **opcoes)
        return ev["contributor_id"].nunique()

    separadas = pessoas("t1")
    # O fixture é pequeno demais para 5 repositórios em comum: só o e-mail noreply junta.
    assert pessoas("t2", fundir_identidades=True) == separadas - 1
    with pytest.raises(SystemExit):
        carga_compacta.carrega(fonte, "pandas", fundir_identidades=True)


def test_autores_ligam_commit_ao_login(zig):
    fonte = _fonte(zig, "separado", False)
    pasta = zig / "separado-False"
    commit = _linha("1", "commit", "Eva Lima", "2023-03-01T00:00:00Z", "e.zig")
    commit["author_email"] = " Eva@Exemplo.com"
    sem_conta = _linha("1", "commit", "Ivo", "2023-03-03T00:00:00Z", "i.zig")
    sem_conta["author_email"] = "ivo@exemplo.com"
    issue = _linha("1", "issue", "eva", "2023-03-02T00:00:00Z", None, "Zig", True)
    pd.DataFrame([commit, sem_conta], columns=COLUNAS).to_csv(
        pasta / "eventos_git.csv", sep="|", index=False, header=False, mode="a"
    )
    pd.DataFrame([issue], columns=COLUNAS).to_csv(
        pasta / "eventos_api.csv", sep="|", index=False, header=False, mode="a"
    )
    autores = pasta / "autores_commits.csv"
    autores.write_text(
        "author_email|author_name|repo_id|sha|login|user_id|status|coletado_em\n"
        "eva@exemplo.com|Eva Lima|1|abc|eva|99|ok|2026-10-26\n"
        "ivo@exemplo.com|Ivo|1|def|||sem_conta|2026-10-26\n"
    )

    separadas = carga_compacta.carrega(fonte, "duckdb", trabalho=zig / "t1", threads=2)
    fonte.autores = autores
    ligadas = carga_compacta.carrega(fonte, "duckdb", trabalho=zig / "t2", threads=2)
    assert ligadas["contributor_id"].nunique() == separadas["contributor_id"].nunique() - 1
    with pytest.raises(SystemExit):
        carga_compacta.carrega(fonte, "pandas")


def test_fusao_por_repositorios_pega_o_par_de_maior_jaccard():
    from adapters.coleta_csv import carga_duckdb

    con = duckdb.connect()
    # tipos: 0 commit, 1 issue, 2 comentário. 10 só commita; 20 e 30 só abrem issue; 40 mistura.
    elegiveis = pd.DataFrame(
        {
            "codigo": [1, 2, 1, 2, 1, 9, 1, 1],
            "tipo": [0, 0, 1, 1, 1, 1, 0, 2],
            "pessoa": [10, 10, 20, 20, 30, 30, 40, 40],
            "marca": [0] * 8,
        }
    )
    con.from_df(elegiveis).create("elegiveis")
    pedido = carga_duckdb.Pedido(
        eventos=[], repos=pd.DataFrame(), linguagem="", extensoes=(), tipos={},
        trabalho=Path(), fundir_identidades=True, fusao_repos_min=1,
    )  # fmt: skip
    stats: dict[str, int] = {}
    nomes = ["commits", "issues", "issue_comments", "pull_requests"]
    carga_duckdb._funde_por_repositorios(con, pedido, nomes, stats)
    pessoas = sorted(con.table("elegiveis").df()["pessoa"].unique())
    assert stats["identidades_fundidas_por_repositorios"] == 1
    assert pessoas == [20, 30, 40]


def _pedido(pasta: Path, git: list, api: list, repos: pd.DataFrame, **opcoes):
    """Pedido duckdb mínimo, com os eventos que o teste escreve."""
    from adapters.coleta_csv import carga_duckdb

    pasta.mkdir()
    pd.DataFrame(git, columns=COLUNAS).to_csv(pasta / "eventos_git.csv", sep="|", index=False)
    pd.DataFrame(api, columns=COLUNAS).to_csv(pasta / "eventos_api.csv", sep="|", index=False)
    return carga_duckdb.Pedido(
        eventos=[(pasta / "eventos_git.csv", "git"), (pasta / "eventos_api.csv", "api")],
        repos=repos,
        linguagem="Zig",
        extensoes=(".zig",),
        tipos=fb.MAPA_TIPO_R2,
        trabalho=pasta / "trabalho",
        threads=1,
        contar_brutas=False,
        **opcoes,
    )


def _repos(criados: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "codigo": range(len(criados)),
            "repo_id": [str(i + 1) for i in range(len(criados))],
            "principal": "Zig",
            "criado": pd.to_datetime(criados),
            "elegivel": True,
        }
    )


def test_commit_com_o_mesmo_sha_em_dois_repositorios_conta_uma_vez(tmp_path):
    from adapters.coleta_csv import carga_duckdb

    git = [
        _linha("1", "commit", "ana", "2022-03-01T10:00:00Z", "a.zig"),
        _linha("2", "commit", "ana", "2022-03-01T10:05:00Z", "a.zig"),  # outra data, mesmo SHA
    ]
    for linha in git:
        linha["sha"] = "abc"
    repos = _repos(["2020-01-01", "2020-01-01"])  # criados no mesmo instante: desempata o repo_id
    antigo = carga_duckdb.carrega(_pedido(tmp_path / "a", git, [], repos))
    assert antigo.estatisticas["commits_duplicados_descartados"] == 0  # a chave antiga não vê o SHA
    sha = carga_duckdb.carrega(_pedido(tmp_path / "b", git, [], repos, commits_pelo_sha=True))
    assert sha.estatisticas["shas_em_mais_de_um_repositorio"] == 1
    assert sha.estatisticas["commits_duplicados_descartados"] == 1


def test_sem_contas_de_sistema_tira_migracao_uuid_e_bots_nomeados(tmp_path):
    from adapters.coleta_csv import carga_duckdb

    git = [_linha("1", "commit", "ana", "2019-01-01T00:00:00Z", "a.zig")]
    logins = [
        "twisted-trac", "vicuna", "coqbot", "85eec1a4-3d04-4b4d-b711-d4db03337c41",
        "tracy", "abstract", "ana", "Mantis_import", "JirA44",
    ]  # fmt: skip
    api = [_linha("1", "issue", n, "2022-04-01T00:00:00Z", None, "Zig", True) for n in logins]
    repos = _repos(["2020-01-01"])
    todos = carga_duckdb.carrega(_pedido(tmp_path / "a", git, api, repos))
    sem = carga_duckdb.carrega(_pedido(tmp_path / "b", git, api, repos, sem_contas_de_sistema=True))
    assert len(todos.eventos) == len(logins) + 1
    # Ficam tracy, abstract, ana (issue) e a ana do commit, que é a mesma pessoa de login, e JirA44,
    # que é uma pessoa mesmo casando com a regra de migração.
    assert sem.estatisticas["contribuidores_finais"] == 4
