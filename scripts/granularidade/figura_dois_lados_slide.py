"""Figura de slide: composição por tempo de casa em 2024, dois lados (discussion e coding).

Lê `composicao_pct.csv` da rodada v3b (definição única). Nele cada pessoa já está em um lado só,
pela regra de `pyramid.vitalidade.lado_no_ano`: discussion se mais da metade dos eventos dela no
ano forem de discussão, coding nos demais casos (empate vai para coding). Não existe grupo
"moved" nesse arquivo. A idade é a da pirâmide (anos de pausa não contam).

Uso: .venv/bin/python scripts/granularidade/figura_dois_lados_slide.py <composicao_pct.csv> <saida>
Grava PDF vetorial, PNG a 600 dpi, `tabela_2024.csv` e `tabela_2024.md` na pasta de saída.
"""

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

FAIXAS = ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"]
ROTULOS = ["0-1 anos", "1-2 anos", "2-3 anos", "3-5 anos", "5-8 anos", "8+ anos"]
LINGUAS = ["clojure", "elixir", "zig", "ocaml", "python"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "ocaml": "OCaml",
    "python": "Python",
}

FUNDO = "#ebebeb"
CONTORNO = "#4d4d4d"
CODING = "#4d4d4d"
LARGURA, ALTURA = 11.0, 2.5  # mesma proporção da imagem de referência (3376 x 773)
# Versão para a caixa de 1260 x 244 px do slide (proporção 5,16:1): figura criada já em 12,6 x 2,44
# pol (100 dpi dá 1260 x 244 px, 400 dpi dá 5040 x 976 px), sem redimensionar a imagem pronta.
CAIXA = {
    "largura": 12.6,
    "altura": 2.44,
    "fonte_titulo": 10,
    "fonte": 8.5,
    "margens": {"left": 0.068, "right": 0.997, "top": 0.9, "bottom": 0.235, "wspace": 0.07},
    "pad_titulo": 2,
    "pad_rotulo": 1,
    "traco": 0.6,
}


def desenha(
    paineis, limite, largura, altura, fonte_titulo, fonte, margens, pad_titulo, pad_rotulo, traco
):
    """Desenha um painel por item de `paineis`, uma lista de (título, tabela por faixa).

    A tabela tem as colunas `discussion_pct` e `coding_pct`, indexada pela faixa. Fontes em pt,
    margens em fração da figura. O eixo é o mesmo em todos os painéis, de -limite a +limite.
    """
    estilo = {
        "font.family": "sans-serif",
        "font.size": fonte,
        "axes.titlesize": fonte_titulo,
        "axes.labelsize": fonte,
        "xtick.labelsize": fonte,
        "ytick.labelsize": fonte,
        "legend.fontsize": fonte,
        "hatch.linewidth": traco,
        "pdf.fonttype": 42,
    }
    with plt.rc_context(estilo):
        fig, eixos = plt.subplots(
            1, len(paineis), figsize=(largura, altura), sharey=True, sharex=True
        )
        posicao = np.arange(len(FAIXAS))
        ticks = [-30, -20, -10, 0, 10, 20, 30]
        for eixo, (titulo, da_faixa) in zip(eixos, paineis, strict=True):
            parte = da_faixa.reindex(FAIXAS)
            eixo.set_facecolor(FUNDO)
            eixo.set_axisbelow(True)
            eixo.grid(axis="x", color="white", linewidth=1.0)
            eixo.grid(axis="y", visible=False)
            for lado in eixo.spines.values():
                lado.set_visible(False)
            eixo.tick_params(length=0, pad=2)
            eixo.barh(
                posicao,
                -parte["discussion_pct"].to_numpy(),
                height=0.85,
                facecolor="white",
                edgecolor=CONTORNO,
                hatch="///",
                linewidth=traco,
            )
            eixo.barh(
                posicao,
                parte["coding_pct"].to_numpy(),
                height=0.85,
                facecolor=CODING,
                edgecolor=CONTORNO,
                linewidth=traco,
            )
            eixo.set_xlim(-limite, limite)
            eixo.set_xticks(ticks)
            eixo.xaxis.set_major_formatter(lambda x, _: f"{abs(x):.0f}")
            eixo.set_title(titulo, pad=pad_titulo)
            eixo.set_xlabel("% dos ativos do ano", labelpad=pad_rotulo)
        eixos[0].set_yticks(posicao, ROTULOS)  # rótulos das faixas só no primeiro painel

        legenda = [
            Patch(
                facecolor="white",
                edgecolor=CONTORNO,
                hatch="///",
                linewidth=traco,
                label="discussion",
            ),
            Patch(facecolor=CODING, edgecolor=CONTORNO, linewidth=traco, label="coding"),
        ]
        fig.legend(
            handles=legenda,
            loc="lower center",
            ncol=2,
            frameon=False,
            bbox_to_anchor=(0.5, 0.0),
            handlelength=1.6,
            borderaxespad=0.2,
        )
        fig.subplots_adjust(**margens)
    return fig


def principal(composicao: Path, saida: Path) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    c = pd.read_csv(composicao)
    c = c[(c["ano"] == 2024) & c["faixa"].isin(FAIXAS) & c["slug"].isin(LINGUAS)]

    # Tabela de conferência: % dos ativos do ano de cada linguagem, por faixa
    linhas = []
    for lingua in LINGUAS:
        soma = 0.0
        for faixa in FAIXAS:
            linha = c[(c["slug"] == lingua) & (c["faixa"] == faixa)]
            assert len(linha) == 1, (lingua, faixa)
            discussao = float(linha["non_coding"].iloc[0])
            codigo = float(linha["coding"].iloc[0])
            soma += discussao + codigo
            linhas.append(
                {
                    "linguagem": NOMES[lingua],
                    "faixa": faixa,
                    "discussion_pct": discussao,
                    "coding_pct": codigo,
                }
            )
        assert abs(soma - 100.0) < 1e-6, (lingua, soma)  # cada linguagem soma 100% dos ativos
    tabela = pd.DataFrame(linhas)
    tabela.to_csv(saida / "tabela_2024.csv", index=False)

    md = ["| Linguagem | Faixa | Discussion (%) | Coding (%) |", "|---|---|---:|---:|"]
    for _, linha in tabela.iterrows():
        d = f"{linha['discussion_pct']:.1f}".replace(".", ",")
        k = f"{linha['coding_pct']:.1f}".replace(".", ",")
        md.append(f"| {linha['linguagem']} | {linha['faixa']} | {d} | {k} |")
    (saida / "tabela_2024.md").write_text("\n".join(md) + "\n")

    # Limite do eixo: 33 como na imagem; sobe por igual nos cinco painéis se alguma barra passar de 30
    maximo = float(tabela[["discussion_pct", "coding_pct"]].max().max())
    limite = 33.0
    if maximo > 30.0:
        limite = math.ceil(maximo) + 3.0

    paineis = []
    for lingua in LINGUAS:
        parte = tabela[tabela["linguagem"] == NOMES[lingua]].set_index("faixa")
        paineis.append((NOMES[lingua], parte))

    # Versão larga de referência (11 x 2,5 pol, PNG a 600 dpi)
    margens = {"left": 0.07, "right": 0.995, "top": 0.88, "bottom": 0.27, "wspace": 0.08}
    fig = desenha(paineis, limite, LARGURA, ALTURA, 12, 9, margens, 6, 4, 0.8)
    fig.savefig(saida / "composicao_dois_lados_2024.pdf")
    fig.savefig(saida / "composicao_dois_lados_2024.png", dpi=600)
    plt.close(fig)

    fig = desenha(paineis, limite, **CAIXA)
    fig.savefig(saida / "composicao_dois_lados_2024_caixa.pdf")
    fig.savefig(saida / "composicao_dois_lados_2024_caixa_1260x244.png", dpi=100)
    fig.savefig(saida / "composicao_dois_lados_2024_caixa_5040x976.png", dpi=400)
    plt.close(fig)
    print("limite do eixo:", limite, "maior barra:", round(maximo, 2))


if __name__ == "__main__":
    principal(Path(sys.argv[1]), Path(sys.argv[2]))
