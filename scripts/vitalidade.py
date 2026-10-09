#!/usr/bin/env python
"""Métricas de vitalidade de uma linguagem (Plano de Experimento, RQ1).

    uv run python scripts/vitalidade.py --linguagem clojure

Carrega a coleta com `carrega_eventos` de `figuras_linguagem_bruta.py` (mesmos
filtros de elegibilidade, bot e conta apagada) e grava, em
`~/Documents/pyramid-tmp/<linguagem>/vitalidade/`:

  anual.csv / anual.png                   ativos, novatos, saídas, voltas, moved, crescimento
  composicao.csv / piramides_faixa.png    pirâmide por faixa de tempo de casa, anos escolhidos
  indice_envelhecimento.csv / .png        ativos 5+ anos / ativos 0-1 ano
  taxa_saida_faixa.csv / .png             saídas / ativos por (ano, faixa)
  tabua_coortes.csv / tabua_coortes.png   tábua de vida por coorte de entrada
  tabua_todas.csv                         tábua de vida com todas as coortes juntas
  projecao_backtest.csv / .png            cada ano previsto só com os anos anteriores
  projecao_resumo.csv, projecao_wilcoxon.csv   mediana do ABRE, cobertura e Wilcoxon
  projecao_anos_validos.csv               anos com MIN_SAIDAS saídas ou mais, por banda
  projecao_futuro.csv / .png              próximos HORIZONTE anos, um por vez

    uv run python scripts/vitalidade.py --comparativo

Compara LINGUAGENS_RQ2 e grava em `~/Documents/pyramid-tmp/geral/vitalidade/`:

  kaplan_meier.csv / .png, logrank.csv    retenção por linguagem
  padronizacao.csv / .png                 taxa bruta, padronizada e SMR por ano

Definições em `src/pyramid/vitalidade.py`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import MaxNLocator

sys.path.insert(0, str(Path(__file__).resolve().parent))
import figuras_linguagem_bruta as fb
from pyramid import plots, vitalidade

PASTA = "vitalidade"
ANOS_PIRAMIDE = [2010, 2014, 2018, 2022, 2026]
COORTES_TABUA = [2010, 2013, 2016, 2019, 2022]
# CDC WONDER: taxa por idade com menos de 20 óbitos é instável. O plano usa como referência.
MIN_SAIDAS = 20
HORIZONTE = 5
# Python e OCaml entram quando as coletas fecharem; a padronização é refeita com elas.
LINGUAGENS_RQ2 = ["clojure", "elixir", "zig"]
ANO_PESOS = 2025

# Paleta de referência do skill dataviz: categórica em ordem fixa, e rampa azul
# (passos 250 a 700) para o que é ordinal (faixas, coortes).
CATEGORICA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
RAMPA = ["#86b6ef", "#5598e7", "#2a78d6", "#256abf", "#184f95", "#0d366b"]


def _csv(df: pd.DataFrame, nome: str) -> None:
    caminho = fb._caminho_csv(f"{PASTA}/{nome}")
    df.to_csv(caminho, index=False)
    print(f"salvo: {caminho}")


def _rampa(n: int) -> list[str]:
    """`n` passos espalhados pela rampa ordinal, do mais claro ao mais escuro."""
    if n == 1:
        return [RAMPA[-1]]
    passos: list[str] = []
    for i in range(n):
        passos.append(RAMPA[round(i * (len(RAMPA) - 1) / (n - 1))])
    return passos


def figura_anual(t: pd.DataFrame) -> None:
    nome = fb.LING.atual.nome
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    series = [
        ("ativos", "ativos"),
        ("novatos", "novatos"),
        ("saidas", "saídas"),
        ("voltas", "voltas"),
    ]
    for (coluna, rotulo), cor in zip(series, CATEGORICA, strict=False):
        ax1.plot(
            t["ano"], t[coluna], color=cor, linewidth=2, marker="o", markersize=4, label=rotulo
        )
    ax1.set_ylabel("pessoas")
    ax1.set_title(f"{nome}: entradas e saídas por ano (saída = 12 meses sem contribuir)")
    ax1.legend(loc="upper left", frameon=False)

    ax2.axhline(0, color="#888888", linewidth=0.8)
    ax2.plot(
        t["ano"], t["crescimento_natural_pct"], color="black", linewidth=2, marker="o", markersize=4
    )
    ax2.set_ylabel("(novatos - saídas) / ativos, %")
    ax2.set_xlabel("ano")
    ax2.set_title("crescimento natural (anos sem saída decidida ficam de fora)")
    for ax in (ax1, ax2):
        plots._theme(ax)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    fb._salva_fig(fig, f"{PASTA}/anual.png")


def figura_piramides(comp: pd.DataFrame) -> None:
    anos = [a for a in ANOS_PIRAMIDE if a in set(comp["ano"])]
    codigo = {faixa: i for i, faixa in enumerate(vitalidade.FAIXAS)}
    quadros = []
    for ano in anos:
        q = comp[comp["ano"] == ano].copy()
        q["band"] = q["faixa"].map(codigo).astype(int)
        quadros.append(q)
    xmax = 1.0
    for q in quadros:
        xmax = max(xmax, float(q["non_coding"].max()), float((q["moved"] + q["coding"]).max()))

    fig, eixos = plt.subplots(1, len(anos), figsize=(3.4 * len(anos), 3.6), sharey=True)
    for ax, ano, q in zip(eixos, anos, quadros, strict=True):
        plots.draw_pyramid(ax, q, xmax=xmax)
        ax.set_ylim(-0.6, len(vitalidade.FAIXAS) - 0.4)
        ax.set_yticks(range(len(vitalidade.FAIXAS)), minor=False)
        ax.set_yticks([], minor=True)
        ax.set_yticklabels([f"{f} anos" for f in vitalidade.FAIXAS])
        ax.set_title(str(ano))
    fig.suptitle(
        f"{fb.LING.atual.nome}: ativos por tempo de casa (esquerda discussão, direita código)"
    )
    fb._legenda_discussion(fig, plots)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fb._salva_fig(fig, f"{PASTA}/piramides_faixa.png")


def figura_indice(ind: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.plot(ind["ano"], ind["indice"], color=CATEGORICA[0], linewidth=2, marker="o", markersize=4)
    ax.set_ylabel("ativos 5+ anos / ativos 0-1 ano")
    ax.set_xlabel("ano")
    ax.set_title(f"{fb.LING.atual.nome}: índice de envelhecimento")
    plots._theme(ax)
    fb._salva_fig(fig, f"{PASTA}/indice_envelhecimento.png")


def figura_taxa_saida(taxa: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for faixa, cor in zip(vitalidade.FAIXAS, _rampa(len(vitalidade.FAIXAS)), strict=True):
        f = taxa[(taxa["faixa"] == faixa) & taxa["taxa_saida"].notna()]
        if f.empty:
            continue
        ax.plot(f["ano"], f["taxa_saida"], color=cor, linewidth=2, label=f"{faixa} anos")
        estavel = f["saidas"] >= MIN_SAIDAS
        ax.scatter(f.loc[estavel, "ano"], f.loc[estavel, "taxa_saida"], color=cor, s=30, zorder=3)
        ax.scatter(
            f.loc[~estavel, "ano"],
            f.loc[~estavel, "taxa_saida"],
            facecolor="white",
            edgecolor=cor,
            s=30,
            zorder=3,
        )
    ax.set_ylim(0, 1)
    ax.set_ylabel("saídas / ativos da faixa")
    ax.set_xlabel("ano")
    ax.set_title(
        f"{fb.LING.atual.nome}: taxa de saída por faixa "
        f"(ponto vazado = menos de {MIN_SAIDAS} saídas)"
    )
    ax.legend(loc="upper right", frameon=False, ncol=3)
    plots._theme(ax)
    fb._salva_fig(fig, f"{PASTA}/taxa_saida_faixa.png")


def figura_tabua(tabuas: pd.DataFrame) -> None:
    coortes = [c for c in COORTES_TABUA if c in set(tabuas["coorte"])]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for coorte, cor in zip(coortes, _rampa(len(coortes)), strict=True):
        t = tabuas[tabuas["coorte"] == coorte]
        ax.plot(t["x"], t["S"], color=cor, linewidth=2, marker="o", markersize=4, label=str(coorte))
    ax.set_ylim(0, 1)
    ax.set_xlabel("anos desde a primeira contribuição (x)")
    ax.set_ylabel("fração da coorte que chega em x, S(x)")
    ax.set_title(f"{fb.LING.atual.nome}: tábua de vida por coorte de entrada")
    ax.legend(title="coorte", frameon=False)
    plots._theme(ax)
    fb._salva_fig(fig, f"{PASTA}/tabua_coortes.png")


def figura_backtest(bt: pd.DataFrame, teto: bool) -> None:
    t = bt[(bt["faixa"] == "total") & (bt["teto"] == teto)]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.fill_between(
        t["ano"],
        t["pessimista"],
        t["otimista"],
        color=CATEGORICA[0],
        alpha=0.15,
        label="pessimista a otimista",
    )
    ax.plot(t["ano"], t["real"], color="black", linewidth=2, marker="o", markersize=4, label="real")
    for metodo, cor in [
        ("ingenuo", CATEGORICA[1]),
        ("coorte", CATEGORICA[2]),
        ("conservador", CATEGORICA[0]),
    ]:
        ax.plot(t["ano"], t[metodo], color=cor, linewidth=2, label=metodo)
    ax.set_ylabel("ativos no ano")
    ax.set_xlabel("ano previsto")
    rotulo_teto = "com teto em 1" if teto else "sem teto"
    ax.set_title(
        f"{fb.LING.atual.nome}: backtest da projeção, um ano à frente (permanência {rotulo_teto})"
    )
    ax.legend(loc="upper left", frameon=False)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    fb._salva_fig(fig, f"{PASTA}/projecao_backtest.png")


def figura_futuro(anual: pd.DataFrame, futuro: pd.DataFrame, ultimo: int, teto: bool) -> None:
    observado = anual[anual["ano"] <= ultimo]
    total = futuro[futuro["faixa"] == "total"]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(
        observado["ano"],
        observado["ativos"],
        color="black",
        linewidth=2,
        marker="o",
        markersize=4,
        label="observado",
    )
    ponto = observado[observado["ano"] == ultimo]
    linhas = {}
    for metodo in vitalidade.METODOS:
        m = total[total["metodo"] == metodo]
        linhas[metodo] = pd.concat(
            [
                pd.DataFrame({"ano": ponto["ano"], "previsto": ponto["ativos"]}),
                m[["ano", "previsto"]],
            ]
        )
    ax.fill_between(
        linhas["pessimista"]["ano"],
        linhas["pessimista"]["previsto"],
        linhas["otimista"]["previsto"],
        color=CATEGORICA[0],
        alpha=0.15,
        label="pessimista a otimista",
    )
    for metodo, cor in [
        ("ingenuo", CATEGORICA[1]),
        ("coorte", CATEGORICA[2]),
        ("conservador", CATEGORICA[0]),
    ]:
        ax.plot(
            linhas[metodo]["ano"],
            linhas[metodo]["previsto"],
            color=cor,
            linewidth=2,
            linestyle="--",
            label=metodo,
        )
    ax.set_ylabel("ativos no ano")
    ax.set_xlabel("ano")
    rotulo_teto = "com teto em 1" if teto else "sem teto"
    ax.set_title(f"{fb.LING.atual.nome}: projeção a partir de {ultimo} (permanência {rotulo_teto})")
    ax.legend(loc="upper left", frameon=False)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    fb._salva_fig(fig, f"{PASTA}/projecao_futuro.png")


def projecao(pa: pd.DataFrame, anual: pd.DataFrame, fim: pd.Timestamp) -> None:
    # O ano em que a coleta termina está pela metade: fica fora da projeção.
    ultimo = fim.year - 1
    partes = []
    for teto in (False, True):
        partes.append(vitalidade.backtest(pa, fim, ultimo, teto, MIN_SAIDAS))
    bt = pd.concat(partes, ignore_index=True)
    resumo = vitalidade.resumo_backtest(bt)

    # O plano adota a forma (com ou sem teto) de menor erro; a outra é sensibilidade.
    abre = resumo["abre"].set_index("teto")
    teto = bool(abre["coorte"].idxmin())
    print(f"permanência adotada: {'com' if teto else 'sem'} teto em 1", file=sys.stderr)
    futuro = vitalidade.projeta_futuro(pa, fim, ultimo, HORIZONTE, teto, MIN_SAIDAS)

    # O plano escolhe o mínimo de saídas olhando quantos anos válidos sobram por banda.
    validos = vitalidade.saidas_por_banda(pa, fim) >= MIN_SAIDAS
    _csv(
        validos.sum().rename("anos_validos").rename_axis("banda").reset_index(),
        "projecao_anos_validos.csv",
    )
    _csv(bt, "projecao_backtest.csv")
    _csv(resumo["abre"], "projecao_resumo.csv")
    _csv(resumo["wilcoxon"], "projecao_wilcoxon.csv")
    _csv(futuro, "projecao_futuro.csv")
    figura_backtest(bt, teto)
    figura_futuro(anual, futuro, ultimo, teto)


def _csv_geral(df: pd.DataFrame, nome: str) -> None:
    caminho = fb._caminho_geral(f"csv/{PASTA}/{nome}")
    df.to_csv(caminho, index=False)
    print(f"salvo: {caminho}")


def _salva_geral(fig: plt.Figure, nome: str) -> None:
    caminho = fb._caminho_geral(f"{PASTA}/{nome}")
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


def figura_km(curvas: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for slug in LINGUAGENS_RQ2:
        c = curvas[curvas["linguagem"] == slug]
        ax.step(
            c["anos"],
            c["S"],
            where="post",
            color=fb.CORES_LINGUAGEM[slug],
            linewidth=2,
            label=fb.LINGUAGENS[slug].nome,
        )
    ax.set_ylim(0, 1)
    ax.set_xlabel("anos desde a primeira contribuição")
    ax.set_ylabel("fração ainda ativa, S(t)")
    ax.set_title("Kaplan-Meier por linguagem (último evento a 12 meses do fim = censura)")
    ax.legend(frameon=False)
    plots._theme(ax)
    _salva_geral(fig, "kaplan_meier.png")


def figura_padronizacao(pad: pd.DataFrame) -> None:
    fig, eixos = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    paineis = [
        ("taxa_bruta", "taxa de saída bruta"),
        ("taxa_padronizada", f"taxa padronizada (pesos de {ANO_PESOS})"),
        ("smr", "SMR (saídas reais / esperadas)"),
    ]
    for ax, (coluna, rotulo) in zip(eixos, paineis, strict=True):
        for slug in LINGUAGENS_RQ2:
            t = pad[(pad["linguagem"] == slug) & pad[coluna].notna()]
            ax.plot(
                t["ano"],
                t[coluna],
                color=fb.CORES_LINGUAGEM[slug],
                linewidth=2,
                marker="o",
                markersize=4,
                label=fb.LINGUAGENS[slug].nome,
            )
        ax.set_ylabel(rotulo)
        plots._theme(ax)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    eixos[2].axhline(1, color="#888888", linewidth=0.8)
    eixos[0].legend(loc="upper left", frameon=False)
    eixos[0].set_title("Taxa de saída corrigida pela composição por tempo de casa")
    eixos[2].set_xlabel("ano")
    _salva_geral(fig, "padronizacao.png")


def comparativo() -> None:
    duracoes = {}
    taxas = {}
    for slug in LINGUAGENS_RQ2:
        fb.LING.aplica(slug)
        fb.CFG.aplica(fb.RODADA)
        eventos = fb.carrega_eventos(fb.RODADA)
        fim = eventos["timestamp"].max()
        duracoes[slug] = vitalidade.duracoes(eventos, fim)
        taxas[slug] = vitalidade.taxa_saida_por_faixa(vitalidade.pessoa_ano(eventos, fim), fim)

    curvas = []
    for slug, dur in duracoes.items():
        curvas.append(vitalidade.kaplan_meier(dur).assign(linguagem=slug))
    curvas_df = pd.concat(curvas, ignore_index=True)

    testes = []
    for slug in LINGUAGENS_RQ2[1:]:
        estatistica, p = vitalidade.logrank(duracoes["clojure"], duracoes[slug])
        testes.append({"comparacao": f"clojure x {slug}", "estatistica": estatistica, "p": p})

    pad = vitalidade.padronizacao(taxas, ANO_PESOS)

    _csv_geral(curvas_df, "kaplan_meier.csv")
    _csv_geral(pd.DataFrame(testes), "logrank.csv")
    _csv_geral(pad, "padronizacao.csv")
    figura_km(curvas_df)
    figura_padronizacao(pad)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--linguagem", default="clojure", choices=sorted(fb.LINGUAGENS))
    parser.add_argument("--comparativo", action="store_true", help="compara LINGUAGENS_RQ2")
    args = parser.parse_args()
    if args.comparativo:
        comparativo()
        return
    fb.LING.aplica(args.linguagem)
    fb.CFG.aplica(fb.RODADA)

    eventos = fb.carrega_eventos(fb.RODADA)
    fim = eventos["timestamp"].max()
    print(f"{fb.LING.atual.nome}: {len(eventos)} eventos, coleta até {fim.date()}", file=sys.stderr)

    pa = vitalidade.pessoa_ano(eventos, fim)
    anual = vitalidade.tabela_anual(pa, fim)
    comp = vitalidade.composicao(pa)
    indice = vitalidade.indice_envelhecimento(pa)
    taxa = vitalidade.taxa_saida_por_faixa(pa, fim)
    dur = vitalidade.duracoes(eventos, fim)
    tabuas = vitalidade.tabuas_por_coorte(dur)

    _csv(anual, "anual.csv")
    _csv(comp, "composicao.csv")
    _csv(indice, "indice_envelhecimento.csv")
    _csv(taxa, "taxa_saida_faixa.csv")
    _csv(tabuas, "tabua_coortes.csv")
    _csv(vitalidade.tabua_de_vida(dur), "tabua_todas.csv")

    figura_anual(anual)
    figura_piramides(comp)
    figura_indice(indice)
    figura_taxa_saida(taxa)
    figura_tabua(tabuas)
    projecao(pa, anual, fim)


if __name__ == "__main__":
    main()
