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
    # Saída é definitiva: B para em 2020 e volta em 2022, então 2020 é pausa, e C para em 2021
    # e volta em 2024, então 2021 também. Só A sai em 2021 e B em 2022.
    # 2023 é o último ano completo: D, que só abriu uma issue em dez/2023, já conta como saída,
    # com o selo de provisório. 2024 é o ano da coleta e fica sem saída.
    assert list(t.loc[[2020, 2021, 2022, 2023], "saidas"]) == [0, 1, 1, 1]
    assert list(t["pausas"]) == [1, 1, 0, 0, 0]
    assert list(t["provisorio"]) == [False, False, False, True, False]
    assert np.isnan(t.loc[2024, "saidas"])
    assert list(t.loc[[2020, 2021, 2022, 2023], "crescimento_natural_pct"]) == [100, 0, -100, 0]


def test_fluxos_por_periodo_de_atividade_bate_com_tabela_anual():
    f = vitalidade.fluxos(_eventos(), FIM, "Y", vida_unica=False)
    t = vitalidade.tabela_anual(vitalidade.pessoa_ano(_eventos(), FIM), FIM)
    t = t[t["ano"] <= 2023]
    assert [p.year for p in f["periodo"]] == [2020, 2021, 2022, 2023]
    assert f["populacao"].tolist() == t["ativos"].tolist()
    assert f["nascimentos"].tolist() == t["novatos"].tolist()
    assert f["voltas"].tolist() == t["voltas"].tolist()
    # Cada período de atividade é uma vida: a pausa conta como óbito.
    assert f["obitos"].iloc[:3].tolist() == (t["saidas"] + t["pausas"]).iloc[:3].tolist()


def test_fluxos_de_vida_unica_nao_tem_volta_e_conta_os_vivos_nas_pausas():
    f = vitalidade.fluxos(_eventos(), FIM, "Y")
    # B está viva em 2021 (pausa) e C em 2022 e 2023: a população é a dos vivos.
    assert f["populacao"].tolist() == [2, 3, 2, 2]
    assert f["nascimentos"].tolist() == [2, 1, 0, 1]
    assert (f["voltas"] == 0).all()
    assert f["obitos"].tolist() == [0, 1, 1, 1]  # o último ano completo entra, provisório


def test_fluxos_trimestral_conta_quem_esta_no_intervalo():
    """A conta em 2020Q2 e 2020Q3 sem evento neles: o período de atividade dela cobre."""
    f = vitalidade.fluxos(_eventos(), FIM, "Q", vida_unica=False).set_index("periodo")
    seis = f.loc[pd.Period("2020Q1") : pd.Period("2021Q2")]
    assert seis["populacao"].tolist() == [1, 2, 1, 1, 2, 1]
    assert seis["nascimentos"].tolist() == [1, 1, 0, 0, 1, 0]
    assert seis["obitos"].tolist() == [0, 1, 0, 0, 1, 1]
    assert f.index[-1] == pd.Period("2024Q1")


def test_tabela_anual_falha_quando_a_conta_nao_fecha():
    pa = vitalidade.pessoa_ano(_eventos(), FIM)
    pa.loc[(pa["contributor_id"] == 1) & (pa["ano"] == 2021), "saida"] = False
    with pytest.raises(ValueError, match="conta não fecha"):
        vitalidade.tabela_anual(pa, FIM)


def test_taxa_saida_por_faixa():
    t = vitalidade.taxa_saida_por_faixa(vitalidade.pessoa_ano(_eventos(), FIM), FIM)
    t = t.set_index(["ano", "faixa"])
    assert t.loc[(2021, "0-1"), "ativos"] == 1
    assert t.loc[(2021, "0-1"), "taxa_saida"] == 0.0  # C parou em 2021, mas voltou: pausa
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
    bt = vitalidade.backtest(
        _pa_estavel(), fim, ultimo_ano=2015, teto=False, regra=vitalidade.RegraCenario(min_saidas=1)
    )
    assert sorted(bt["ano"].unique()) == [2012, 2013, 2014, 2015]
    total = bt[bt["faixa"] == "total"]
    assert (total["real"] == 15).all()
    assert total["coorte"].tolist() == pytest.approx([15] * 4)
    assert total["conservador"].tolist() == pytest.approx([15] * 4)
    assert (total["cobre"] == 1).all()
    assert (bt["abre_coorte"].dropna() == 0).all()

    # Sem nenhum ano com 1000 saídas, os cenários caem na permanência do coorte.
    sem_validos = vitalidade.backtest(
        _pa_estavel(), fim, 2015, teto=False, regra=vitalidade.RegraCenario(min_saidas=1000)
    )
    assert sem_validos["pessimista"].tolist() == pytest.approx(sem_validos["coorte"].tolist())

    futuro = vitalidade.projeta_futuro(
        _pa_estavel(), fim, 2015, 3, teto=False, regra=vitalidade.RegraCenario(min_saidas=1)
    )
    futuro = futuro[futuro["faixa"] == "total"]
    assert futuro["previsto"].tolist() == pytest.approx([15] * 15)


def test_cenarios_por_taxa_com_janela():
    """Ativos totais 10, 20, 40, 40; novatos 10, 15, 20, 12. Taxas: 1,5, 1,0, 0,3."""
    pop = pd.DataFrame(
        {0: [10, 15, 20, 12], 1: [0, 5, 20, 28]}, index=[2020, 2021, 2022, 2023]
    ).reindex(columns=range(10), fill_value=0)
    saidas = pd.DataFrame(0.0, index=pop.index, columns=range(vitalidade.BANDAS))
    regra = vitalidade.RegraCenario(janela=2, novatos_por_taxa=True)
    c = vitalidade.cenarios(pop, saidas, 2023, regra)
    # A janela de 2 anos fica só com 2022 e 2023 (taxas 1,0 e 0,3); o 1,5 de 2021 sai.
    assert c["pessimista"][1] == pytest.approx(0.3)
    assert c["otimista"][1] == pytest.approx(1.0)


def _eventos_aleatorios() -> pd.DataFrame:
    """300 pessoas com rajadas no mesmo dia, silêncios longos e os sete tipos de evento."""
    rng = np.random.default_rng(7)
    tipos = ["commits", "pull_requests", "issues", "issue_comments", "issue_events"]
    linhas = []
    for pessoa in range(300):
        dia = pd.Timestamp("2010-01-01") + pd.Timedelta(days=int(rng.integers(0, 2000)))
        for _ in range(int(rng.integers(1, 12))):
            dia += pd.Timedelta(days=int(rng.choice([0, 3, 40, 200, 400, 900])))
            for _ in range(int(rng.integers(1, 5))):
                instante = dia + pd.Timedelta(seconds=int(rng.integers(0, 86400)))
                linhas.append((pessoa, str(rng.choice(tipos)), instante))
    return pd.DataFrame(linhas, columns=["contributor_id", "event_type", "timestamp"])


def test_periodos_igual_ao_profile_do_motor():
    from pyramid.classify import profile

    ev = _eventos_aleatorios()
    esperado = profile(ev, vitalidade.TIPOS_CODING, vitalidade.GAP_DIAS)
    pd.testing.assert_frame_equal(vitalidade.periodos(ev), esperado)


def test_compacta_nao_muda_nenhuma_metrica():
    ev = _eventos_aleatorios()
    pequeno = vitalidade.compacta(ev)
    assert len(pequeno) < len(ev)
    fim = ev["timestamp"].max()

    pa_cheio = vitalidade.pessoa_ano(ev, fim)
    pa_pequeno = vitalidade.pessoa_ano(pequeno, fim)
    pd.testing.assert_frame_equal(pa_cheio, pa_pequeno)
    pd.testing.assert_frame_equal(
        vitalidade.tabela_anual(pa_cheio, fim), vitalidade.tabela_anual(pa_pequeno, fim)
    )
    pd.testing.assert_frame_equal(vitalidade.duracoes(ev, fim), vitalidade.duracoes(pequeno, fim))
    for freq in ("Y", "Q"):
        pd.testing.assert_frame_equal(
            vitalidade.fluxos(ev, fim, freq), vitalidade.fluxos(pequeno, fim, freq)
        )


def test_compacta_em_pedacos_da_o_mesmo_resultado():
    """Compactar cada pedaço e juntar equivale a compactar tudo: vale para coletas enormes."""
    ev = _eventos_aleatorios()
    corte = len(ev) // 3
    pedacos = [ev.iloc[:corte], ev.iloc[corte : 2 * corte], ev.iloc[2 * corte :]]
    em_pedacos = vitalidade.compacta(pd.concat([vitalidade.compacta(p) for p in pedacos]))
    inteiro = vitalidade.compacta(ev)
    pd.testing.assert_frame_equal(em_pedacos, inteiro)
    # E o resultado não muda se for compactado de novo.
    pd.testing.assert_frame_equal(vitalidade.compacta(inteiro), inteiro)


def test_kaplan_meier_de_amostra_enorme_fica_com_um_ponto_por_dia(monkeypatch):
    rng = np.random.default_rng(3)
    anos = rng.uniform(0, 5, 3000)
    dur = pd.DataFrame({"duracao_anos": anos, "saiu": rng.random(3000) < 0.7})
    completa = vitalidade.kaplan_meier(dur)
    monkeypatch.setattr(vitalidade, "MAX_PONTOS_KM", 100)
    fina = vitalidade.kaplan_meier(dur)
    assert len(fina) < len(completa)
    assert len(fina) <= 5 * 366
    # Cada ponto que sobra é um ponto da curva completa, com o mesmo S.
    juntos = fina.merge(completa, on="anos", suffixes=("_fina", "_completa"))
    assert len(juntos) == len(fina)
    assert np.allclose(juntos["S_fina"], juntos["S_completa"])


def test_dois_eventos_no_mesmo_ano_bissexto_sao_um_periodo_so():
    """1/jan e 31/dez de 2024 distam 365,67 dias e, ainda assim, são o mesmo ano."""
    linhas = [
        (1, "commits", "2019-09-06 23:13:20"),
        (1, "commits", "2024-01-01 02:23:05"),
        (1, "commits", "2024-12-31 18:16:16"),
        (2, "commits", "2016-01-01 00:00:10"),
        (2, "commits", "2016-12-31 12:00:00"),
        (2, "commits", "2018-06-01 00:00:00"),
    ]
    ev = pd.DataFrame(linhas, columns=["contributor_id", "event_type", "timestamp"])
    ev["timestamp"] = pd.to_datetime(ev["timestamp"])
    spans = vitalidade.periodos(ev)
    # A pessoa 1 tem dois períodos (2019 e 2024); a 2 também (2016 e 2018), nenhum partido no ano.
    assert spans.groupby("contributor_id").size().to_dict() == {1: 2, 2: 2}
    fim = pd.Timestamp("2027-01-01")
    pa = vitalidade.pessoa_ano(ev, fim)  # antes falhava com (pessoa, ano) repetido
    assert not pa.duplicated(["contributor_id", "ano"]).any()
    vitalidade.tabela_anual(pa, fim)


def test_crescimento_liquido_conta_as_voltas():
    t = vitalidade.tabela_anual(vitalidade.pessoa_ano(_eventos(), FIM), FIM).set_index("ano")
    # Em 2022: 1 ativo (a pessoa 2, que volta e sai), 0 novatos, 1 saída, 1 volta, 0 pausas.
    assert t.loc[2022, "crescimento_natural_pct"] == -100
    assert t.loc[2022, "crescimento_liquido_pct"] == 0
    # Em 2020 a pessoa 2 pausa: o natural não vê, o líquido sim.
    assert t.loc[2020, "crescimento_natural_pct"] == 100
    assert t.loc[2020, "crescimento_liquido_pct"] == 50


def test_so_quem_codou_guarda_os_eventos_de_discussao_de_quem_codou():
    ev = _eventos()
    so_codigo = vitalidade.so_quem_codou(ev)
    # A pessoa 4 só abriu issue e sai. A 2 discutiu e depois commitou: fica com os dois.
    assert set(so_codigo["contributor_id"]) == {1, 2, 3}
    assert (so_codigo["contributor_id"] == 2).sum() == 2


def test_composicao_trimestral_poe_cada_pessoa_na_banda_de_90_dias():
    ev = pd.DataFrame(
        [
            (1, "commits", "2023-12-20"),  # entrou há 12 dias do fim de 2023: banda 0
            (2, "commits", "2023-06-01"),  # 214 dias: banda 2
            (3, "issues", "2020-01-01"),  # 1461 dias: banda 16
            (3, "issues", "2023-11-01"),
        ],
        columns=["contributor_id", "event_type", "timestamp"],
    )
    ev["timestamp"] = pd.to_datetime(ev["timestamp"])
    pa = vitalidade.pessoa_ano(ev, pd.Timestamp("2026-01-01"))
    t = vitalidade.composicao_trimestral(pa).set_index(["ano", "band"])
    assert t.loc[(2023, 0), "coding"] == 1
    assert t.loc[(2023, 2), "coding"] == 1
    assert t.loc[(2023, 16), "non_coding"] == 1


def test_tira_pessoas_de_um_dia():
    ev = pd.DataFrame(
        [
            (1, "commits", "2023-05-01 09:00"),
            (1, "commits", "2023-05-01 18:00"),  # dois eventos no mesmo dia: fica de fora
            (2, "commits", "2023-05-01 23:59"),
            (2, "commits", "2023-05-02 00:01"),  # dois dias, a poucos minutos: fica
        ],
        columns=["contributor_id", "event_type", "timestamp"],
    )
    ev["timestamp"] = pd.to_datetime(ev["timestamp"])
    assert set(vitalidade.tira_pessoas_de_um_dia(ev)["contributor_id"]) == {2}
