import pytest

from pyramid import snapshots

# --- guarda de datas de config (docs/replicacao/discrepancias.md seção 7) ---------------------

BASE_CFG = {
    "snapshots": {
        "start": "2010-03-31",
        "end": "2013-09-30",
        "freq_months": 3,
        "classification_snapshot": "2013-09-30",
        "projection_base": ["2013-03-31", "2013-06-30"],
        "projection_target": "2013-09-30",
    }
}


def test_serie_cai_em_fim_de_mes_civil():
    """Regressão da seção 8: o dia-do-mês não pode grudar em 30 após o 1o mês curto.

    Antes o gerador usava DateOffset(months=3) acumulado, que truncava o dia em
    2010-06-30 e nunca mais voltava para 31.
    """
    d = {t.date().isoformat() for t in snapshots.snapshot_dates(BASE_CFG)}
    assert "2013-03-31" in d and "2013-03-30" not in d
    assert "2011-12-31" in d and "2011-12-30" not in d
    assert "2012-12-31" in d
    # jun/set acabam mesmo no dia 30: eram os que escondiam o bug
    assert "2013-06-30" in d and "2013-09-30" in d


def test_serie_rejeita_freq_nao_trimestral():
    import copy

    cfg = copy.deepcopy(BASE_CFG)
    cfg["snapshots"]["freq_months"] = 4
    with pytest.raises(ValueError, match="freq_months"):
        snapshots.snapshot_dates(cfg)


def test_check_dates_aceita_config_valida():
    snapshots.check_dates(BASE_CFG)


def test_check_dates_rejeita_base_inexistente():
    import copy

    cfg = copy.deepcopy(BASE_CFG)
    cfg["snapshots"]["projection_base"] = ["2013-03-30", "2013-06-30"]
    with pytest.raises(ValueError, match="projection_base"):
        snapshots.check_dates(cfg)


def test_require_date_match_falha_alto_em_vazio():
    """Nenhum filtro por data pode seguir com DataFrame vazio em silêncio."""
    import pandas as pd

    with pytest.raises(ValueError, match="não casou nenhuma linha"):
        snapshots.require_date_match(
            pd.DataFrame(), pd.Timestamp("2011-12-30"), "snapshot", "teste"
        )


def test_require_date_match_deixa_passar_nao_vazio():
    import pandas as pd

    df = pd.DataFrame({"snapshot": [pd.Timestamp("2011-12-31")]})
    assert snapshots.require_date_match(df, pd.Timestamp("2011-12-31"), "snapshot", "teste").equals(
        df
    )


def test_check_dates_rejeita_target_inexistente():
    import copy

    cfg = copy.deepcopy(BASE_CFG)
    cfg["snapshots"]["projection_target"] = "2013-10-01"
    with pytest.raises(ValueError, match="projection_target"):
        snapshots.check_dates(cfg)


def test_banda_zero_e_a_base_da_piramide():
    """Trava a ORIENTAÇÃO do eixo de idade: `band` cresce com a idade.

    `band=0` são os recém-chegados (a base larga da pirâmide) e a banda maior é
    a coorte mais velha (o topo estreito). A figura do artigo é desenhada com a
    idade crescendo para cima, então quem lê os pixels dela varre na ordem
    INVERSA desta coluna. Casar as duas ordens espelha a comparação inteira e
    foi o que aconteceu de seção 19 a seção 30 do `discrepancias.md` (ver seção 31).

    Se este teste cair, todo alvo lido em pixel (`checkpoints.yaml`
    `figures.esem14_fig2.bars_read_clojure`) precisa ser reindexado junto.
    """
    import numpy as np
    import pandas as pd

    bd = snapshots.band_days()
    idades = pd.Series([1.0, bd, bd + 1.0, 3 * bd])
    bandas = (np.ceil((idades / bd).round(9)).astype(int) - 1).clip(lower=0)

    assert list(bandas) == [0, 0, 1, 2]
    assert bandas.iloc[0] < bandas.iloc[-1], "banda tem de crescer com a idade"


# --- janela pedida na CLI (--desde/--ate) -------------------------------------


def test_janela_da_cli_reancora_as_datas_da_projecao(monkeypatch):
    """A janela desloca âncoras e checkpoint juntos.

    Sem isto, `--ate 2012-12-31` gera uma série que termina em dez/2012 e a
    projeção continua pedindo set/2013, uma data que a série não tem: o
    `require_date_match` derruba a execução inteira.
    """
    import copy

    from pyramid import config, projection

    cfg = copy.deepcopy(BASE_CFG)
    monkeypatch.setattr(config, "settings", lambda: cfg)
    monkeypatch.setattr(snapshots, "settings", lambda: cfg)

    config.set_window(fim="2012-12-31")
    try:
        a = snapshots.anchors(cfg)
        assert a["classification_snapshot"] == "2012-12-31"
        assert a["projection_target"] == "2012-12-31"
        assert a["projection_base"] == ["2012-06-30", "2012-09-30"]
        assert snapshots.classification_snapshot(cfg) == "2012-12-31"
        assert projection.checkpoint_snapshot() == "2012-12-31"
    finally:
        config.set_window(None, None)


def test_sem_janela_o_checkpoint_e_o_do_artigo(monkeypatch):
    """Janela padrão mantém o snapshot dos checkpoints do IEICE16."""
    from pyramid import config, projection

    monkeypatch.setattr(config, "checkpoints", lambda: {"types": {"snapshot": "2013-09-30"}})
    config.set_window(None, None)
    assert projection.checkpoint_snapshot() == "2013-09-30"


def test_janela_invertida_falha_alto():
    from pyramid import config

    config.set_window("2013-01-01", "2012-01-01")
    try:
        with pytest.raises(ValueError, match="janela vazia"):
            snapshots.window(BASE_CFG)
    finally:
        config.set_window(None, None)
