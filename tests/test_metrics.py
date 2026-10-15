"""`metrics.newcomer_basis`: novato por banda (padrão) ou por idade real.

`from_pyramids()` não tinha teste próprio até aqui; a cobertura vinha só da
validação de ponta a ponta contra o MSR14. Estes testes prendem especificamente
o desacoplamento entre "banda da pirâmide" e "definição de novato", que o
código confundia antes: `new = band == 0` significava "menos de 3 meses" só
porque `periods.band_months` também vale 3 por coincidência de valor, não por
definição. Mudar a banda (por exemplo para testar pirâmide com banda de 1 ano)
mudava a classificação Tipo A-D em silêncio.
"""

import pandas as pd
import pytest

from pyramid import metrics


def _cfg(basis: str = "band", newcomer_max_months: int = 3) -> dict:
    return {
        "metrics": {"newcomer_basis": basis},
        "periods": {"newcomer_max_months": newcomer_max_months},
    }


def _linha(band: int, age_days: float, category: str = "coding") -> dict:
    return {
        "scope_id": 1,
        "snapshot": pd.Timestamp("2020-12-31"),
        "contributor_id": None,  # preenchido pelo chamador, precisa ser único
        "category": category,
        "band": band,
        "age_days": age_days,
        "active": True,
    }


def _df(linhas: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(linhas)
    df["contributor_id"] = range(len(df))
    return df


def test_basis_band_e_o_padrao_novato_e_banda_0(monkeypatch):
    """Comportamento de sempre, sem settings.yaml tocado: banda 0 é novato."""
    monkeypatch.setattr(metrics, "settings", lambda: _cfg("band"))
    # Banda 0 com 400 dias de idade (banda larga: 5 anos = 1800 dias por
    # banda). Sob `band`, ainda conta como novato, porque só olha a banda.
    df = _df([_linha(band=0, age_days=400.0), _linha(band=1, age_days=40.0)])
    out = metrics.from_pyramids(df)
    linha = out.iloc[0]
    assert linha["new"] == 1
    assert linha["experienced"] == 1


def test_basis_days_usa_idade_real_nao_a_banda(monkeypatch):
    """Com `days`, quem tem 400 dias não é novato mesmo caindo na banda 0.

    E quem tem 40 dias É novato mesmo caindo na banda 1 (banda larga o
    suficiente pra isso acontecer). É exatamente o desacoplamento pedido: a
    banda deixa de decidir quem é novato.
    """
    monkeypatch.setattr(metrics, "settings", lambda: _cfg("days", newcomer_max_months=3))
    df = _df([_linha(band=0, age_days=400.0), _linha(band=1, age_days=40.0)])
    out = metrics.from_pyramids(df)
    linha = out.iloc[0]
    assert linha["new"] == 1  # só quem tem 40 dias
    assert linha["experienced"] == 1  # quem tem 400 dias


def test_basis_band_e_days_concordam_quando_banda_vale_3_meses(monkeypatch):
    """A coincidência que escondia o bug: com band_months=3, os dois batem."""
    linhas = [_linha(band=0, age_days=80.0), _linha(band=1, age_days=100.0)]

    monkeypatch.setattr(metrics, "settings", lambda: _cfg("band"))
    por_banda = metrics.from_pyramids(_df(linhas))

    monkeypatch.setattr(metrics, "settings", lambda: _cfg("days", newcomer_max_months=3))
    por_dias = metrics.from_pyramids(_df(linhas))

    assert por_banda.iloc[0]["new"] == por_dias.iloc[0]["new"]
    assert por_banda.iloc[0]["experienced"] == por_dias.iloc[0]["experienced"]


def test_basis_invalido_falha_alto(monkeypatch):
    monkeypatch.setattr(metrics, "settings", lambda: _cfg("idade"))
    df = _df([_linha(band=0, age_days=10.0)])
    with pytest.raises(ValueError, match="newcomer_basis"):
        metrics.from_pyramids(df)
