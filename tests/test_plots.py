"""Guardas da população da pirâmide (docs/replicacao/discrepancias.md seção 18 e seção 19).

A Fig.2 do ESEM14 desenha quem **está na comunidade** no snapshot: o artigo diz
que o contribuidor termina quando deixa o projeto, e a legenda da Fig.1 conta
dois de três developers por isso. O `stock` (todo mundo que já passou) foi
tentado e descartado: enche as bandas 9-11 do blueprint-css, vazias no artigo.
A LARGURA da janela é 12 meses, fixada pela medição em pixel da figura (seção 20:
L1 mínimo nos quatro painéis). O `inactivity_months: 3` das métricas fica de
fora: são duas janelas diferentes de propósito. Estes testes prendem a população e o
fato de a janela vir do settings; o valor 12 é prendido em `test_settings`.
"""

import pandas as pd
import pytest
import yaml

from pyramid import plots, snapshots
from pyramid.config import CONFIG_DIR

T = pd.Timestamp("2011-12-31")


JANELA_M = 12


def _cfg(populacao: str) -> dict:
    return {
        "plots": {
            "pyramid_population": populacao,
            "pyramid_window_months": JANELA_M,
        },
        "periods": {"band_months": 3},
    }


def _df() -> pd.DataFrame:
    """Banda 0 só com ativos; banda 1 com 1 ativo e 3 inativos.

    Reproduz em miniatura a forma real: quem entrou na janela é ativo por
    definição, então o filtro só morde da banda 1 para cima.

    Quem decide não é mais a coluna `active` (essa é a janela de 3 meses do
    `classify`) e sim `idle_days` contra a janela de `plots` (seção 19). Os inativos
    aqui estão a 400 dias, bem além dos ~365 da janela; os ativos a 10.
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
            "idle_days": [10.0 if a else 400.0 for _, _, a in linhas],
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
    mudou e a seção 18 precisa ser reaberta. Ruído de plotagem não produz isso.
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


def test_default_do_settings_e_active():
    """O default versionado é o que reproduz o artigo. Trocar exige justificar.

    `stock` foi tentado e descartado (discrepancias.md seção 18 superada / seção 19): o
    ESEM14 tira da pirâmide quem já saiu, e o estoque enche as bandas 9-11 do
    blueprint-css, vazias na Fig.2.
    """
    cfg = yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text())
    assert cfg["plots"]["pyramid_population"] == "active"


def test_janela_e_banda_versionadas_sao_as_medidas_na_figura():
    """12 meses e 90 dias saíram de medição em pixel, não de convenção (seção 20/seção 21).

    São dois valores que a simetria pede para mudar e a figura proíbe: a janela
    da pirâmide (12m) não é a das métricas (`inactivity_months: 3`), e a banda
    (90d) não é `band_months` × 365.25/12 (= 91.3125). Mexer aqui refaz a seção 20.
    """
    cfg = yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text())
    assert cfg["plots"]["pyramid_window_months"] == 12
    assert cfg["periods"]["band_days"] == 90
    assert cfg["periods"]["inactivity_months"] == 3


# ---------------------------------------------------------------------------
# Régua do artigo na Fig.2 (checkpoints.yaml esem14_fig2.x_ticks)
# ---------------------------------------------------------------------------
def _frame(maior: int) -> pd.DataFrame:
    return pd.DataFrame({"band": [0], "non_coding": [0], "moved": [0], "coding": [maior]})


def test_xticks_do_artigo_sao_espelhados_com_zero(monkeypatch):
    """Tick declarado como [50, 100] vira 100/50/0/50/100, sem sinal."""
    monkeypatch.setattr(plots, "settings", lambda: _cfg("active"))
    import matplotlib.pyplot as plt

    _, ax = plt.subplots()
    plots.draw_pyramid(ax, _frame(30), xticks=[50, 100])
    assert list(ax.get_xticks()) == [-100.0, -50.0, 0.0, 50.0, 100.0]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["100", "50", "0", "50", "100"]
    plt.close("all")


def test_xticks_do_artigo_nao_recortam_barra_que_transborda(monkeypatch):
    """Barra maior que o último tick continua inteira dentro do eixo.

    O transbordo é o achado (a replicação conta mais gente que o artigo); recortar
    a barra na régua do artigo esconderia exatamente a divergência.
    """
    monkeypatch.setattr(plots, "settings", lambda: _cfg("active"))
    import matplotlib.pyplot as plt

    _, ax = plt.subplots()
    plots.draw_pyramid(ax, _frame(180), xticks=[50, 100])
    assert ax.get_xlim()[1] >= 180
    assert list(ax.get_xticks()) == [-100.0, -50.0, 0.0, 50.0, 100.0]
    plt.close("all")


def test_pdf_da_figura_nao_carrega_relogio(tmp_path, monkeypatch):
    """Duas gravações da mesma figura dão o mesmo arquivo PDF.

    O PDF do matplotlib grava CreationDate por padrão. Com o relógio dentro do
    arquivo, rodar o pipeline duas vezes suja o diff do repositório e a
    conferência por checksum deixa de valer.
    """
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plots, "out_dir", lambda: tmp_path)
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    plots._save(fig, "primeira")
    primeiro = (tmp_path / "primeira.pdf").read_bytes()

    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    plots._save(fig, "segunda")
    segundo = (tmp_path / "segunda.pdf").read_bytes()

    assert b"CreationDate" not in primeiro
    assert primeiro == segundo
    plt.close("all")
