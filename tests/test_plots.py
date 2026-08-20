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
            "pyramid_window_months": {"esem14": JANELA_M, "ieice16": 3, "default": 3},
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
    """Cada artigo com a sua janela, e a banda de 90 dias (seções 20, 21 e 40).

    O 12 do ESEM14 saiu de medição em pixel e não da regra de nenhum artigo; o 3
    do IEICE16 é literal na p.1306. A banda (90d) não é `band_months` × 365.25/12
    (= 91.3125). Mexer aqui refaz a seção 20.
    """
    cfg = yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text())
    assert cfg["plots"]["pyramid_window_months"] == {"esem14": 12, "ieice16": 3, "default": 3}
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


# ---------------------------------------------------------------------------
# Dispersões da seção 2.3 do IEICE16 (Fig.3)
# ---------------------------------------------------------------------------
def test_scatter_sem_corte_nao_desenha_regua():
    """Fig.3 descreve o dataset e não tem corte nenhum a marcar.

    A régua vermelha da Fig.5 é o zero que atribui o tipo, e a da Fig.2 do MSR14
    são as medianas que definem o quadrante. Desenhar uma linha na Fig.3
    inventaria uma divisória que o artigo não tem.
    """
    import matplotlib.pyplot as plt

    x = pd.Series([1.0, 2.0])
    y = pd.Series([3.0, 4.0])

    _, com = plt.subplots()
    plots._scatter(com, x, y, 0.0, 0.0, "x", "y")
    _, sem = plt.subplots()
    plots._scatter(sem, x, y, None, None, "x", "y")

    assert len(com.lines) == 2
    assert len(sem.lines) == 0
    plt.close("all")


def test_regua_da_fig3_e_a_do_artigo():
    """Os ticks saem da figura publicada, medidos em pixel (seção 39.1).

    Deixar no autolocator faria a régua acompanhar o dado, e é justamente a
    comparação com a régua impressa que mostra o lado de código ficando baixo.
    """
    cfg = yaml.safe_load((CONFIG_DIR / "checkpoints.yaml").read_text())["figures"]["ieice16_fig3"]
    assert cfg["xticks"] == [0, 10000, 20000, 30000, 40000, 50000, 60000]
    assert cfg["yticks"] == [0, 50000, 100000, 150000, 200000, 250000]
    # mxcl/homebrew e rails/rails, os dois que o artigo nomeia dentro do gráfico.
    assert cfg["highlight"] == [79163, 78852]


def test_regua_da_fig2_e_a_do_artigo():
    """Fig.2 do IEICE16: 5.000 dias em x, 12.000 contribuidores em y (seção 39.1)."""
    cfg = yaml.safe_load((CONFIG_DIR / "checkpoints.yaml").read_text())["figures"]["ieice16_fig2"]
    assert cfg["xticks"] == [0, 1000, 2000, 3000, 4000, 5000]
    assert cfg["yticks"] == [0, 2000, 4000, 6000, 8000, 10000, 12000]
    assert cfg["highlight"] == [79163, 78852]


# ---------------------------------------------------------------------------
# Janela por artigo (seção 40)
# ---------------------------------------------------------------------------
def test_janela_sai_do_artigo_pedido(monkeypatch):
    monkeypatch.setattr(plots, "settings", lambda: _cfg("active"))
    assert plots.janela_meses("esem14") == 12
    assert plots.janela_meses("ieice16") == 3
    assert plots.janela_meses() == 3


def test_artigo_desconhecido_falha_alto(monkeypatch):
    """Cair no default calado desenharia a figura com a regra de outro artigo."""
    monkeypatch.setattr(plots, "settings", lambda: _cfg("active"))
    with pytest.raises(ValueError, match="não declara"):
        plots.janela_meses("esem15")


def test_flag_da_cli_sobrescreve_os_dois_artigos(monkeypatch):
    """`--window-months 4` é como se varre outro valor sem editar arquivo."""
    from pyramid import config

    monkeypatch.setattr(plots, "settings", lambda: _cfg("active"))
    try:
        config.set_pyramid_window(4)
        assert plots.janela_meses("esem14") == 4
        assert plots.janela_meses("ieice16") == 4
    finally:
        config.set_pyramid_window(None)


def test_janela_nao_positiva_e_recusada():
    from pyramid import config

    with pytest.raises(ValueError, match="positiva"):
        config.set_pyramid_window(0)


def test_janela_maior_traz_mais_gente_para_a_banda_1(monkeypatch):
    """A janela é o que decide, e a figura muda com ela: 3 meses corta os inativos.

    Mesma pirâmide, duas janelas: com 12 meses a banda 1 tem os quatro (um ativo
    e três parados há 400 dias), com 3 meses sobra o ativo.
    """
    monkeypatch.setattr(plots, "settings", lambda: _cfg("active"))
    largo = plots.pyramid_frame(_df(), T, 24)
    estreito = plots.pyramid_frame(_df(), T, 3)
    assert largo[largo["band"] == 1][list(snapshots.CATEGORIES)].to_numpy().sum() == 4
    assert estreito[estreito["band"] == 1][list(snapshots.CATEGORIES)].to_numpy().sum() == 1


@pytest.mark.checkpoint
def test_piramide_do_ieice16_desenha_a_populacao_que_gerou_o_tipo():
    """Com a janela do IEICE16, a Fig.6 mostra a MESMA gente que virou CCR e NCR.

    A janela de 3 meses é a regra que o artigo escreve (p.1306) e é a que o
    `metrics` usa. Enquanto a figura usava 12 meses, o painel do projeto mostrava
    uma população e o rótulo de tipo ao lado vinha de outra. Este teste é o que
    trava a coerência: some se alguém mexer na janela do ieice16 sem mexer em
    `periods.inactivity_months`.

    Lê parquet e só parquet. Os ids vão explícitos porque `metrics.load_all()` sem
    escopo pergunta a lista ao banco, e teste de checkpoint tem de rodar no CI,
    que não tem dump nem banco de pé.
    """
    from pyramid import metrics

    ids = [79163, 78852, 25875, 91020]  # homebrew, rails, jquery, gitlabhq
    faltando = [s for s in ids if not (metrics.path(s).exists() and snapshots.path(s).exists())]
    if faltando:
        pytest.skip(f"faltam parquets de {faltando}: rode `pyramid run-all`")

    t = pd.Timestamp(snapshots.classification_snapshot())
    m = metrics.load_all(ids)
    m = m[m["snapshot"] == t].set_index("scope_id")

    for sid in ids:
        frame = plots.pyramid_frame(snapshots.load(sid), t, plots.janela_meses("ieice16"))
        desenhados = int(frame[list(snapshots.CATEGORIES)].to_numpy().sum())
        assert desenhados == int(m.loc[sid, "coding"] + m.loc[sid, "non_coding"])
