"""Métricas de vitalidade contra um caso pequeno feito à mão.

Quatro pessoas, coleta até 30/06/2024:

  A  commit 01/03/2020, 01/11/2020, 01/05/2021      sai em 2021
  B  discute 01/06/2020, commit 15/01/2022          sai em 2020; em 2022 volta, vira moved e sai
  C  commit 01/02/2021, 01/03/2024                  sai em 2021, volta em 2024, segue ativa
  D  issue 01/12/2023                               censurada (menos de 12 meses até o fim)
"""

import numpy as np
import pandas as pd
import pytest

from pyramid import vitalidade

FIM = pd.Timestamp("2024-06-30")


def _eventos() -> pd.DataFrame:
    linhas = [
        (1, "commits", "2020-03-01"),
        (1, "commits", "2020-11-01"),
        (1, "commits", "2021-05-01"),
        (2, "issue_comments", "2020-06-01"),
        (2, "commits", "2022-01-15"),
        (3, "commits", "2021-02-01"),
        (3, "commits", "2024-03-01"),
        (4, "issues", "2023-12-01"),
    ]
    df = pd.DataFrame(linhas, columns=["contributor_id", "event_type", "timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def test_faixa_fechada_embaixo():
    faixas = vitalidade.faixa_de(pd.Series([0.0, 0.999, 1.0, 4.9, 5.0, 8.0, 20.0]))
    assert list(faixas) == ["0-1", "0-1", "1-2", "3-5", "5-8", "8+", "8+"]


def test_pessoa_ano():
    pa = vitalidade.pessoa_ano(_eventos(), FIM).set_index(["contributor_id", "ano"])
    assert pa.loc[(2, 2020), "categoria"] == "non_coding"
    assert pa.loc[(2, 2022), "categoria"] == "moved"
    assert pa.loc[(2, 2022), "faixa"] == "2-3"
    assert pa.loc[(3, 2024), "faixa"] == "3-5"
    assert pa.loc[(3, 2024), "volta"]
    assert not pa.loc[(3, 2024), "saida"]


def test_tabela_anual():
    t = vitalidade.tabela_anual(vitalidade.pessoa_ano(_eventos(), FIM), FIM).set_index("ano")
    assert list(t["ativos"]) == [2, 2, 1, 1, 1]
    assert list(t["novatos"]) == [2, 1, 0, 1, 0]
    assert list(t["voltas"]) == [0, 0, 1, 0, 1]
    assert list(t["moved"]) == [0, 0, 1, 0, 0]
    assert list(t.loc[[2020, 2021, 2022], "saidas"]) == [1, 2, 1]
    assert t.loc[[2023, 2024], "saidas"].isna().all()
    assert list(t.loc[[2020, 2021, 2022], "crescimento_natural_pct"]) == [50, -50, -100]


def test_tabela_anual_falha_quando_a_conta_nao_fecha():
    pa = vitalidade.pessoa_ano(_eventos(), FIM)
    pa.loc[(pa["contributor_id"] == 1) & (pa["ano"] == 2021), "saida"] = False
    with pytest.raises(ValueError, match="conta não fecha"):
        vitalidade.tabela_anual(pa, FIM)


def test_taxa_saida_por_faixa():
    t = vitalidade.taxa_saida_por_faixa(vitalidade.pessoa_ano(_eventos(), FIM), FIM)
    t = t.set_index(["ano", "faixa"])
    assert t.loc[(2021, "0-1"), "ativos"] == 1
    assert t.loc[(2021, "0-1"), "taxa_saida"] == 1.0
    assert t.loc[(2021, "1-2"), "ativos"] == 1
    assert t.loc[(2021, "1-2"), "taxa_saida"] == 1.0
    assert np.isnan(t.loc[(2024, "3-5"), "taxa_saida"])


def test_tabua_de_vida_com_censura():
    t = vitalidade.tabua_de_vida(vitalidade.duracoes(_eventos(), FIM))
    assert list(t["l"]) == [4, 3, 1, 1]
    assert list(t["d"]) == [0, 2, 0, 0]
    assert list(t["censurados"]) == [1, 0, 0, 1]
    assert t["q"].tolist() == pytest.approx([0, 2 / 3, 0, 0])
    assert t["e"].tolist() == pytest.approx([7 / 3, 4 / 3, 2, 1])
    assert t["e_truncado"].all()


def test_tabua_sem_censura_da_a_media_da_duracao():
    dur = pd.DataFrame({"duracao_anos": [0.5, 1.5], "saiu": [True, True]})
    t = vitalidade.tabua_de_vida(dur)
    assert t["e"].tolist() == pytest.approx([1.0, 0.5])
    assert not t["e_truncado"].any()


def test_kaplan_meier_sem_censura_bate_com_a_tabua():
    dur = pd.DataFrame({"duracao_anos": [0.5, 1.5, 2.5, 3.5], "saiu": [True] * 4})
    km = vitalidade.kaplan_meier(dur)
    assert km["anos"].tolist() == [0.5, 1.5, 2.5, 3.5]
    assert km["S"].tolist() == pytest.approx([0.75, 0.5, 0.25, 0])
    tabua = vitalidade.tabua_de_vida(dur)
    assert tabua.loc[1, "S"] == pytest.approx(km.loc[0, "S"])


def test_logrank_de_amostras_iguais_nao_rejeita():
    dur = pd.DataFrame({"duracao_anos": [0.5, 1.5, 2.5, 3.5], "saiu": [True, True, False, True]})
    estatistica, p = vitalidade.logrank(dur, dur.copy())
    assert estatistica == pytest.approx(0)
    assert p == pytest.approx(1)


def _taxa(ativos: list[int], saidas: list[int]) -> pd.DataFrame:
    t = pd.DataFrame({"ano": 2020, "faixa": vitalidade.FAIXAS, "ativos": ativos})
    t["saidas"] = [float(s) for s in saidas]
    t["taxa_saida"] = t["saidas"] / t["ativos"]
    return t


def test_padronizacao_tira_o_efeito_da_composicao():
    """Mesma taxa em cada faixa, composições diferentes.

    A bruta difere (40% contra 30%). A padronizada é a mesma nas duas, e o SMR é 1.
    Pesos: ativos juntos [80, 24, 24, 24, 24, 24] / 200 = [0,4, 0,12 x 5].
    Padronizada: 0,5 x 0,4 + 0,25 x 0,6 = 0,35.
    """
    taxas = {
        "um": _taxa([60, 8, 8, 8, 8, 8], [30, 2, 2, 2, 2, 2]),
        "dois": _taxa([20, 16, 16, 16, 16, 16], [10, 4, 4, 4, 4, 4]),
    }
    t = vitalidade.padronizacao(taxas, 2020).set_index("linguagem")
    assert t.loc["um", "taxa_bruta"] == pytest.approx(0.40)
    assert t.loc["dois", "taxa_bruta"] == pytest.approx(0.30)
    assert t["taxa_padronizada"].tolist() == pytest.approx([0.35, 0.35])
    assert t["smr"].tolist() == pytest.approx([1, 1])


def test_projeta_um_ano_com_a_8_mais_aberta():
    p = np.array([10, 0, 0, 0, 0, 0, 0, 4, 5], dtype=float)
    sr = np.array([0.5, np.nan, 1, 1, 1, 1, 1, 0.25, 0.8])
    # 8+ recebe 4 x 0,25 da banda 7 e guarda 5 x 0,8 de quem já estava nela.
    proj = vitalidade.projeta_um_ano(p, sr, novatos=7, teto=False)
    assert proj.tolist() == pytest.approx([7, 5, 0, 0, 0, 0, 0, 0, 5])

    sr[0] = 1.5
    assert vitalidade.projeta_um_ano(p, sr, novatos=7, teto=True)[1] == 10


def test_permanencia_separa_quem_chega_na_8_mais():
    pop = pd.DataFrame(
        [[10, 0, 0, 0, 0, 0, 0, 4, 6, 4], [9, 5, 0, 0, 0, 0, 0, 0, 3, 6]],
        index=[2020, 2021],
        columns=range(10),
    )
    sr = vitalidade.permanencia(pop, 2021)
    assert sr[0] == 0.5
    assert np.isnan(sr[1])
    assert sr[7] == pytest.approx(3 / 4)
    assert sr[8] == pytest.approx(6 / 10)


def _pa_estavel() -> pd.DataFrame:
    """Todo ano: 8 novatos, 4 com 1 ano, 2 com 2, 1 com 3. Metade de cada idade fica."""
    linhas = []
    for ano in range(2010, 2016):
        for idade, n in [(0, 8), (1, 4), (2, 2), (3, 1)]:
            for i in range(n):
                linhas.append({"ano": ano, "idade_anos": idade, "saida": i >= n // 2})
    return pd.DataFrame(linhas)


def test_backtest_em_populacao_estavel_acerta():
    fim = pd.Timestamp("2030-01-01")
    bt = vitalidade.backtest(_pa_estavel(), fim, ultimo_ano=2015, teto=False, min_saidas=1)
    assert sorted(bt["ano"].unique()) == [2012, 2013, 2014, 2015]
    total = bt[bt["faixa"] == "total"]
    assert (total["real"] == 15).all()
    assert total["coorte"].tolist() == pytest.approx([15] * 4)
    assert total["conservador"].tolist() == pytest.approx([15] * 4)
    assert (total["cobre"] == 1).all()
    assert (bt["abre_coorte"].dropna() == 0).all()

    # Sem nenhum ano com 1000 saídas, os cenários caem na permanência do coorte.
    sem_validos = vitalidade.backtest(_pa_estavel(), fim, 2015, teto=False, min_saidas=1000)
    assert sem_validos["pessimista"].tolist() == pytest.approx(sem_validos["coorte"].tolist())

    futuro = vitalidade.projeta_futuro(_pa_estavel(), fim, 2015, 3, teto=False, min_saidas=1)
    futuro = futuro[futuro["faixa"] == "total"]
    assert futuro["previsto"].tolist() == pytest.approx([15] * 15)
