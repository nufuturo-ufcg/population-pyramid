import pytest

from pyramid import snapshots



# --- guarda de datas de config (docs/discrepancias.md §7) ---------------------

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
    """Regressão do §8: o dia-do-mês não pode grudar em 30 após o 1o mês curto.

    Antes o gerador usava DateOffset(months=3) acumulado, que truncava o dia em
    2010-06-30 e nunca mais voltava para 31.
    """
    d = {t.date().isoformat() for t in snapshots.snapshot_dates(BASE_CFG)}
    assert "2013-03-31" in d and "2013-03-30" not in d
    assert "2011-12-31" in d and "2011-12-30" not in d
    assert "2012-12-31" in d
    # jun/set acabam mesmo no dia 30 — eram os que escondiam o bug
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
    assert snapshots.require_date_match(
        df, pd.Timestamp("2011-12-31"), "snapshot", "teste"
    ).equals(df)


def test_check_dates_rejeita_target_inexistente():
    import copy

    cfg = copy.deepcopy(BASE_CFG)
    cfg["snapshots"]["projection_target"] = "2013-10-01"
    with pytest.raises(ValueError, match="projection_target"):
        snapshots.check_dates(cfg)
