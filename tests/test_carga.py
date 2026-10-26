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
    assert pd.read_parquet(pasta / "repos.parquet")["codigo"].is_unique
    meses = pd.read_parquet(pasta / "meses.parquet")
    assert set(meses["grupo"]) <= {"codigo", "discussao"}


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
