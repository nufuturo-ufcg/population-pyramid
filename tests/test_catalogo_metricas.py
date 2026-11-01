"""Catálogo de métricas: cobre o registro, tem os blocos completos e calcula o mesmo que o motor."""

import re
import sys
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from pyramid import attractiveness
from pyramid import catalogo_metricas as catalogo
from pyramid import vitalidade as motor

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import vitalidade as script  # noqa: E402

PARTES = ["#   O que é:", "#   Referência:", "#   Entrada:", "#   Resultado esperado:"]
SEIS_MESES = 12 * 365.25 / 12


def _eventos() -> pd.DataFrame:
    """3 mil eventos de 300 pessoas em 3 escopos, de 2012 a 2024, com semente fixa."""
    rng = np.random.default_rng(7)
    n = 3000
    dias = rng.integers(0, 13 * 365, n)
    df = pd.DataFrame(
        {
            "contributor_id": rng.integers(0, 300, n),
            "event_type": rng.choice(["commits", "pull_requests", "issue_comments", "issues"], n),
            "timestamp": pd.Timestamp("2012-01-01") + pd.to_timedelta(dias, unit="D"),
            "scope_id": rng.integers(1, 4, n),
        }
    )
    return df.sort_values("timestamp").reset_index(drop=True)


def _roda(m) -> dict:
    """As funções que o catálogo e o motor têm em comum, rodadas nos mesmos eventos."""
    eventos = _eventos()
    fim = eventos["timestamp"].max()
    pa = m.pessoa_ano(eventos, fim, False)
    dur = m.duracoes(eventos, fim)
    par = pa["contributor_id"] % 2 == 0
    taxas = {
        "a": m.taxa_saida_por_faixa(pa[par], fim),
        "b": m.taxa_saida_por_faixa(pa[~par], fim),
    }
    dur_par = dur["contributor_id"] % 2 == 0
    pop = m.populacao_por_idade(pa)
    regra = m.RegraCenario()
    ultimo = fim.year - 1
    bt = m.backtest(pa, fim, ultimo, False, regra)
    tabua = m.tabua_de_vida(dur)
    return {
        "pessoa_ano": pa,
        "tabela_anual": m.tabela_anual(pa, fim),
        "composicao": m.composicao(pa),
        "composicao_trimestral": m.composicao_trimestral(pa),
        "indice_envelhecimento": m.indice_envelhecimento(pa),
        "duracoes": dur,
        "tabua_de_vida": tabua,
        "tabuas_por_coorte": m.tabuas_por_coorte(dur),
        "taxa_saida_por_faixa": m.taxa_saida_por_faixa(pa, fim),
        "kaplan_meier": m.kaplan_meier(dur),
        "logrank": m.logrank(dur[dur_par], dur[~dur_par]),
        "padronizacao": m.padronizacao(taxas, 2022),
        "permanencia": m.permanencia(pop, 2020),
        "backtest": bt,
        "resumo_backtest": m.resumo_backtest(bt),
        "projeta_futuro": m.projeta_futuro(pa, fim, ultimo, 3, False, regra),
        "abre": [m.abre(10, 12), m.abre(12, 10), m.abre(0, 5)],
        "ccr_ncr_trimestral": m.ccr_ncr_trimestral(eventos, SEIS_MESES, round(SEIS_MESES), fim),
    }


def _igual(a, b, onde: str) -> None:
    if isinstance(a, pd.DataFrame):
        pd.testing.assert_frame_equal(a, b, obj=onde)
    elif isinstance(a, dict):
        assert a.keys() == b.keys(), onde
        for chave in a:
            _igual(a[chave], b[chave], f"{onde}.{chave}")
    elif isinstance(a, tuple | list):
        assert len(a) == len(b), onde
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            _igual(x, y, f"{onde}[{i}]")
    elif isinstance(a, np.ndarray):
        np.testing.assert_array_equal(a, b, err_msg=onde)
    else:
        assert a == b or (np.isnan(a) and np.isnan(b)), onde


@pytest.fixture(scope="module")
def do_catalogo() -> dict:
    return _roda(catalogo)


def test_registro_tem_as_linhas_do_registro_e_todas_as_metricas():
    assert set(catalogo.REGISTRO) == set(script.METRICAS)
    nas_linhas = {nome for nomes in catalogo.REGISTRO.values() for nome in nomes}
    assert nas_linhas == set(catalogo.CATALOGO)


def test_toda_metrica_tem_bloco_com_as_quatro_partes_na_ordem():
    fonte = Path(catalogo.__file__).read_text()
    blocos = re.findall(r"^# Métrica: (\w+)\n((?:#.*\n)+)", fonte, re.MULTILINE)
    nomes = [nome for nome, _ in blocos]
    assert sorted(nomes) == sorted(set(nomes)), "bloco repetido"
    assert set(nomes) == set(catalogo.CATALOGO)
    for nome, texto in blocos:
        posicoes = [texto.find(parte) for parte in PARTES]
        assert -1 not in posicoes, nome
        assert posicoes == sorted(posicoes), nome


def test_toda_metrica_aponta_para_funcao_e_coluna_que_existem(do_catalogo):
    for nome, (funcao, coluna) in catalogo.CATALOGO.items():
        assert callable(funcao), nome
        assert funcao.__doc__, f"{nome}: {funcao.__name__} sem docstring"
        saida = do_catalogo.get(funcao.__name__)
        if coluna is None or saida is None:
            continue
        colunas = saida.columns if isinstance(saida, pd.DataFrame) else saida.keys()
        assert coluna in colunas, f"{nome}: coluna {coluna!r} não está em {funcao.__name__}"


def test_o_catalogo_calcula_o_mesmo_que_o_motor(do_catalogo):
    do_motor = _roda(motor)
    assert do_catalogo.keys() == do_motor.keys()
    for nome in do_motor:
        _igual(do_catalogo[nome], do_motor[nome], nome)


def test_atratividade_igual_a_do_motor():
    pares = catalogo.pares_de_codigo(_eventos())
    cfg = {
        "attractiveness": {"min_active_devs": 5, "cutoff": "median", "stickiness_scope": "project"}
    }
    esperado = attractiveness.annual(pares, cfg=cfg)
    obtido = catalogo.atratividade_anual(pares, min_devs=5)
    pd.testing.assert_frame_equal(obtido, esperado)
    assert obtido["quadrant"].notna().any(), "o caso de teste precisa ter escopo elegível"


def test_trajetoria_e_composicao_em_pct_iguais_as_do_script():
    eventos = _eventos()
    fim = eventos["timestamp"].max()
    pa = motor.pessoa_ano(eventos, fim, False)
    anual = motor.tabela_anual(pa, fim)
    lingua = SimpleNamespace(anual=anual, pa=pa, fim=fim, fim_acompanhamento=fim)
    ctx = SimpleNamespace(
        por_lingua={"x": lingua}, p=SimpleNamespace(ano_base_indice=2019, carencia_anos=1)
    )
    do_script = script.metrica_trajetoria(ctx)
    colunas = ["saida_pct", "volta_pct", "novato_pct", "reposicao", "indice"]
    pd.testing.assert_frame_equal(
        catalogo.trajetoria(anual, 2019)[colunas], do_script["trajetoria"][colunas]
    )
    pd.testing.assert_frame_equal(
        catalogo.composicao_em_pct(pa), do_script["composicao_pct"].drop(columns="slug")
    )


def test_chance_de_seguir_e_um_menos_q():
    dur = motor.duracoes(_eventos(), pd.Timestamp("2024-12-31"))
    tabua = motor.tabua_de_vida(dur)
    assert list(catalogo.chance_de_seguir(tabua)) == list(1 - tabua["q"])


def test_o_exemplo_do_cabecalho_roda():
    exemplo = catalogo.__doc__.split("Do evento à métrica:\n\n")[1].split("\n\n")[0]
    espaco = {
        **{nome: getattr(catalogo, nome) for nome in dir(catalogo) if not nome.startswith("_")},
        "eventos": _eventos(),
    }
    exec(dedent(exemplo), espaco)
    assert {"ativos", "crescimento_natural_pct"} <= set(espaco["anual"].columns)
