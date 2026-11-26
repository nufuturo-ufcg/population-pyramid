"""Ícones dos métodos (Ingênua, Coorte, Conservador) desenhados em vetor no matplotlib.

As formas copiam os SVG de `tcc/slides-nubank/icones/` (viewBox 96 x 96, traço arredondado). O
desenho é nativo, não uma imagem colada, então o PDF continua vetorial e a cor é um parâmetro:
roxo nos eixos dos slides de Clojure, cor da barra nas legendas.

Dois usos:
  icones_no_eixo_y(fig, eixo, metodos)   ícones à esquerda dos nomes do eixo y
  Icone(nome, cor) + HandlerIcone        ícone no lugar do quadradinho da legenda
"""

from matplotlib.legend_handler import HandlerBase
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyBboxPatch, Wedge

ROXO = "#820AD1"

# Formas em coordenadas do SVG (y para baixo). "linhas": (pontos, largura do traço).
ICONES = {
    "ingenua": {
        "circulos": [(18, 48, 7)],
        "retangulos": [],
        "tigelas": [],
        "linhas": [
            ([(32, 48), (80, 48)], 6),
            ([(67, 35), (80, 48), (67, 61)], 6),
        ],
    },
    "coorte": {
        "circulos": [],
        "retangulos": [(10, 68, 60, 10), (18, 53, 44, 10), (26, 38, 28, 10), (34, 23, 12, 10)],
        "tigelas": [],
        "linhas": [
            ([(84, 76), (84, 24)], 6),
            ([(75, 33), (84, 24), (93, 33)], 6),
        ],
    },
    "conservador": {
        "circulos": [(48, 17, 5)],
        "retangulos": [],
        "tigelas": [(16, 56, 10), (80, 56, 10)],
        "linhas": [
            ([(48, 22), (48, 80)], 5),
            ([(30, 80), (66, 80)], 5),
            ([(16, 30), (80, 30)], 5),
            ([(8, 56), (16, 30), (24, 56)], 5),
            ([(72, 56), (80, 30), (88, 56)], 5),
        ],
    },
}
LARGURA_TRACO_TIGELA = 5


def artistas_do_icone(nome, x0, y0, k, pt_por_unidade, cor, transform):
    """Artistas do ícone com canto inferior esquerdo em (x0, y0).

    `k` é o tamanho de uma unidade do SVG nas unidades do `transform` e `pt_por_unidade` é o mesmo
    tamanho em pontos, para a largura do traço.
    """
    forma = ICONES[nome]

    def ponto(x, y):
        return (x0 + x * k, y0 + (96 - y) * k)

    artistas = []
    for cx, cy, r in forma["circulos"]:
        artistas.append(Circle(ponto(cx, cy), r * k, fc=cor, ec="none", transform=transform))
    for x, y, w, h in forma["retangulos"]:
        caixa = FancyBboxPatch(
            ponto(x, y + h),
            w * k,
            h * k,
            boxstyle=f"round,pad=0,rounding_size={3 * k}",
            fc=cor,
            ec="none",
            transform=transform,
        )
        artistas.append(caixa)
    for cx, cy, r in forma["tigelas"]:
        tigela = Wedge(
            ponto(cx, cy),
            r * k,
            180,
            360,
            fc=cor,
            ec=cor,
            lw=LARGURA_TRACO_TIGELA * pt_por_unidade,
            joinstyle="round",
            transform=transform,
        )
        artistas.append(tigela)
    for pontos, largura in forma["linhas"]:
        xs = []
        ys = []
        for x, y in pontos:
            px, py = ponto(x, y)
            xs.append(px)
            ys.append(py)
        linha = Line2D(
            xs,
            ys,
            color=cor,
            lw=largura * pt_por_unidade,
            solid_capstyle="round",
            solid_joinstyle="round",
            transform=transform,
        )
        artistas.append(linha)
    return artistas


class Icone:
    """Entrada de legenda: o ícone `nome` na cor `cor`."""

    def __init__(self, nome, cor):
        self.nome = nome
        self.cor = cor


class HandlerIcone(HandlerBase):
    # assinatura do matplotlib: `legend` e `fontsize` não são usados
    def create_artists(
        self,
        legend,  # noqa: ARG002
        orig_handle,
        xdescent,
        ydescent,
        width,
        height,
        fontsize,  # noqa: ARG002
        trans,
    ):
        # as unidades da caixa da legenda são pontos
        tamanho = height
        k = tamanho / 96.0
        x0 = -xdescent + (width - tamanho) / 2.0
        return artistas_do_icone(orig_handle.nome, x0, -ydescent, k, k, orig_handle.cor, trans)


# Ícones de cada método no eixo y: (ícone, tem R)
ICONES_DO_METODO = {
    "Ingênua": [("ingenua", False)],
    "Coorte": [("coorte", False)],
    "Conservador": [("conservador", False)],
    "Coorte^R": [("coorte", True)],
    "Conservador^R": [("conservador", True)],
    "Ingênua-Coorte^R": [("ingenua", False), ("coorte", True)],
}


def icones_no_eixo_y(fig, eixo, metodos, cor=ROXO, altura_pt=11.0, folga_pt=3.0):
    """Põe os ícones à esquerda do nome de cada método do eixo y, na mesma linha da barra.

    `metodos` na ordem das barras (a barra i está em y = i). Chamar depois de fixar as margens.
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    pol = fig.dpi_scale_trans  # unidades: polegadas
    for posicao, (rotulo, metodo) in enumerate(zip(eixo.get_yticklabels(), metodos, strict=True)):
        icones = ICONES_DO_METODO[metodo]
        tamanho_pt = altura_pt if len(icones) == 1 else altura_pt * 0.82
        tamanho = tamanho_pt / 72.0
        folga = folga_pt / 72.0
        direita = rotulo.get_window_extent(renderer).x0 / fig.dpi - folga
        y_centro = eixo.transData.transform((0, posicao))[1] / fig.dpi
        for nome, tem_r in reversed(icones):
            if tem_r:
                direita -= 0.22 * tamanho  # espaço do R, que avança além da borda direita
            k = tamanho / 96.0
            x0 = direita - tamanho
            y0 = y_centro - tamanho / 2.0
            for artista in artistas_do_icone(nome, x0, y0, k, k * 72.0, cor, pol):
                fig.add_artist(artista)
            if tem_r:
                fig.text(
                    direita - 0.12 * tamanho,
                    y0 + tamanho * 0.98,
                    "R",
                    transform=pol,
                    color=cor,
                    fontsize=altura_pt * 0.55,
                    fontweight="bold",
                    ha="left",
                    va="center",
                )
            direita = x0 - folga * 0.5
