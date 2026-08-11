"""Estágio 6: figuras. Leitura pura: nada aqui recalcula método.

Toda figura sai de um parquet que outro estágio já produziu e já foi conferido
contra checkpoint. Se um número aparece aqui, ele veio de `snapshots`, `metrics`
ou `attractiveness`. Este módulo não decide categoria, não corta mediana e não
classifica quadrante. Isso é deliberado: gráfico que refaz conta é gráfico que
mente sem ninguém notar.

Consequência prática: `plots` não abre o MySQL. Os rótulos vêm do cache que o
`extract` gravou no manifesto (`extract.labels()`), então as figuras se regeram
com o banco desligado.

Sobre 2013 na Fig.3, ver docs/discrepancias.md, seção 11.1. A pirâmide é um
estoque (olha para trás), então os quatro painéis são renderizados completos,
2013 incluído. O que não existe em 2013 é a métrica anual de stickiness, que
precisa de Y+1 e o dump acaba em out/2013. O painel leva a marca
`right-censored` e nenhum rótulo de quadrante. Isso é exatamente o que o
ESEM14 faz no parágrafo do jekyll, onde os autores cravam "terminal" só para
2011 e falam de 2013 pela forma ("becomes balanced shape") mais uma
condicional ("we think this project had a possibility to become attractive or
fluctuating project in near future").
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from . import attractiveness as attr
from . import logging_config as runlog
from . import metrics, projection, snapshots
from .config import checkpoints, settings, stage_dir
from .extract import labels

log = logging.getLogger(__name__)
# Mesmo nome do módulo: `_module()` importa pelo nome do estágio e o manifesto
# mora em output/<estágio>/. Batizar a pasta de "figures" custaria uma caça ao
# manifesto toda vez que alguém procurasse o log deste estágio.
STAGE = "plots"

# Fundo cinza com grid branco: o estilo dos gráficos dos dois artigos (ggplot2
# clássico). Não é enfeite: é para a figura ficar comparável de relance com a
# original ao lado.
BG = "#EBEBEB"
GRID = "#FFFFFF"
# Régua de trimestre à esquerda do painel. Não pode ser GRID: o traço aponta
# para FORA do eixo, cai no fundo branco da figura e some. Cinza médio é a
# única cor que se lê tanto contra o branco de fora quanto contra o BG.
TICK = "#9E9E9E"

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


def out_dir() -> Path:
    """Pasta deste estágio: `output/plots/`."""
    return stage_dir(STAGE)


def _theme(ax: Axes) -> None:
    ax.set_facecolor(BG)
    ax.set_axisbelow(True)
    ax.grid(True, color=GRID, linewidth=0.8)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, labelsize=8)


def _repo(sid: int | str) -> str:
    """Rótulo curto de um projeto: só o pedaço depois da barra.

    Os três artigos nomeiam os painéis pelo repositório ("jekyll", "homebrew"),
    e o dono ocupa metade da largura útil em nomes como
    "FortAwesome/Font-Awesome". O nome completo continua nos CSVs e nas
    mensagens de erro, onde a identificação tem de ser única.
    """
    return str(labels().get(int(sid), sid)).rsplit("/", 1)[-1]


# ---------------------------------------------------------------------------
# pirâmide
# ---------------------------------------------------------------------------
def pyramid_frame(df: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    """Contagem por (banda, categoria) num snapshot.

    População controlada por `plots.pyramid_population` (ver AMBIGUIDADE 5 no
    settings.yaml). O default é `active`: o ESEM14 tira da pirâmide quem já
    saiu da comunidade (Fig.1: em t1 só dois dos três developers contam). O
    `stock` foi tentado e descartado nas seções 18 e 19 das discrepâncias. A
    largura da janela vem de `plots.pyramid_window_months` (12 meses).
    `periods.inactivity_months` (3) não entra aqui: são duas janelas
    diferentes de propósito, fixadas pela medição em pixel da Fig.2
    (seção 20).
    """
    cut = snapshots.require_date_match(
        df[df["snapshot"] == t], t, "snapshot", "plots.pyramid_frame"
    )
    cfg = settings()["plots"]
    populacao = cfg["pyramid_population"]
    if populacao not in ("stock", "active"):
        raise ValueError(
            f"plots.pyramid_population inválido: {populacao!r}. Use 'stock' ou 'active'."
        )
    if populacao == "active":
        janela = float(cfg["pyramid_window_months"]) * snapshots.DAYS_PER_MONTH
        if "idle_days" not in cut.columns:
            raise ValueError(
                "snapshots sem a coluna `idle_days`: estágio velho. "
                "Rode `pyramid snapshots --force`."
            )
        cut = cut[cut["idle_days"] <= janela]
    if cut.empty:
        return pd.DataFrame(columns=["band", *snapshots.CATEGORIES])

    piv = (
        cut.pivot_table(index="band", columns="category", values="contributor_id", aggfunc="size")
        .reindex(columns=snapshots.CATEGORIES, fill_value=0)
        .fillna(0)
        .astype(int)
    )
    piv = piv.reindex(range(0, int(piv.index.max()) + 1), fill_value=0)
    return piv.reset_index().rename(columns={"index": "band"})


def draw_pyramid(
    ax: Axes,
    frame: pd.DataFrame,
    xmax: float | None = None,
    ymax: int | None = None,
    xticks: list[float] | None = None,
) -> tuple[float, int]:
    """Desenha uma pirâmide num eixo. Devolve o (xmax, ymax) usado.

    `xmax`/`ymax` existem para o chamador impor escala comum a um conjunto de
    painéis. Sem isso, cada painel se auto-escala e a comparação entre eles
    vira ilusão de ótica.

    `xticks` fixa os ticks do lado positivo (o eixo espelha e acrescenta o 0),
    para reproduzir a régua impressa no artigo. O eixo ainda se estica se a
    barra passar do último tick: a régua é do artigo, a barra é do dado, e
    esconder o transbordo seria falsificar a comparação.
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
        ax.barh(
            y,
            -non,
            height=0.85,
            color=FILL["non_coding"],
            hatch=HATCH["non_coding"],
            edgecolor="#4D4D4D",
            linewidth=0.5,
        )
        ax.barh(y, moved, height=0.85, color=FILL["moved"], edgecolor="#4D4D4D", linewidth=0.5)
        ax.barh(
            y,
            coding,
            height=0.85,
            left=moved,
            color=FILL["coding"],
            edgecolor="#4D4D4D",
            linewidth=0.5,
        )

    lim = (
        xmax
        if xmax is not None
        else (max(float(non.max()), float((moved + coding).max()), 1.0) if not frame.empty else 1.0)
    )
    if xticks:
        lim = max(lim, float(max(xticks)))
    # Topo arredondado para a próxima fronteira de ano: o rótulo do eixo y só
    # existe na banda que fecha um ano, então uma pirâmide que termina no meio
    # do ano (blueprint-css em 2012 acaba na banda de 4 anos e meio) desenhava a
    # barra de cima acima do último rótulo, encostada na moldura, com cara de
    # figura cortada. Sobra no máximo o resto de um ano em branco, e a régua
    # passa a fechar sempre num "N years".
    por_ano = max(round(12 / bm), 1)
    bruto = ymax if ymax is not None else topo
    alto = -(-(bruto + 1) // por_ano) * por_ano - 1
    # Folga maior quando a régua é nossa: com escala automática o limite sai do
    # próprio dado, então a barra máxima terminava exatamente na moldura (o
    # blueprint-css tem 4 pessoas e o eixo ia a 4) e parecia transbordo. Com a
    # régua do artigo o limite é dele, e apertar ou afrouxar seria reescrevê-la.
    folga = 1.08 if xticks else 1.15
    ax.set_xlim(-lim * folga, lim * folga)
    ax.set_ylim(-0.8, alto + 0.8)
    # Eixo central BRANCO e por cima das barras: com banda de 90 dias há
    # trimestre em que os dois lados estão ocupados, e barra preta encostada em
    # barra preta virava um bloco só. O leitor não via onde acabava o
    # `non_coding` e começava o `coding`. Branco corta os dois.
    ax.axvline(0, color="white", linewidth=0.9, zorder=3)

    if frame.empty:
        # Painel vazio mantém a escala dos vizinhos: o vazio é o dado (projeto
        # sem ninguém ativo), e só dá para ver isso contra a mesma régua.
        ax.text(
            0.5,
            0.5,
            "nenhum contribuidor ativo",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=8,
            color="#888888",
            style="italic",
        )

    # Eixo x sem sinal: o lado esquerdo mostra contagem. O valor negativo do
    # array só orienta a barra para a esquerda; ele não aparece como número
    # real no eixo, porque contagem de contribuidor não é negativa.
    # Locator inteiro obrigatório: contribuidor não é fracionário, e em painel de
    # poucas pessoas (blueprint-css tem 1) o default do matplotlib punha tick em
    # ±0.5, que o formato `.0f` abaixo renderizava como um segundo "0" no eixo.
    if xticks:
        ticks = [-v for v in sorted(xticks, reverse=True)] + [0] + sorted(xticks)
    else:
        # Ticks contados de um lado só e espelhados, no máximo três por lado.
        # O locator padrão trabalha no eixo inteiro (-lim a +lim) e chegava a
        # nove rótulos num painel de 3,6 polegadas: em projeto grande, "320 240
        # 160 80 0 80 160 240 320" saía com os números encostados uns nos
        # outros, ilegível. O artigo usa dois ou três por lado.
        lado = [
            t
            for t in matplotlib.ticker.MaxNLocator(
                nbins=3, integer=True, steps=[1, 2, 2.5, 5, 10]
            ).tick_values(0, lim)
            if 0 < t <= lim * 1.08
        ]
        ticks = [-t for t in reversed(lado)] + [0.0] + lado
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{abs(v):.0f}" for v in ticks])

    # Eixo y em anos de idade acumulada: as bandas são de `band_months`, mas o
    # leitor pensa em anos, e é assim que o artigo rotula.
    #
    # A banda b termina em (b+1)*bm meses, então o rótulo "1 year" cai na banda
    # 3 (12 meses), não na 0. Sem tick em 0: "0 year" não existe no artigo, e um
    # tick ali sugeria uma coorte de idade zero que a figura não tem.
    #
    # Grade menor em TODA banda: a Fig.2 tem quatro linhas por ano, uma por
    # trimestre. Só as anuais deixavam a leitura de trimestre impossível, o
    # que fez a replicação parecer um bloco anual por ano.
    yt = list(range(por_ano - 1, alto + 1, por_ano))
    ax.set_yticks(yt)
    ax.set_yticklabels(
        [f"{(b + 1) * bm // 12} year" + ("s" if (b + 1) * bm // 12 > 1 else "") for b in yt]
    )
    ax.set_yticks([b + 0.5 for b in range(-1, alto + 1)], minor=True)
    ax.grid(True, which="minor", axis="y", color=GRID, linewidth=0.4)
    ax.grid(False, which="major", axis="y")
    # Traço cinza para fora em cada fronteira de banda: com quatro bandas por
    # ano o rótulo anual sozinho não diz em qual trimestre a barra está. O
    # traço é a régua de trimestre, e fica claro (0.4pt, cinza) para não
    # competir com a barra.
    ax.tick_params(
        axis="y",
        which="minor",
        length=3,
        width=0.6,
        color=TICK,
        direction="out",
        left=True,
        right=False,
    )
    return lim, alto


def figure_pyramid(scope_id: int, snapshot: str | pd.Timestamp | None = None) -> Path:
    """Pirâmide avulsa de um projeto num snapshot."""
    t = pd.Timestamp(snapshot or settings()["snapshots"]["classification_snapshot"])
    df = snapshots.load(scope_id)
    frame = pyramid_frame(df, t)

    fig, ax = plt.subplots(figsize=(4.2, 3.4))
    draw_pyramid(ax, frame)
    ax.set_title(f"{_repo(scope_id)}, {t.date()}", fontsize=9)
    ax.set_xlabel("contribuidores", fontsize=8)
    ax.set_ylabel("idade acumulada (anos)", fontsize=8)
    _legend(fig)
    return _save(fig, f"pyramid_{scope_id}_{t.date()}")


def _legend(fig: Figure) -> None:
    from matplotlib.patches import Patch

    handles = [
        Patch(facecolor=FILL[c], hatch=HATCH[c], edgecolor="#4D4D4D", label=PT_LABEL[c])
        for c in ["non_coding", "moved", "coding"]
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=8)


def _save(
    fig: Figure, stem: str, rect: tuple[float, float, float, float] = (0, 0.06, 1, 1)
) -> Path:
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


def _dump(df: pd.DataFrame, stem: str) -> Path:
    """Os pontos exatos que a figura desenhou, em CSV ao lado do PNG.

    Sem isso a única forma de conferir uma dispersão contra o artigo é medir
    pixel, que foi o que custou caro nas divergências de eixo. O CSV é o que
    entrou no `ax`, não o parquet inteiro: mesma linha, mesma coluna, mesma
    ordem de plotagem.
    """
    csv = out_dir() / f"{stem}.csv"
    df.to_csv(csv, index=False)
    log.info("dados da figura: %s", csv.name, extra={"stage": STAGE})
    return csv


# ---------------------------------------------------------------------------
# ESEM14 Fig.3: transições
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


def figure_fig3() -> Path:
    """Fig.3 do ESEM14: as pirâmides dos mesmos projetos ao longo dos anos."""
    ck = checkpoints()["attractiveness"]
    shape_only = set(ck.get("shape_only_years", []))
    ids = [int(k) for k in ck["transitions"]]
    dates = fig3_dates()

    frames = {sid: {t: pyramid_frame(snapshots.load(sid), t) for t in dates} for sid in ids}

    fig, axes = plt.subplots(
        len(ids), len(dates), figsize=(3.0 * len(dates), 2.5 * len(ids)), squeeze=False
    )
    for i, sid in enumerate(ids):
        # Escala comum na linha, nos DOIS eixos. A Fig.3 é sobre a pirâmide
        # mudar de forma ao longo do tempo: se cada painel se auto-escala, o
        # crescimento em altura (que é o que o artigo aponta no homebrew) some
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
                ax.set_ylabel(f"{_repo(sid)}\nidade acumulada (anos)", fontsize=8)
            else:
                # Escala de y é comum na linha, então repetir "1 year, 2 years,
                # ..." nos quatro painéis é tinta gasta duas vezes e largura a
                # menos para a barra. O artigo rotula só a coluna da esquerda.
                ax.tick_params(axis="y", labelleft=False)
            if i == len(ids) - 1:
                ax.set_xlabel("contribuidores", fontsize=8)

    _legend(fig)
    fig.suptitle("ESEM14 Fig.3: transições da pirâmide populacional", fontsize=10)
    return _save(fig, "esem14_fig3_transicoes", rect=(0, 0.05, 1, 0.96))


# ---------------------------------------------------------------------------
# dispersões
# ---------------------------------------------------------------------------
def _scatter(  # noqa: PLR0913, PLR0917
    ax: Axes,
    x: pd.Series,
    y: pd.Series,
    vx: float,
    vy: float,
    xlabel: str,
    ylabel: str,
) -> None:
    _theme(ax)
    ax.axvline(vx, color="#B03A2E", linewidth=0.9, linestyle="--", zorder=1)
    ax.axhline(vy, color="#B03A2E", linewidth=0.9, linestyle="--", zorder=1)
    ax.scatter(x, y, s=18, color="#333333", zorder=3)
    ax.set_xlabel(xlabel, fontsize=8)
    ax.set_ylabel(ylabel, fontsize=8)


def _anelar(
    ax: Axes,
    alvo: pd.DataFrame,
    xcol: str,
    ycol: str,
    rotulo: Callable[[pd.Series], str],
) -> None:
    """Anel aberto + nome nos projetos que o artigo nomeia no próprio gráfico.

    Sem o anel a anotação flutua perto de uma nuvem densa e não dá para saber a
    qual ponto ela se refere. É puro desenho: não entra em mediana, quadrante
    nem contagem.
    """
    ax.scatter(
        alvo[xcol],
        alvo[ycol],
        s=70,
        facecolors="none",
        edgecolors="#B03A2E",
        linewidths=1.4,
        zorder=4,
    )

    fonte = 7
    dpi = ax.figure.dpi
    pt = dpi / 72.0  # 1 ponto tipográfico em pixels
    quadro = ax.get_window_extent()
    ocupado: list[tuple[float, float, float, float]] = []

    def _caixa(
        px: float, py: float, dx: float, dy: float, texto: str
    ) -> tuple[float, float, float, float]:
        """Retângulo que o rótulo vai ocupar, em pixels, para testar colisão."""
        linhas = texto.split("\n")
        # Largura por caractere é estimada. Medir de verdade exige renderer e
        # o ganho não paga o acoplamento. Erra para mais, que é o lado seguro.
        w = max(len(s) for s in linhas) * fonte * 0.58 * pt
        h = len(linhas) * fonte * 1.35 * pt
        x = px + dx * pt if dx > 0 else px + dx * pt - w
        y = py + dy * pt if dy > 0 else py + dy * pt - h
        return x, y, x + w, y + h

    # Texto que já está no eixo (os rótulos de quadrante da Fig.5, por exemplo)
    # também é obstáculo: sem isto o nome de um projeto de borda pousa em cima
    # da contagem do quadrante, que é justamente o número que a figura existe
    # para mostrar.
    for texto in ax.texts:
        tx, ty = ax.transData.transform(texto.get_position())
        linhas = texto.get_text().split("\n")
        tf = float(texto.get_fontsize())
        w = max(len(s) for s in linhas) * tf * 0.58 * (dpi / 72.0)
        h = len(linhas) * tf * 1.35 * (dpi / 72.0)
        ha = texto.get_horizontalalignment()
        va = texto.get_verticalalignment()
        x0 = tx - w / 2 if ha == "center" else (tx - w if ha == "right" else tx)
        y0 = ty - h / 2 if va == "center" else (ty - h if va == "top" else ty)
        ocupado.append((x0, y0, x0 + w, y0 + h))

    def _bate(c: tuple[float, float, float, float]) -> bool:
        if c[0] < quadro.x0 or c[2] > quadro.x1 or c[1] < quadro.y0 or c[3] > quadro.y1:
            return True  # rótulo saindo do gráfico
        return any(
            not (c[2] <= o[0] or c[0] >= o[2] or c[3] <= o[1] or c[1] >= o[3]) for o in ocupado
        )

    meio_x = ax.get_xlim()[0] + (ax.get_xlim()[1] - ax.get_xlim()[0]) / 2
    meio_y = ax.get_ylim()[0] + (ax.get_ylim()[1] - ax.get_ylim()[0]) / 2
    # Ordem estável (não a do DataFrame) para que a figura não dependa de qual
    # projeto o parquet devolveu primeiro: o desenho tem de ser reprodutível.
    for _, r in alvo.sort_values([ycol, xcol], ascending=[False, True]).iterrows():
        px, py = ax.transData.transform((r[xcol], r[ycol]))
        # Preferência: para dentro do gráfico (ponto na metade direita recebe
        # rótulo à esquerda, e vice-versa), que é o que basta quando os pontos
        # estão soltos. Se a vaga já estiver tomada (nuvem densa do miolo),
        # tenta as outras direções e vai afastando, senão os nomes se empilham
        # e nenhum deles fica legível.
        sx = 1 if r[xcol] < meio_x else -1
        sy = 1 if r[ycol] < meio_y else -1
        direcoes = [(sx, sy), (sx, -sy), (-sx, sy), (-sx, -sy)]
        escolha = None
        for raio in (1.0, 1.8, 2.8, 4.0, 5.6):
            for ux, uy in direcoes:
                dx, dy = ux * 14 * raio, uy * 12 * raio
                c = _caixa(px, py, dx, dy, rotulo(r))
                if not _bate(c):
                    escolha = (dx, dy, c)
                    break
            if escolha:
                break
        if escolha is None:  # grafo lotado: volta ao padrão simples
            dx, dy = sx * 14, sy * 12
            escolha = (dx, dy, _caixa(px, py, dx, dy, rotulo(r)))
        dx, dy, caixa = escolha
        ocupado.append(caixa)
        ax.annotate(
            rotulo(r),
            (r[xcol], r[ycol]),
            textcoords="offset points",
            xytext=(dx, dy),
            ha="left" if dx > 0 else "right",
            va="bottom" if dy > 0 else "top",
            fontsize=fonte,
            color="#B03A2E",
            zorder=5,
            arrowprops=dict(arrowstyle="-", color="#B03A2E", linewidth=0.6, shrinkA=0, shrinkB=6),
        )


def _anelados(
    cfg: dict,
    disponiveis: pd.Series,
    highlight: list[int] | None,
    figura: str,
    onde: str,
) -> list[int]:
    """Ids a anelar, com o `--highlight` da CLI sobrescrevendo o do checkpoints.

    Anel pedido em projeto fora do plano interrompe a figura. Ou o id está
    errado, ou o projeto não é elegível, e nos dois casos a figura não tem
    onde marcá-lo.
    """
    ids = [int(s) for s in (highlight if highlight is not None else cfg.get("highlight", []))]
    faltando = sorted(set(ids) - set(int(s) for s in disponiveis))
    if faltando:
        raise ValueError(
            f"{figura}: highlight {faltando} não está entre os projetos elegíveis {onde}."
        )
    return ids


def figure_fig2(year: int | None = None, highlight: list[int] | None = None) -> Path:
    """MSR14 Fig.2: stickiness (x) × magnetismo (y), com as medianas como eixos.

    É a figura que *origina* os quadrantes que a ESEM14 Fig.2 depois desenha
    como pirâmides. Não está na lista da seção 6 da spec: fica porque é a única
    vista do critério de classificação em si.

    Ordem dos eixos, ticks e limites vêm da figura publicada: Sticky na
    horizontal, Magnet na vertical. Trocar os eixos não muda quadrante nenhum,
    porque o quadrante sai da comparação com as medianas em `attractiveness`,
    mas espelha a nuvem e atrapalha a comparação visual com o artigo.

    `highlight` (ou `figures.msr14_fig2.highlight`) é só desenho: anela e nomeia
    os project.id pedidos. Não entra em conta nenhuma, e o CSV irmão traz a
    coluna `highlighted` para o anel ser conferível fora da imagem.
    """
    cfg = _fig_cfg("msr14_fig2")
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
        ax,
        df["stickiness"],
        df["magnetism"],
        float(df["median_stickiness"].iloc[0]),
        float(df["median_magnetism"].iloc[0]),
        "stickiness (Sticky)",
        "magnetismo (Magnet)",
    )
    # Régua da figura publicada, declarada em checkpoints. Os limites deixam
    # folga só para o anel caber; ponto que passasse da régua continuaria
    # desenhado.
    ax.set_xlim(*cfg["xlim"])
    ax.set_ylim(*cfg["ylim"])
    ax.set_xticks(cfg["xticks"])
    ax.set_yticks(cfg["yticks"])

    anelados = _anelados(cfg, df["scope_id"], highlight, "Fig.2", f"de {y}")
    _anelar(
        ax,
        df[df["scope_id"].isin(anelados)],
        "stickiness",
        "magnetism",
        lambda r: f"{_repo(r['scope_id'])}\n({r['quadrant']})",
    )

    ax.set_title(f"MSR14 Fig.2: stickiness × magnetismo, {y}  (n={len(df)})", fontsize=9)
    stem = f"msr14_fig2_{y}"
    dados = df[
        ["scope_id", "stickiness", "magnetism", "quadrant", "median_stickiness", "median_magnetism"]
    ].copy()
    dados.insert(1, "project", dados["scope_id"].map(lambda s: lbl.get(int(s), str(s))))
    dados["highlighted"] = dados["scope_id"].isin(anelados)
    _dump(dados.sort_values("scope_id"), stem)
    return _save(fig, stem)


def figure_fig5(snapshot: str | None = None, highlight: list[int] | None = None) -> Path:
    """IEICE16 Fig.5: NCR (x) × CCR (y) no snapshot de classificação, quadrantes A-D.

    A ordem dos eixos é a do artigo, NÃO a do nome da figura: a Fig.5 publicada
    põe NCR na horizontal e CCR na vertical, o que deixa os quadrantes lidos em
    C, A, D, B (da esquerda para a direita, de cima para baixo). Inverter os
    eixos não muda tipo nenhum, porque `metrics._type_of` decide por sinal de
    CCR e NCR e não por posição, mas troca B e C de lado na figura e faz a
    comparação visual com o artigo parecer um erro de classificação.
    """
    t = pd.Timestamp(snapshot or settings()["snapshots"]["classification_snapshot"])
    df = metrics.load_all()
    if df.empty:
        raise ValueError("Fig.5: sem métricas; rode `pyramid metrics` antes.")
    cut = snapshots.require_date_match(df[df["snapshot"] == t], t, "snapshot", "plots.fig5")
    cut = cut[cut["type"].notna()]

    fig, ax = plt.subplots(figsize=(5.0, 4.4))
    # O corte usa ZERO como referência (IEICE16 s3). A mediana não entra aqui:
    # a linha desenhada tem de ser a mesma que o `metrics` usou para atribuir
    # o tipo.
    _scatter(ax, cut["ncr"], cut["ccr"], 0.0, 0.0, "NCR", "CCR")
    # Folga acima/abaixo do domínio real (CCR e NCR vivem em [-1, 1]) para os
    # rótulos de quadrante caberem sem pousar em cima dos pontos de borda.
    ax.set_xlim(-1.08, 1.08)
    ax.set_ylim(-1.30, 1.30)
    # Régua fixa nos extremos e no corte. CCR e NCR vivem em [-1, 1] e é o zero
    # que separa os tipos, então marcar -1, 0 e 1 basta; deixar no autolocator
    # faz a régua mudar de snapshot para snapshot conforme o dado.
    ax.set_xticks([-1, 0, 1])
    ax.set_yticks([-1, 0, 1])

    contagem = cut["type"].value_counts().to_dict()
    # O artigo lado a lado, no próprio gráfico. Esta replicação não fecha o GATE
    # exato da seção 9 (docs/discrepancias.md, seção 1: sobra em A, falta em
    # C), e uma Fig.5 publicada só com os meus números seria lida como
    # reprodução exata.
    alvo = checkpoints()["types"]["counts"]
    # Posição de cada rótulo = quadrante do artigo com NCR em x e CCR em y:
    # C em cima à esquerda, A em cima à direita, D embaixo à esquerda, B
    # embaixo à direita.
    for tipo, (px, py) in {
        "A": (0.54, 1.16),
        "C": (-0.54, 1.16),
        "B": (0.54, -1.16),
        "D": (-0.54, -1.16),
    }.items():
        n = contagem.get(tipo, 0)
        ref = alvo[tipo]
        marca = "" if n == ref else "  ≠"
        ax.text(
            px,
            py,
            f"Tipo {tipo}   n={n}   (artigo: {ref}){marca}",
            fontsize=8,
            ha="center",
            color="#B03A2E",
        )

    # Os oito projetos que o artigo usa como exemplo nas Fig.6 e Fig.7. Anelar
    # aqui é o único jeito de ver, na mesma imagem, que a divergência de
    # contagem não toca em nenhum projeto que o artigo nomeia.
    cfg = _fig_cfg("ieice16_fig5")
    anelados = _anelados(cfg, cut["scope_id"], highlight, "Fig.5", f"em {t.date()}")
    _anelar(
        ax,
        cut[cut["scope_id"].isin(anelados)],
        "ncr",
        "ccr",
        lambda r: f"{_repo(r['scope_id'])}\n({r['type']})",
    )

    ax.set_title(
        f"IEICE16 Fig.5: NCR (x) × CCR (y) em {t.date()}\n"
        f"{len(cut)} projetos classificados (artigo: {checkpoints()['types']['total_classified']})"
        ", ver docs/discrepancias.md, seção 1",
        fontsize=9,
    )
    stem = f"ieice16_fig5_{t.date()}"
    dados = cut[["scope_id", "ncr", "ccr", "type"]].copy()
    dados.insert(1, "project", dados["scope_id"].map(lambda s: labels().get(int(s), str(s))))
    dados["highlighted"] = dados["scope_id"].isin(anelados)
    _dump(dados.sort_values(["type", "scope_id"]), stem)
    return _save(fig, stem)


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


def _cell(  # noqa: PLR0913
    ax: Axes,
    sid: int,
    t: pd.Timestamp,
    *,
    sub: str | None = None,
    xmax: float | None = None,
    ymax: int | None = None,
    xticks: list[float] | None = None,
) -> None:
    """Um painel de grade: pirâmide + nome do projeto + nota de conferência."""
    draw_pyramid(ax, pyramid_frame(snapshots.load(sid), t), xmax=xmax, ymax=ymax, xticks=xticks)
    ax.set_title(_repo(sid), fontsize=9)
    if sub:
        # Vermelho só quando há divergência; o "=" fica cinza para o olho poder
        # varrer a grade atrás do que não bate.
        cor = "#B03A2E" if "≠" in sub else "#555555"
        ax.text(
            0.5, -0.30, sub, transform=ax.transAxes, ha="center", va="top", fontsize=7.5, color=cor
        )


def _confere(obtido: object, esperado: object) -> str:
    """`replicação (artigo: X)` com marca quando os dois discordam."""
    o = "-" if obtido is None or (isinstance(obtido, float) and pd.isna(obtido)) else str(obtido)
    return f"{o}   (artigo: {esperado})" + ("" if o == str(esperado) else "   ≠")


def figure_grid_status() -> Path:
    """ESEM14 Fig.2: as quatro pirâmides com o status de cada projeto."""
    cfg = _fig_cfg("esem14_fig2")
    chave = cfg["from_attractiveness"]
    esperado = {int(k): v for k, v in checkpoints()["attractiveness"][chave].items()}
    t = pd.Timestamp(chave)
    ano = attr.year_of(chave)

    quad = attr.load()
    quad = quad[quad["year"] == ano].set_index("scope_id")

    ids = list(esperado)
    ticks_artigo = {int(k): list(v) for k, v in (cfg.get("x_ticks") or {}).items()}
    # Mesma grade do artigo: 2x2 quando são os quatro painéis, para a leitura
    # ficar posição a posição contra a Fig.2 publicada.
    ncols = 2 if len(ids) == 4 else len(ids)
    nrows = -(-len(ids) // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.4 * ncols, 3.4 * nrows), squeeze=False)
    for j, sid in enumerate(ids):
        # Escala por painel: o artigo põe quatro projetos de portes muito
        # diferentes lado a lado e o que ele compara é a *forma*. O tamanho
        # fica de fora: uma régua comum achataria clojure contra homebrew.
        ax = axes[j // ncols][j % ncols]
        got = quad["quadrant"].get(sid) if sid in quad.index else None
        _cell(ax, sid, t, sub=_confere(got, esperado[sid]), xticks=ticks_artigo.get(sid))
        ax.set_xlabel("contribuidores", fontsize=8)
    for i in range(nrows):
        axes[i][0].set_ylabel("idade acumulada (anos)", fontsize=8)
    for k in range(len(ids), nrows * ncols):
        axes[k // ncols][k % ncols].axis("off")

    _legend(fig)
    fig.suptitle(
        f"ESEM14 Fig.2: pirâmides e status em {t.date()}"
        "   (eixo x: ticks do artigo; barra que passa do último tick é transbordo real)",
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


def figure_grid_types() -> Path:
    """IEICE16 Fig.6: dois exemplos de cada tipo (A, B, C), uma linha por tipo."""
    cfg = _fig_cfg("ieice16_fig6")
    t = pd.Timestamp(cfg["snapshot"])
    rows = {k: [int(s) for s in v] for k, v in cfg["rows"].items()}
    tipos = _tipos_no_snapshot(t)

    ncols = max(len(v) for v in rows.values())
    fig, axes = plt.subplots(
        len(rows), ncols, figsize=(3.2 * ncols, 2.7 * len(rows)), squeeze=False
    )
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
        f"IEICE16 Fig.6: exemplos de cada tipo em {t.date()}"
        "   (escalas independentes, como no original)",
        fontsize=10,
    )
    return _save(fig, f"ieice16_fig6_tipos_{t.date()}", rect=(0, 0.05, 1, 0.95))


def figure_grid_centered() -> Path:
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
        ccr, ncr = (
            float(cut["ccr"].get(sid, float("nan"))),
            float(cut["ncr"].get(sid, float("nan"))),
        )
        _cell(
            ax,
            sid,
            t,
            sub=(
                f"CCR={ccr:+.3f}  NCR={ncr:+.3f}\n"
                f"{_confere(tipos.get(sid), esperado.get(sid, '?'))}"
            ),
        )
        ax.set_xlabel("contribuidores", fontsize=8)
    axes[0][0].set_ylabel("idade acumulada (anos)", fontsize=8)

    _legend(fig)
    fig.suptitle(f"IEICE16 Fig.7: CCR e NCR próximos de zero, {t.date()}", fontsize=10)
    return _save(fig, f"ieice16_fig7_centrados_{t.date()}", rect=(0, 0.12, 1, 0.93))


# ---------------------------------------------------------------------------
# IEICE16 Fig.8: pirâmide medida com a projeção por cima
# ---------------------------------------------------------------------------
def _projection_frame(sub: pd.DataFrame, coluna: str) -> pd.DataFrame:
    piv = (
        sub.pivot_table(index="band", columns="category", values=coluna, aggfunc="sum")
        .reindex(columns=snapshots.CATEGORIES, fill_value=0.0)
        .fillna(0.0)
    )
    piv = piv.reindex(range(0, int(piv.index.max()) + 1), fill_value=0.0)
    return piv.reset_index().rename(columns={"index": "band"})


def figure_projection_overlay() -> Path:
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

    # Mesma grade do artigo: 3 linhas x 2 colunas, painel a painel na mesma
    # posição da Fig.8 publicada.
    ncol = 2
    nlin = -(-len(ids) // ncol)
    fig, axes = plt.subplots(nlin, ncol, figsize=(7.2, 3.1 * nlin), squeeze=False)
    for k, sid in enumerate(ids):
        ax = axes[k // ncol][k % ncol]
        sub = df[df["scope_id"] == sid]
        real = _projection_frame(sub, "actual")
        pred = _projection_frame(sub, "cohort_pred")

        # As barras vêm do `actual` da própria projeção. Um novo `pyramid_frame`
        # não entra aqui: a linha tem de passar sobre a mesma população que o
        # ABIRE mediu, senão a figura contradiz a Tabela 3 sem avisar.
        lim, _ = draw_pyramid(ax, real.astype({"band": int}))
        y = pred["band"].to_numpy()
        esq = -pred["non_coding"].to_numpy()
        dirr = (pred["moved"] + pred["coding"]).to_numpy()
        for serie in (esq, dirr):
            ax.plot(
                serie,
                y,
                color="#B03A2E",
                linewidth=1.2,
                linestyle="--",
                marker="o",
                markersize=2.5,
                zorder=6,
            )

        # Reescala se a projeção estourar a régua das barras: cortar a linha
        # esconderia justamente o erro que a figura existe para mostrar.
        pico = float(max(abs(esq).max(initial=0.0), dirr.max(initial=0.0)))
        if pico > lim:
            ax.set_xlim(-pico * 1.08, pico * 1.08)

        med = sub.loc[sub["category"] == "all", "abre_cohort"].median()
        ax.set_title(_repo(sid), fontsize=9)
        ax.text(
            0.5,
            -0.28,
            f"ABRE(coorte, all) = {med:.3f}",
            transform=ax.transAxes,
            ha="center",
            va="top",
            fontsize=7.5,
            color="#555555",
        )
        if k // ncol == nlin - 1:
            ax.set_xlabel("contribuidores", fontsize=8)
        if k % ncol == 0:
            ax.set_ylabel("idade acumulada (anos)", fontsize=8)
    for k in range(len(ids), nlin * ncol):
        axes[k // ncol][k % ncol].axis("off")

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    handles = [
        Patch(facecolor=FILL[c], hatch=HATCH[c], edgecolor="#4D4D4D", label=PT_LABEL[c])
        for c in ["non_coding", "moved", "coding"]
    ] + [
        Line2D(
            [],
            [],
            color="#B03A2E",
            linestyle="--",
            marker="o",
            markersize=3,
            label="projeção (coorte)",
        )
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=8)
    fig.suptitle(
        f"IEICE16 Fig.8: medido vs. projetado em {alvo.date()} (base {base})",
        fontsize=10,
    )
    return _save(fig, f"ieice16_fig8_projecao_{alvo.date()}", rect=(0, 0.07, 1, 0.95))


# ---------------------------------------------------------------------------
# IEICE16 Tabelas 3 e 4: não são gráfico, mas são resultado obrigatório da
# seção 6
# ---------------------------------------------------------------------------
def figure_abre_table() -> Path:
    """Tabelas 3 e 4 lado a lado com o artigo, em CSV e markdown."""
    tabs = projection.tables()
    ck_abre = checkpoints()["projection_abre"]["table"]
    ck_wil = checkpoints()["projection_wilcoxon"]["table"]
    tol = float(checkpoints()["projection_abre"]["tolerance_rel"])
    ordem = [*snapshots.CATEGORIES, "all"]

    # Mesmo critério de igualdade do `validate`, importado, não recopiado: se
    # esta tabela usasse um "perto" próprio, ela poderia dizer OK numa célula
    # que o veredito oficial reprova, e o leitor não teria como saber qual crer.
    from .validate import _perto

    linhas: list[str] = [
        "# IEICE16 Tabelas 3 e 4: replicação vs. artigo",
        "",
        f"Gerado por `pyramid plot --figure abre-table`. Tolerância relativa: {tol:.0%}.",
        "Cada célula traz `replicação (artigo)`; `≠` marca quem está fora da tolerância.",
        "",
        "## Tabela 3: mediana do ABRE (menor é melhor)",
        "",
        "| tipo | projetos | pares | "
        + " | ".join(f"{c} coorte | {c} baseline" for c in ordem)
        + " |",
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
        "## Tabela 4: Wilcoxon pareado, coorte vs. baseline (95%)",
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
        "`*` = significativo a 95%. Em Tab.4 compara-se a decisão; o p exato fica de fora.",
        "",
        "## Curto vs. longo prazo (corte em 1 ano de atividade)",
        "",
        "| medida | replicação | artigo |",
        "|---|---|---|",
        f"| ABRE mediano, curto prazo | {termo['short_term_abre_median']:.4f} "
        f"(n={termo['short_n']}) | {ck_t['short_term_abre_median']} |",
        f"| ABRE mediano, longo prazo | {termo['long_term_abre_median']:.4f} "
        f"(n={termo['long_n']}) | {ck_t['long_term_abre_median']} |",
        f"| p-valor | {termo['wilcoxon_p']:.4f} | {ck_t['wilcoxon_p']} |",
        "",
        "A inversão de curto/longo prazo está analisada em `docs/discrepancias.md`, seção 12.3.",
        "",
        "## Resumo",
        "",
        f"- Tabela 3: **{dentro_t3}/{celulas_t3}** células dentro de {tol:.0%}.",
        f"- Tabela 4: **{dentro_t4}/{celulas_t4}** decisões de significância iguais às do artigo.",
        "",
        "O veredito formal é do `pyramid validate`. Esta tabela é a vista lado a",
        "lado, e usa o mesmo critério de igualdade (`validate._perto`) para não",
        "poder discordar dele.",
        "",
    ]

    d = out_dir()
    tabs["abre"].to_csv(d / "ieice16_tab3_abre.csv", index=False)
    tabs["wilcoxon"].to_csv(d / "ieice16_tab4_wilcoxon.csv", index=False)
    md = d / "ieice16_tab3_tab4.md"
    md.write_text("\n".join(linhas), encoding="utf-8")
    log.info(
        "tabelas: %s (Tab.3 %d/%d dentro de %.0f%%, Tab.4 %d/%d decisões iguais)",
        md.name,
        dentro_t3,
        celulas_t3,
        tol * 100,
        dentro_t4,
        celulas_t4,
        extra={"stage": STAGE},
    )
    return md


# ---------------------------------------------------------------------------
# MSR14 Tabela 2: a grade de quadrantes. O artigo publica a dele; esta é a
# nossa, no mesmo formato, para o leitor comparar célula a célula.
# ---------------------------------------------------------------------------
def figure_quadrant_table() -> Path:
    """Tabela 2 do MSR'14 na versão da replicação, em markdown."""
    ck = checkpoints()["msr14_tab2"]
    anos = list(ck["years"])
    grade = ck["grid"]
    # Mesmo vocabulário do artigo: ele escreve "Fluctuating" onde o nosso
    # código escreve "floating". Traduzir aqui evita que o leitor ache que
    # são estados diferentes.
    letra = {"A": "Attractive", "F": "Fluctuating", "S": "Stagnant", "T": "Terminal"}
    nosso_para_artigo = {
        "attractive": "Attractive",
        "floating": "Fluctuating",
        "stagnant": "Stagnant",
        "terminal": "Terminal",
    }

    df = attr.table()
    por_nome = {
        str(p): sid
        for sid, p in df[["scope_id", "project"]].drop_duplicates().itertuples(index=False)
    }
    celula: dict[tuple[int, int], str] = {}
    for r in df.itertuples():
        q = r.quadrant
        celula[(int(r.scope_id), int(r.year))] = (
            "*" if not bool(r.eligible) or q is None or pd.isna(q) else str(q)
        )

    # A primeira coluna do artigo agrupa por "Quadrant in 2011", que é a última
    # coluna da grade. Reproduzir o agrupamento mantém as duas tabelas
    # sobreponíveis linha a linha.
    ultimo = {nome: str(linha).split()[-1] for nome, linha in grade.items()}

    linhas: list[str] = [
        "# MSR14 Tabela 2: a grade de quadrantes da replicação",
        "",
        "Gerado por `pyramid plot --figure quadrant-table`.",
        "",
        "Mesmo formato da Tabela 2 do artigo, com os mesmos 12 projetos e os mesmos",
        "anos, para comparar célula a célula. `-` é ano sem atividade no projeto e",
        "`*` é ano ativo com 10 desenvolvedores ou menos, que o artigo deixa fora do",
        "filtro. Onde a replicação discorda do artigo, a célula traz o valor do",
        "artigo entre parênteses.",
        "",
        "| quadrante em 2011 | projeto | " + " | ".join(str(a) for a in anos[:-1]) + " |",
        "|" + "---|" * (2 + len(anos) - 1),
    ]
    # Duas contagens separadas de propósito: as células com quadrante são o
    # critério de aceite, as de estrutura ("-" e "*") só confirmam que estamos
    # olhando o mesmo recorte de projeto e ano.
    batem = total = 0
    batem_e = total_e = 0
    for nome, linha in grade.items():
        sid = por_nome.get(nome)
        esperados = str(linha).split()
        cels = [letra.get(ultimo[nome], ultimo[nome]), f"`{nome}`"]
        for ano, esp in list(zip(anos, esperados, strict=True))[:-1]:
            got = "-" if sid is None else celula.get((int(sid), ano), "-")
            nosso = nosso_para_artigo.get(got, got)
            artigo = letra.get(esp, esp)
            ok = nosso == artigo
            if esp in {"-", "*"}:
                total_e += 1
                batem_e += ok
            else:
                total += 1
                batem += ok
            cels.append(nosso if ok else f"**{nosso}** ({artigo})")
        linhas.append("| " + " | ".join(cels) + " |")

    linhas += [
        "",
        f"Células com quadrante iguais às do artigo: **{batem}/{total}**. Células de",
        f"estrutura (`-` e `*`): **{batem_e}/{total_e}**. As divergentes estão em",
        "negrito, com o valor do artigo ao lado, e cada uma tem causa no",
        "`docs/RESUMO_EXECUTIVO.md`, seção 3.",
        "",
        "O total aqui é menor que os 55 da seção 3 porque a coluna de 2011 virou a",
        "primeira coluna, como no artigo, e não se repete.",
        "",
        "O veredito formal continua sendo o do `pyramid validate`: esta tabela é a",
        "vista lado a lado, não um segundo juiz.",
        "",
    ]
    md = out_dir() / "msr14_tab2_replicacao.md"
    md.write_text("\n".join(linhas), encoding="utf-8")
    log.info(
        "tabela: %s (%d/%d células iguais ao artigo)", md.name, batem, total, extra={"stage": STAGE}
    )
    return md


FIGURES = {
    "pyramid-grid-status": figure_grid_status,
    "pyramid-transition": figure_fig3,
    "type-scatter": figure_fig5,
    "pyramid-grid-types": figure_grid_types,
    "pyramid-grid-centered": figure_grid_centered,
    "pyramid-projection-overlay": figure_projection_overlay,
    "abre-table": figure_abre_table,
    "quadrant-table": figure_quadrant_table,
    "magnet-sticky": figure_fig2,
}

# `pyramid-single` não entra no dict: é a única que exige --project, então não
# tem o que rodar em `--figure all`.
SINGLE = "pyramid-single"


def run(scopes: list[int] | None = None, *, figures: list[str] | None = None, **_: object) -> dict:
    """Assinatura de estágio: o 1º posicional é escopo em todo o pipeline.

    As figuras dos artigos têm projeto fixo. A composição de cada painel vem
    de `config/checkpoints.yaml: figures`, então um `--project` aqui não teria
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
    man: dict[str, Any] = {"stage": STAGE, "ok": {}, "failed": {}}
    for nome in alvos:
        if nome not in FIGURES:
            raise ValueError(f"figura desconhecida: {nome}. Conhecidas: {sorted(FIGURES)}")
        try:
            man["ok"][nome] = str(FIGURES[nome]().name)
        except Exception as e:
            man["failed"][nome] = f"{type(e).__name__}: {e}"
            log.exception("falha na figura %s", nome, extra={"stage": STAGE})
    runlog.save(STAGE, man)
    log.info("figuras: %d ok, %d falhas", len(man["ok"]), len(man["failed"]))
    return man
