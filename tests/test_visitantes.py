"""Visitantes: quem tem uma ocasião só, contado por ano de chegada com 12 meses de folga."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import visitantes


def _pessoas() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "primeiro": pd.to_datetime(["2020-03-01", "2020-05-01", "2021-01-10", "2025-06-01"]),
            "ultimo": pd.to_datetime(["2020-03-01", "2023-01-01", "2021-01-10", "2026-09-01"]),
            "codigo_do_primeiro": [1, 1, 2, 2],
            "tipo_do_primeiro": ["issues", "commits", "issues", "commits"],
            "codou": [False, True, False, True],
            "ocasioes": [1, 5, 1, 3],
        }
    )


def test_so_entram_anos_com_folga_de_12_meses():
    # Fim da coleta em set/2026: quem chegou em 2025 ainda pode voltar.
    p = visitantes.marca_visitantes(_pessoas())
    assert sorted(p["ano"].unique()) == [2020, 2021]


def test_por_ano_conta_visitantes_e_porcentagem():
    t = visitantes.por_ano(visitantes.marca_visitantes(_pessoas())).set_index("ano")
    assert t.loc[2020, "chegadas"] == 2
    assert t.loc[2020, "visitantes"] == 1
    assert t.loc[2020, "pct_visitantes"] == 50
    assert t.loc[2021, "visitantes_so_discussao"] == 1


def test_portas_de_entrada_ordena_pelos_visitantes():
    p = visitantes.marca_visitantes(_pessoas())
    repos = pd.DataFrame({"codigo": [1, 2], "repo_name": ["a/x", "b/y"]})
    t = visitantes.portas_de_entrada(p, repos)
    assert list(t["visitantes"]) == [1, 1]
    assert t["pct_dos_visitantes_da_linguagem"].sum() == 100
