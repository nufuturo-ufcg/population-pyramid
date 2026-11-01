"""Catálogo de métricas: cada métrica resolve para função real, tem as quatro partes e roda."""

import re
import sys
from pathlib import Path
from textwrap import dedent

import pandas as pd

from pyramid import catalogo_metricas as catalogo
from pyramid import vitalidade as motor

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import vitalidade as script  # noqa: E402

PARTES = ["# O que é:", "# Referência:", "# Entrada:", "# Resultado esperado:"]


def _eventos() -> pd.DataFrame:
    linhas = [
        (1, "commits", "2020-03-01"),
        (1, "commits", "2021-05-01"),
        (2, "issue_comments", "2020-06-01"),
        (2, "commits", "2022-01-15"),
        (3, "commits", "2021-02-01"),
        (3, "commits", "2024-03-01"),
    ]
    df = pd.DataFrame(linhas, columns=["contributor_id", "event_type", "timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def test_catalogo_tem_as_mesmas_metricas_do_registro():
    assert set(catalogo.CATALOGO) == set(script.METRICAS)


def test_toda_funcao_do_catalogo_existe_e_tem_docstring():
    for nome, funcoes in catalogo.CATALOGO.items():
        assert funcoes, nome
        for funcao in funcoes:
            assert callable(funcao), nome
            assert funcao.__doc__, f"{nome}: {funcao.__name__} sem docstring"


def test_todo_bloco_tem_as_quatro_partes_na_ordem():
    fonte = Path(catalogo.__file__).read_text()
    for nome in catalogo.CATALOGO:
        achou = re.search(rf"# --- {nome} -+\n(.*?)CATALOGO\[\"{nome}\"\]", fonte, re.DOTALL)
        assert achou, nome
        posicoes = [achou.group(1).find(parte) for parte in PARTES]
        assert -1 not in posicoes, nome
        assert posicoes == sorted(posicoes), nome


def test_o_exemplo_do_cabecalho_roda():
    cabecalho = catalogo.__doc__
    exemplo = cabecalho.split("roda estas mesmas):\n\n")[1].split("\n\n")[0]
    espaco = {"vitalidade": motor, "eventos": _eventos()}
    exec(dedent(exemplo), espaco)
    assert {"ativos", "crescimento_natural_pct"} <= set(espaco["anual"].columns)
    assert {"saida", "faixa"} <= set(espaco["pa"].columns)
    assert {"duracao_anos", "saiu"} <= set(espaco["dur"].columns)
