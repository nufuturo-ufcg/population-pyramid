"""Estágio 6 — figuras. Leitura pura: nada aqui recalcula método.

Toda figura sai de um parquet que outro estágio já produziu e já foi conferido
contra checkpoint. Se um número aparece aqui, ele veio de `snapshots`, `metrics`
ou `attractiveness` — este módulo não decide categoria, não corta mediana e não
classifica quadrante. Isso é deliberado: gráfico que refaz conta é gráfico que
mente sem ninguém notar.

Consequência prática: `plots` não abre o MySQL. Os rótulos vêm do cache que o
`extract` gravou no manifesto (`extract.labels()`), então as figuras se regeram
com o banco desligado.

Sobre 2013 na Fig.3 — ver docs/discrepancias.md §11.1. A pirâmide é um estoque
(olha para trás), então os quatro painéis são renderizados completos, 2013
incluído. O que não existe em 2013 é a métrica anual de stickiness, que precisa
de Y+1 e o dump acaba em out/2013. O painel leva a marca `right-censored` e
NENHUM rótulo de quadrante — exatamente o que o ESEM14 faz no parágrafo do
jekyll, onde os autores cravam "terminal" só para 2011 e falam de 2013 pela
forma ("becomes balanced shape") mais uma condicional ("we think this project
had a possibility to become attractive or fluctuating project in near future").
"""

from __future__ import annotations

import logging

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402
import pandas as pd  # noqa: E402

from . import attractiveness as attr  # noqa: E402
from . import logging_config as runlog  # noqa: E402
from . import metrics, projection, snapshots  # noqa: E402
from .config import checkpoints, settings, stage_dir  # noqa: E402
from .extract import labels  # noqa: E402

log = logging.getLogger(__name__)
# Mesmo nome do módulo: `_module()` importa pelo nome do estágio e o manifesto
# mora em output/<estágio>/. Batizar a pasta de "figures" custaria uma caça ao
# manifesto toda vez que alguém procurasse o log deste estágio.
STAGE = "plots"

# Fundo cinza com grid branco: o estilo dos gráficos dos dois artigos (ggplot2
# clássico). Não é enfeite — é para a figura ficar comparável de relance com a
# original ao lado.
BG = "#EBEBEB"
GRID = "#FFFFFF"

# Lado não-coding vai para a esquerda (valores negativos), lado coding para a
# direita, empilhado com `moved` na base. Mesma ordem da Fig.1 do IEICE16.
FILL = {
    "non_coding": "#FFFFFF",
    "moved": "#BDBDBD",
    "coding": "#4D4D4D",
}
HATCH = {"non_coding": "///", "moved": "", "coding": ""}
PT_LABEL = {
    "non_coding": "non-coding",
    "moved": "moved to coding",
    "coding": "coding",
}


def out_dir():
    return stage_dir(STAGE)


def _theme(ax) -> None:
    ax.set_facecolor(BG)
    ax.set_axisbelow(True)
    ax.grid(True, color=GRID, linewidth=0.8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, labelsize=8)


# ---------------------------------------------------------------------------
# pirâmide
# ---------------------------------------------------------------------------
def pyramid_frame(df: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    """Contagem por (banda, categoria) num snapshot.

    População controlada por `plots.pyramid_population` (ver AMBIGUIDADE 5 no
    settings.yaml). O default é `stock`: a pirâmide é um retrato acumulado, não
    a foto de quem está ativo agora. Sob `active` a Fig.2 do ESEM14 não fecha —
    o homebrew perde a barra de ~750 na banda 1 e o blueprint-css desaba para
    uma única pessoa. `metrics` continua filtrando `active` por conta própria.
    """
    cut = snapshots.require_date_match(
        df[df["snapshot"] == t], t, "snapshot", "plots.pyramid_frame"
    )
    populacao = settings()["plots"]["pyramid_population"]
    if populacao not in ("stock", "active"):
        raise ValueError(
            f"plots.pyramid_population inválido: {populacao!r}. "
            f"Use 'stock' ou 'active'."
        )
    if populacao == "active":
        cut = cut[cut["active"]]
    if cut.empty:
        return pd.DataFrame(columns=["band", *snapshots.CATEGORIES])

    piv = (
        cut.pivot_table(
            index="band", columns="category", values="contributor_id", aggfunc="size"
        )
        .reindex(columns=snapshots.CATEGORIES, fill_value=0)
        .fillna(0)
        .astype(int)
    )
    piv = piv.reindex(range(0, int(piv.index.max()) + 1), fill_value=0)
    return piv.reset_index().rename(columns={"index": "band"})


def draw_pyramid(
    ax, frame: pd.DataFrame, xmax: float | None = None, ymax: int | None = None
) -> tuple[float, int]:
    """Desenha uma pirâmide num eixo. Devolve o (xmax, ymax) usado.

    `xmax`/`ymax` existem para o chamador impor escala comum a um conjunto de
    painéis — sem isso, cada painel se auto-escala e a comparação entre eles
    vira ilusão de ótica.
    """
    bm = settings()["periods"]["band_months"]
    _theme(ax)

    if frame.empty:
        y, non, moved, coding = (pd.Series(dtype=float),) * 4
        topo = 0
    else:
        y = frame["band"].to_numpy()
        non = frame["non_coding"].to_numpy()
        moved = frame["moved"].to_numpy()
        coding = frame["coding"].to_numpy()
        topo = int(y.max())
        ax.barh(y, -non, height=0.85, color=FILL["non_coding"], hatch=HATCH["non_coding"],
                edgecolor="#4D4D4D", linewidth=0.5)
        ax.barh(y, moved, height=0.85, color=FILL["moved"], edgecolor="#4D4D4D",
                linewidth=0.5)
        ax.barh(y, coding, height=0.85, left=moved, color=FILL["coding"],
                edgecolor="#4D4D4D", linewidth=0.5)

    lim = xmax if xmax is not None else (
        max(float(non.max()), float((moved + coding).max()), 1.0) if not frame.empty else 1.0
    )
    alto = ymax if ymax is not None else topo
    ax.set_xlim(-lim * 1.08, lim * 1.08)
    ax.set_ylim(-0.8, alto + 0.8)
    ax.axvline(0, color="#4D4D4D", linewidth=0.6)

    if frame.empty:
        # Painel vazio mantém a escala dos vizinhos: o vazio é o dado (projeto
        # sem ninguém ativo), e só dá para ver isso contra a mesma régua.
        ax.text(0.5, 0.5, "nenhum contribuidor ativo", ha="center", va="center",
                transform=ax.transAxes, fontsize=8, color="#888888", style="italic")

    # Eixo x sem sinal: o lado esquerdo é contagem, não número negativo.
    # Locator inteiro obrigatório: contribuidor não é fracionário, e em painel de
    # poucas pessoas (blueprint-css tem 1) o default do matplotlib punha tick em
    # ±0.5, que o formato `.0f` abaixo renderizava como um segundo "0" no eixo.
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ticks = [t for t in ax.get_xticks() if abs(t) <= lim * 1.08]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{abs(v):.0f}" for v in ticks])

    # Eixo y em anos de idade acumulada — as bandas são de `band_months`, mas o
    # leitor pensa em anos, e é assim que os artigos rotulam.
    per_year = max(int(round(12 / bm)), 1)
    yt = list(range(0, alto + 1, per_year))
    ax.set_yticks(yt)
    ax.set_yticklabels([f"{b * bm // 12}" for b in yt])
    return lim, alto


def figure_pyramid(scope_id: int, snapshot: str | pd.Timestamp | None = None):
    """Pirâmide avulsa de um projeto num snapshot."""
    t = pd.Timestamp(snapshot or settings()["snapshots"]["classification_snapshot"])
    df = snapshots.load(scope_id)
    frame = pyramid_frame(df, t)

    fig, ax = plt.subplots(figsize=(4.2, 3.4))
    draw_pyramid(ax, frame)
    name = labels().get(int(scope_id), str(scope_id))
    ax.set_title(f"{name} — {t.date()}", fontsize=9)
    ax.set_xlabel("contribuidores", fontsize=8)
    ax.set_ylabel("idade acumulada (anos)", fontsize=8)
    _legend(fig)
    return _save(fig, f"pyramid_{scope_id}_{t.date()}")


def _legend(fig) -> None:
    from matplotlib.patches import Patch

    handles = [
        Patch(facecolor=FILL[c], hatch=HATCH[c], edgecolor="#4D4D4D", label=PT_LABEL[c])
        for c in ["non_coding", "moved", "coding"]
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=8)


def _save(fig, stem: str, rect: tuple[float, float, float, float] = (0, 0.06, 1, 1)):
    # O `rect` é por figura: quem tem suptitle precisa reservar o topo, quem tem
    # legenda embaixo precisa reservar a base. Aplicar um rect fixo aqui
    # descartaria o layout que a figura já escolheu e cortaria o título.
    fig.tight_layout(rect=rect)
    png = out_dir() / f"{stem}.png"
    pdf = out_dir() / f"{stem}.pdf"
    # bbox_inches="tight" garante que nada de texto fique fora do papel.
    fig.savefig(png, dpi=200, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    log.info("figura: %s", png.name, extra={"stage": STAGE})
    return png


# ---------------------------------------------------------------------------
# ESEM14 Fig.3 — transições
# ---------------------------------------------------------------------------
def fig3_dates() -> list[pd.Timestamp]:
    """Os quatro pontos de junho que o artigo mostra, validados contra a série.

    Junho é o mês do meio do ano coberto e o único que existe nos quatro anos
    do dataset (2010-03 é o começo, 2013-09 é o corte). `require_date_match`
    depois garante que cada data realmente saiu do parquet.
    """
    serie = set(snapshots.snapshot_dates())
    want = [pd.Timestamp(f"{y}-06-30") for y in (2010, 2011, 2012, 2013)]
    faltando = [str(d.date()) for d in want if d not in serie]
    if faltando:
        raise ValueError(
            f"Fig.3 pede snapshots que não existem na série: {faltando}. "
            "Ajuste snapshots.start/end/freq_months ou a lista da figura."
        )
    return want


def figure_fig3():
    """Fig.3 do ESEM14: as pirâmides dos mesmos projetos ao longo dos anos."""
    ck = checkpoints()["attractiveness"]
    shape_only = set(ck.get("shape_only_years", []))
    ids = [int(k) for k in ck["transitions"]]
    dates = fig3_dates()
    lbl = labels()

    frames = {
        sid: {t: pyramid_frame(snapshots.load(sid), t) for t in dates} for sid in ids
    }

    fig, axes = plt.subplots(
        len(ids), len(dates), figsize=(3.0 * len(dates), 2.5 * len(ids)), squeeze=False
    )
    for i, sid in enumerate(ids):
        # Escala comum na linha, nos DOIS eixos. A Fig.3 é sobre a pirâmide
        # mudar de forma ao longo do tempo: se cada painel se auto-escala, o
        # crescimento em altura — que é o que o artigo aponta no homebrew — some
        # da figura, porque 2013 é redesenhado do tamanho de 2010.
        row = frames[sid]
        vivos = [f for f in row.values() if not f.empty]
        xmax = max(
            (max(f["non_coding"].max(), (f["moved"] + f["coding"]).max()) for f in vivos),
            default=1,
        )
        ymax = max((int(f["band"].max()) for f in vivos), default=0)
        for j, t in enumerate(dates):
            ax = axes[i][j]
            draw_pyramid(ax, row[t], xmax=float(xmax), ymax=ymax)
            marca = "  [right-censored]" if t.year in shape_only else ""
            ax.set_title(f"{t.year}{marca}", fontsize=9)
            if j == 0:
                ax.set_ylabel(f"{lbl.get(sid, sid)}\nidade acumulada (anos)", fontsize=8)
            if i == len(ids) - 1:
                ax.set_xlabel("contribuidores", fontsize=8)

    _legend(fig)
    fig.suptitle("ESEM14 Fig.3 — transições da pirâmide populacional", fontsize=10)
    return _save(fig, "esem14_fig3_transicoes", rect=(0, 0.05, 1, 0.96))


# ---------------------------------------------------------------------------
# dispersões
# ---------------------------------------------------------------------------
def _scatter(ax, x, y, vx, vy, xlabel, ylabel):
    _theme(ax)
    ax.axvline(vx, color="#B03A2E", linewidth=0.9, linestyle="--", zorder=1)
    ax.axhline(vy, color="#B03A2E", linewidth=0.9, linestyle="--", zorder=1)
    ax.scatter(x, y, s=18, color="#333333", zorder=3)
    ax.set_xlabel(xlabel, fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)


def figure_fig2(year: int | None = None):
    """MSR14 Fig.2: magnetismo × stickiness, com as medianas como eixos.

    É a figura que *origina* os quadrantes que a ESEM14 Fig.2 depois desenha
    como pirâmides. Não está na lista do §6 da spec — fica porque é a única
    vista do critério de classificação em si, e porque os quatro projetos
    nomeados pelo ESEM14 aparecem anelados aqui, prontos para conferência.
    """
    ck = checkpoints()["attractiveness"]
    chave = next(k for k in ck if str(k).startswith("20"))
    y = attr.year_of(year or chave)

    df = attr.load()
    df = df[(df["year"] == y) & df["eligible"]]
    if df.empty:
        raise ValueError(f"Fig.2: nenhum projeto elegível em {y}.")

    lbl = labels()
    fig, ax = plt.subplots(figsize=(5.0, 4.4))
    _scatter(
        ax, df["magnetism"], df["stickiness"],
        float(df["median_magnetism"].iloc[0]), float(df["median_stickiness"].iloc[0]),
        "magnetismo", "stickiness",
    )

    nomeados = {int(k) for k in ck.get(str(chave), {})}
    alvo = df[df["scope_id"].isin(nomeados)]
    # Anel aberto por cima do ponto: sem isso a anotação flutua perto de uma
    # nuvem densa e não dá para saber a qual ponto ela se refere.
    ax.scatter(alvo["magnetism"], alvo["stickiness"], s=70, facecolors="none",
               edgecolors="#B03A2E", linewidths=1.4, zorder=4)

    meio_x = ax.get_xlim()[0] + (ax.get_xlim()[1] - ax.get_xlim()[0]) / 2
    meio_y = ax.get_ylim()[0] + (ax.get_ylim()[1] - ax.get_ylim()[0]) / 2
    for _, r in alvo.iterrows():
        # Texto sempre para dentro do gráfico: ponto na metade direita recebe
        # rótulo à esquerda, e vice-versa. Senão nomes longos saem pela borda.
        dir_x = r["magnetism"] < meio_x
        dir_y = r["stickiness"] < meio_y
        ax.annotate(
            f"{lbl.get(int(r['scope_id']), r['scope_id'])}\n({r['quadrant']})",
            (r["magnetism"], r["stickiness"]),
            textcoords="offset points",
            xytext=(14 if dir_x else -14, 12 if dir_y else -12),
            ha="left" if dir_x else "right",
            va="bottom" if dir_y else "top",
            fontsize=7, color="#B03A2E", zorder=5,
            arrowprops=dict(arrowstyle="-", color="#B03A2E", linewidth=0.6,
                            shrinkA=0, shrinkB=6),
        )

    ax.set_title(f"MSR14 Fig.2 — magnetismo × stickiness, {y}  (n={len(df)})", fontsize=9)
    return _save(fig, f"msr14_fig2_{y}")


def figure_fig5(snapshot: str | None = None):
    """IEICE16 Fig.5: CCR × NCR no snapshot de classificação, quadrantes A-D."""
    t = pd.Timestamp(snapshot or settings()["snapshots"]["classification_snapshot"])
    df = metrics.load_all()
    if df.empty:
        raise ValueError("Fig.5: sem métricas; rode `pyramid metrics` antes.")
    cut = snapshots.require_date_match(df[df["snapshot"] == t], t, "snapshot", "plots.fig5")
    cut = cut[cut["type"].notna()]

    fig, ax = plt.subplots(figsize=(5.0, 4.4))
    # Corte em ZERO, não na mediana (IEICE16 s3) — a linha desenhada tem de ser
    # a mesma que o `metrics` usou para atribuir o tipo.
    _scatter(ax, cut["ccr"], cut["ncr"], 0.0, 0.0, "CCR", "NCR")
    # Folga acima/abaixo do domínio real (CCR e NCR vivem em [-1, 1]) para os
    # rótulos de quadrante caberem sem pousar em cima dos pontos de borda.
    ax.set_xlim(-1.08, 1.08)
    ax.set_ylim(-1.30, 1.30)

    contagem = cut["type"].value_counts().to_dict()
    # O artigo lado a lado, no próprio gráfico. Esta replicação não fecha o GATE
    # exato do §9 (docs/discrepancias.md §1: sobra em A, falta em C), e uma Fig.5
    # publicada só com os meus números seria lida como reprodução exata.
    alvo = checkpoints()["types"]["counts"]
    for tipo, (px, py) in {
        "A": (0.54, 1.16), "B": (-0.54, 1.16), "C": (0.54, -1.16), "D": (-0.54, -1.16)
    }.items():
        n = contagem.get(tipo, 0)
        ref = alvo[tipo]
        marca = "" if n == ref else "  ≠"
        ax.text(px, py, f"Tipo {tipo}   n={n}   (artigo: {ref}){marca}",
                fontsize=8, ha="center", color="#B03A2E")

    ax.set_title(
        f"IEICE16 Fig.5 — CCR × NCR em {t.date()}\n"
        f"{len(cut)} projetos classificados (artigo: {checkpoints()['types']['total_classified']})"
        " — ver docs/discrepancias.md §1",
        fontsize=9,
    )
    return _save(fig, f"ieice16_fig5_{t.date()}")


# ---------------------------------------------------------------------------
# grades de pirâmides (ESEM14 Fig.2, IEICE16 Fig.6 e Fig.7)
# ---------------------------------------------------------------------------
def _fig_cfg(nome: str) -> dict:
    try:
        return checkpoints()["figures"][nome]
    except KeyError as e:  # pragma: no cover - erro de config
        raise ValueError(
            f"config/checkpoints.yaml não declara figures.{nome}; a composição "
            "dos painéis é dado do artigo e tem de vir de lá."
        ) from e


def _cell(ax, sid: int, t: pd.Timestamp, *, sub: str | None = None,
          xmax: float | None = None, ymax: int | None = None) -> None:
    """Um painel de grade: pirâmide + nome do projeto + nota de conferência."""
    draw_pyramid(ax, pyramid_frame(snapshots.load(sid), t), xmax=xmax, ymax=ymax)
    ax.set_title(labels().get(int(sid), str(sid)), fontsize=9)
    if sub:
        # Vermelho só quando há divergência; o "=" fica cinza para o olho poder
        # varrer a grade atrás do que não bate.
        cor = "#B03A2E" if "≠" in sub else "#555555"
        ax.text(0.5, -0.30, sub, transform=ax.transAxes, ha="center", va="top",
                fontsize=7.5, color=cor)


def _confere(obtido, esperado) -> str:
    """`réplica (artigo: X)` com marca quando os dois discordam."""
    o = "—" if obtido is None or (isinstance(obtido, float) and pd.isna(obtido)) else str(obtido)
    return f"{o}   (artigo: {esperado})" + ("" if o == str(esperado) else "   ≠")


def figure_grid_status():
    """ESEM14 Fig.2: as quatro pirâmides com o status de cada projeto."""
    cfg = _fig_cfg("esem14_fig2")
    chave = cfg["from_attractiveness"]
    esperado = {int(k): v for k, v in checkpoints()["attractiveness"][chave].items()}
    t = pd.Timestamp(chave)
    ano = attr.year_of(chave)

    quad = attr.load()
    quad = quad[quad["year"] == ano].set_index("scope_id")

    ids = list(esperado)
    fig, axes = plt.subplots(1, len(ids), figsize=(3.0 * len(ids), 3.2), squeeze=False)
    for j, sid in enumerate(ids):
        # Escala por painel: o artigo põe quatro projetos de portes muito
        # diferentes lado a lado e o que ele compara é a *forma*, não o
        # tamanho. Uma régua comum achataria clojure contra homebrew.
        got = quad["quadrant"].get(sid) if sid in quad.index else None
        _cell(axes[0][j], sid, t, sub=_confere(got, esperado[sid]))
        axes[0][j].set_xlabel("contribuidores", fontsize=8)
    axes[0][0].set_ylabel("idade acumulada (anos)", fontsize=8)

    _legend(fig)
    fig.suptitle(
        f"ESEM14 Fig.2 — pirâmides e status em {t.date()}"
        "   (escalas independentes por painel)",
        fontsize=10,
    )
    return _save(fig, f"esem14_fig2_status_{t.date()}", rect=(0, 0.10, 1, 0.94))


def _tipos_no_snapshot(t: pd.Timestamp) -> pd.Series:
    df = metrics.load_all()
    if df.empty:
        raise ValueError("sem métricas; rode `pyramid metrics` antes.")
    cut = snapshots.require_date_match(
        df[df["snapshot"] == t], t, "snapshot", "plots._tipos_no_snapshot"
    )
    return cut.set_index("scope_id")["type"]


def figure_grid_types():
    """IEICE16 Fig.6: dois exemplos de cada tipo (A, B, C), uma linha por tipo."""
    cfg = _fig_cfg("ieice16_fig6")
    t = pd.Timestamp(cfg["snapshot"])
    rows = {k: [int(s) for s in v] for k, v in cfg["rows"].items()}
    tipos = _tipos_no_snapshot(t)

    ncols = max(len(v) for v in rows.values())
    fig, axes = plt.subplots(len(rows), ncols, figsize=(3.2 * ncols, 2.7 * len(rows)),
                             squeeze=False)
    for i, (tipo, ids) in enumerate(rows.items()):
        for j in range(ncols):
            ax = axes[i][j]
            if j >= len(ids):
                ax.axis("off")
                continue
            sid = ids[j]
            _cell(ax, sid, t, sub=_confere(tipos.get(sid), tipo))
            if i == len(rows) - 1:
                ax.set_xlabel("contribuidores", fontsize=8)
        axes[i][0].set_ylabel(f"Tipo {tipo}\nidade acumulada (anos)", fontsize=8)

    _legend(fig)
    fig.suptitle(
        f"IEICE16 Fig.6 — exemplos de cada tipo em {t.date()}"
        "   (escalas independentes, como no original)",
        fontsize=10,
    )
    return _save(fig, f"ieice16_fig6_tipos_{t.date()}", rect=(0, 0.05, 1, 0.95))


def figure_grid_centered():
    """IEICE16 Fig.7: os dois projetos com CCR e NCR perto de zero."""
    cfg = _fig_cfg("ieice16_fig7")
    t = pd.Timestamp(cfg["snapshot"])
    ids = [int(s) for s in cfg["projects"]]
    tipos = _tipos_no_snapshot(t)
    esperado = {int(k): v for k, v in checkpoints()["types"]["examples"].items()}

    df = metrics.load_all()
    cut = snapshots.require_date_match(
        df[df["snapshot"] == t], t, "snapshot", "plots.fig7"
    ).set_index("scope_id")

    fig, axes = plt.subplots(1, len(ids), figsize=(3.4 * len(ids), 3.4), squeeze=False)
    for j, sid in enumerate(ids):
        ax = axes[0][j]
        # CCR/NCR no rótulo: o recorte desta figura é justamente "perto de 0",
        # e sem os dois números o leitor tem de aceitar a alegação na palavra.
        ccr, ncr = float(cut["ccr"].get(sid, float("nan"))), float(cut["ncr"].get(sid, float("nan")))
        _cell(ax, sid, t,
              sub=f"CCR={ccr:+.3f}  NCR={ncr:+.3f}\n{_confere(tipos.get(sid), esperado.get(sid, '?'))}")
        ax.set_xlabel("contribuidores", fontsize=8)
    axes[0][0].set_ylabel("idade acumulada (anos)", fontsize=8)

    _legend(fig)
    fig.suptitle(f"IEICE16 Fig.7 — CCR e NCR próximos de zero, {t.date()}", fontsize=10)
    return _save(fig, f"ieice16_fig7_centrados_{t.date()}", rect=(0, 0.12, 1, 0.93))


# ---------------------------------------------------------------------------
# IEICE16 Fig.8 — pirâmide medida com a projeção por cima
# ---------------------------------------------------------------------------
def _projection_frame(sub: pd.DataFrame, coluna: str) -> pd.DataFrame:
    piv = (
        sub.pivot_table(index="band", columns="category", values=coluna, aggfunc="sum")
        .reindex(columns=snapshots.CATEGORIES, fill_value=0.0)
        .fillna(0.0)
    )
    piv = piv.reindex(range(0, int(piv.index.max()) + 1), fill_value=0.0)
    return piv.reset_index().rename(columns={"index": "band"})


def figure_projection_overlay():
    """IEICE16 Fig.8: pirâmide real com a linha da projeção sobreposta."""
    cfg = _fig_cfg("ieice16_fig8")
    ids = [int(s) for s in cfg["projects"]]
    ck = checkpoints()["projection_abre"]
    alvo = pd.Timestamp(ck["target"])
    base = ck["base_snapshots"][0]

    df = projection.load()
    if df.empty:
        raise ValueError("Fig.8: sem projeção; rode `pyramid projection` antes.")
    faltam = [s for s in ids if s not in set(df["scope_id"])]
    if faltam:
        raise ValueError(
            f"Fig.8 pede projetos fora da projeção: "
            f"{[labels().get(s, s) for s in faltam]}. O filtro de "
            f"{ck['min_contributors']} contribuidores os excluiu."
        )

    fig, axes = plt.subplots(2, 3, figsize=(10.2, 6.4), squeeze=False)
    for k, sid in enumerate(ids):
        ax = axes[k // 3][k % 3]
        sub = df[df["scope_id"] == sid]
        real = _projection_frame(sub, "actual")
        pred = _projection_frame(sub, "cohort_pred")

        # As barras vêm do `actual` da própria projeção, não de um novo
        # `pyramid_frame`: a linha tem de passar sobre a mesma população que o
        # ABIRE mediu, senão a figura contradiz a Tabela 3 sem avisar.
        lim, _ = draw_pyramid(ax, real.astype({"band": int}))
        y = pred["band"].to_numpy()
        esq = -pred["non_coding"].to_numpy()
        dirr = (pred["moved"] + pred["coding"]).to_numpy()
        for série in (esq, dirr):
            ax.plot(série, y, color="#B03A2E", linewidth=1.2, linestyle="--",
                    marker="o", markersize=2.5, zorder=6)

        # Reescala se a projeção estourar a régua das barras — cortar a linha
        # esconderia justamente o erro que a figura existe para mostrar.
        pico = float(max(abs(esq).max(initial=0.0), dirr.max(initial=0.0)))
        if pico > lim:
            ax.set_xlim(-pico * 1.08, pico * 1.08)

        med = sub.loc[sub["category"] == "all", "abre_cohort"].median()
        ax.set_title(labels().get(sid, str(sid)), fontsize=9)
        ax.text(0.5, -0.28, f"ABRE(coorte, all) = {med:.3f}", transform=ax.transAxes,
                ha="center", va="top", fontsize=7.5, color="#555555")
        if k // 3 == 1:
            ax.set_xlabel("contribuidores", fontsize=8)
        if k % 3 == 0:
            ax.set_ylabel("idade acumulada (anos)", fontsize=8)

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    handles = [
        Patch(facecolor=FILL[c], hatch=HATCH[c], edgecolor="#4D4D4D", label=PT_LABEL[c])
        for c in ["non_coding", "moved", "coding"]
    ] + [Line2D([], [], color="#B03A2E", linestyle="--", marker="o", markersize=3,
                label="projeção (coorte)")]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=8)
    fig.suptitle(
        f"IEICE16 Fig.8 — medido vs. projetado em {alvo.date()} (base {base})",
        fontsize=10,
    )
    return _save(fig, f"ieice16_fig8_projecao_{alvo.date()}", rect=(0, 0.07, 1, 0.95))


# ---------------------------------------------------------------------------
# IEICE16 Tabelas 3 e 4 — não é gráfico, mas é resultado obrigatório do §6
# ---------------------------------------------------------------------------
def figure_abre_table():
    """Tabelas 3 e 4 lado a lado com o artigo, em CSV e markdown."""
    tabs = projection.tables()
    ck_abre = checkpoints()["projection_abre"]["table"]
    ck_wil = checkpoints()["projection_wilcoxon"]["table"]
    tol = float(checkpoints()["projection_abre"]["tolerance_rel"])
    ordem = [*snapshots.CATEGORIES, "all"]

    # Mesmo critério de igualdade do `validate` — importado, não recopiado: se
    # esta tabela usasse um "perto" próprio, ela poderia dizer OK numa célula
    # que o veredito oficial reprova, e o leitor não teria como saber qual crer.
    from .validate import _perto

    linhas: list[str] = [
        "# IEICE16 Tabelas 3 e 4 — réplica vs. artigo",
        "",
        f"Gerado por `pyramid plot --figure abre-table`. Tolerância relativa: {tol:.0%}.",
        "Cada célula traz `réplica (artigo)`; `≠` marca quem está fora da tolerância.",
        "",
        "## Tabela 3 — mediana do ABRE (menor é melhor)",
        "",
        "| tipo | projetos | pares | " + " | ".join(
            f"{c} coorte | {c} baseline" for c in ordem
        ) + " |",
        "|" + "---|" * (3 + 2 * len(ordem)),
    ]
    dentro_t3 = celulas_t3 = 0
    for _, r in tabs["abre"].iterrows():
        chave = "All" if r["type"] == "All types" else r["type"]
        cels = [str(r["type"]), str(int(r["projects"])), str(int(r["pairs"]))]
        for c in ordem:
            for k, rotulo in ((0, "cohort"), (1, "baseline")):
                got = float(r[f"{c}_{rotulo}"])
                exp = float(ck_abre[chave][c][k])
                ok = _perto(got, exp, tol)
                celulas_t3 += 1
                dentro_t3 += ok
                cels.append(f"{got:.4f} ({exp:.4f}){'' if ok else ' ≠'}")
        linhas.append("| " + " | ".join(cels) + " |")

    linhas += [
        "",
        "## Tabela 4 — Wilcoxon pareado, coorte vs. baseline (95%)",
        "",
        "| tipo | " + " | ".join(ordem) + " |",
        "|" + "---|" * (1 + len(ordem)),
    ]
    dentro_t4 = celulas_t4 = 0
    for _, r in tabs["wilcoxon"].iterrows():
        chave = "All" if r["type"] == "All types" else r["type"]
        cels = [str(r["type"])]
        for c in ordem:
            got = float(r[c])
            exp, exp_sig = ck_wil[chave][c]
            # O que a Tabela 4 afirma é a *decisão* (significativo ou não), e é
            # ela que tem de bater; o p exato de uma amostra menor não vai
            # coincidir e comparar só o número esconderia a concordância real.
            sig = bool(got < 0.05) if not pd.isna(got) else False
            ok = sig == bool(exp_sig)
            celulas_t4 += 1
            dentro_t4 += ok
            cels.append(
                f"{got:.5f}{'*' if sig else ''} ({float(exp):.5f}"
                f"{'*' if exp_sig else ''}){'' if ok else ' ≠'}"
            )
        linhas.append("| " + " | ".join(cels) + " |")

    termo = projection.term_split()
    ck_t = checkpoints()["projection_term"]
    linhas += [
        "",
        "`*` = significativo a 95%. Em Tab.4 o que se compara é a decisão, não o p exato.",
        "",
        "## Curto vs. longo prazo (corte em 1 ano de atividade)",
        "",
        "| medida | réplica | artigo |",
        "|---|---|---|",
        f"| ABRE mediano, curto prazo | {termo['short_term_abre_median']:.4f} "
        f"(n={termo['short_n']}) | {ck_t['short_term_abre_median']} |",
        f"| ABRE mediano, longo prazo | {termo['long_term_abre_median']:.4f} "
        f"(n={termo['long_n']}) | {ck_t['long_term_abre_median']} |",
        f"| p-valor | {termo['wilcoxon_p']:.4f} | {ck_t['wilcoxon_p']} |",
        "",
        "A inversão de curto/longo prazo está analisada em `docs/discrepancias.md` §12.3.",
        "",
        "## Resumo",
        "",
        f"- Tabela 3: **{dentro_t3}/{celulas_t3}** células dentro de {tol:.0%}.",
        f"- Tabela 4: **{dentro_t4}/{celulas_t4}** decisões de significância iguais às do artigo.",
        "",
        "O veredito formal é do `pyramid validate` — esta tabela é a vista lado a",
        "lado, e usa o mesmo critério de igualdade (`validate._perto`) para não",
        "poder discordar dele.",
        "",
    ]

    d = out_dir()
    tabs["abre"].to_csv(d / "ieice16_tab3_abre.csv", index=False)
    tabs["wilcoxon"].to_csv(d / "ieice16_tab4_wilcoxon.csv", index=False)
    md = d / "ieice16_tab3_tab4.md"
    md.write_text("\n".join(linhas), encoding="utf-8")
    log.info("tabelas: %s (Tab.3 %d/%d dentro de %.0f%%, Tab.4 %d/%d decisões iguais)",
             md.name, dentro_t3, celulas_t3, tol * 100, dentro_t4, celulas_t4,
             extra={"stage": STAGE})
    return md


FIGURES = {
    "pyramid-grid-status": figure_grid_status,
    "pyramid-transition": figure_fig3,
    "type-scatter": figure_fig5,
    "pyramid-grid-types": figure_grid_types,
    "pyramid-grid-centered": figure_grid_centered,
    "pyramid-projection-overlay": figure_projection_overlay,
    "abre-table": figure_abre_table,
    "magnet-sticky": figure_fig2,
}

# `pyramid-single` não entra no dict: é a única que exige --project, então não
# tem o que rodar em `--figure all`.
SINGLE = "pyramid-single"


def run(scopes: list[int] | None = None, *, figures: list[str] | None = None, **_) -> dict:
    """Assinatura de estágio: o 1º posicional é escopo em todo o pipeline.

    As figuras dos artigos têm projeto fixo — a composição de cada painel vem
    de `config/checkpoints.yaml: figures` — então um `--project` aqui não teria
    o que filtrar: avisa em vez de fingir que respeitou.
    """
    if scopes:
        log.warning(
            "as figuras dos artigos têm projetos fixos; --project ignorado. "
            f"Para uma pirâmide de um projeto qualquer: "
            f"pyramid plot --figure {SINGLE} --project X",
            extra={"stage": STAGE},
        )
    alvos = figures or list(FIGURES)
    man = {"stage": STAGE, "ok": {}, "failed": {}}
    for nome in alvos:
        if nome not in FIGURES:
            raise ValueError(f"figura desconhecida: {nome}. Conhecidas: {sorted(FIGURES)}")
        try:
            man["ok"][nome] = str(FIGURES[nome]().name)
        except Exception as e:  # noqa: BLE001
            man["failed"][nome] = f"{type(e).__name__}: {e}"
            log.exception("falha na figura %s", nome, extra={"stage": STAGE})
    runlog.save(STAGE, man)
    log.info("figuras: %d ok, %d falhas", len(man["ok"]), len(man["failed"]))
    return man
