"""Guardas da população da pirâmide (docs/discrepancias.md §18).

A Fig.2 do ESEM14 desenha **estoque**: todo mundo que já contribuiu até o
snapshot, posicionado pela idade que alcançou. Filtrar `active` aqui foi o bug
que achatava o homebrew (banda 1 caía de 734 para 73) e esvaziava o
blueprint-css (36 pessoas para 1). Estes testes prendem essa decisão.
"""

import pandas as pd
import pytest
import yaml

from pyramid import plots, snapshots
from pyramid.config import CONFIG_DIR

T = pd.Timestamp("2011-12-31")


def _cfg(populacao: str) -> dict:
    return {"plots": {"pyramid_population": populacao}, "periods": {"band_months": 3}}


def _df() -> pd.DataFrame:
    """Banda 0 só com ativos; banda 1 com 1 ativo e 3 inativos.

    Reproduz em miniatura a forma real: quem entrou na janela é ativo por
    definição, então o filtro só morde da banda 1 para cima.
    """
    linhas = [
        (0, "coding", True),
        (0, "non_coding", True),
        (1, "coding", True),
        (1, "coding", False),
        (1, "non_coding", False),
        (1, "moved", False),
    ]
    return pd.DataFrame(
        {
            "snapshot": [T] * len(linhas),
            "band": [b for b, _, _ in linhas],
            "category": [c for _, c, _ in linhas],
            "active": [a for _, _, a in linhas],
            "contributor_id": range(len(linhas)),
        }
    )


def test_estoque_conta_quem_ja_saiu(monkeypatch):
    monkeypatch.setattr(plots, "settings", lambda: _cfg("stock"))
    f = plots.pyramid_frame(_df(), T).set_index("band")
    assert f.loc[1, snapshots.CATEGORIES].sum() == 4


def test_active_descarta_quem_ja_saiu(monkeypatch):
    monkeypatch.setattr(plots, "settings", lambda: _cfg("active"))
    f = plots.pyramid_frame(_df(), T).set_index("band")
    assert f.loc[1, snapshots.CATEGORIES].sum() == 1


def test_banda_zero_identica_nos_dois_regimes(monkeypatch):
    """Quem entrou nos últimos `band_months` é ativo por construção.

    Se algum dia a banda 0 divergir entre os regimes, a definição de `active`
    mudou e o §18 precisa ser reaberto — não é ruído de plotagem.
    """
    saidas = {}
    for pop in ("stock", "active"):
        monkeypatch.setattr(plots, "settings", lambda pop=pop: _cfg(pop))
        saidas[pop] = plots.pyramid_frame(_df(), T).set_index("band").loc[0]
    pd.testing.assert_series_equal(saidas["stock"], saidas["active"])


def test_populacao_invalida_falha_alto(monkeypatch):
    monkeypatch.setattr(plots, "settings", lambda: _cfg("ativos"))
    with pytest.raises(ValueError, match="pyramid_population"):
        plots.pyramid_frame(_df(), T)


def test_default_do_settings_e_estoque():
    """O default versionado é o que reproduz o artigo — trocar exige justificar."""
    cfg = yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text())
    assert cfg["plots"]["pyramid_population"] == "stock"
