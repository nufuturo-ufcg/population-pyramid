"""Gráficos das métricas de vitalidade e a camada de estilo que os controla.

Cada gráfico é uma função `(contexto, tabelas)` registrada com `@figura(métrica,
nome)`. Ele só desenha: as tabelas já vieram prontas de `scripts/vitalidade.py`,
da memória ou de `resultados/` em disco (`--so-figuras`), sem reler os eventos.

Tudo que muda a aparência vive em `scripts/vitalidade_figuras.yaml`, por gráfico
(`tamanho.anual`) ou para todos (`global`), e pode ser sobreposto numa execução com
`--estilo tamanho.anual:titulo="Outro título"`. As chaves aceitas estão em
`CHAVES_DE_ESTILO` e explicadas no yaml. O que o yaml não cobre (um painel novo, uma
série nova) se muda na função do gráfico, que é curta e isolada.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import yaml
from matplotlib.ticker import MaxNLocator

import carga_fonte
import figuras_linguagem_bruta as fb
from pyramid import plots, vitalidade

PASTA = "vitalidade"
YAML_ESTILO = Path(__file__).parent / "vitalidade_figuras.yaml"

Dados = dict[str, pd.DataFrame]
FIGURAS: dict[str, dict[str, Callable[[Any, Dados], None]]] = {}
FIGURAS_PADRAO: set[tuple[str, str]] = set()


def figura(metrica_nome: str, nome: str, padrao: bool = False) -> Callable[[Callable], Callable]:
    """Registra um gráfico de uma métrica. Recebe o contexto e as tabelas da métrica.

    Escolha na linha de comando com `--figuras metrica.nome`.
    """

    def registra(funcao: Callable) -> Callable:
        FIGURAS.setdefault(metrica_nome, {})[nome] = funcao
        if padrao:
            FIGURAS_PADRAO.add((metrica_nome, nome))
        return funcao

    return registra


# --- Estilo --------------------------------------------------------------------

# Opções de estilo que um gráfico aceita. Chave fora desta lista no yaml dá erro.
CHAVES_DE_ESTILO = {
    "figsize",  # [largura, altura] em polegadas
    "dpi",
    "formato",  # png, svg, pdf
    "titulo",  # título do primeiro painel; {linguagem} vira o nome da linguagem
    "titulo_geral",  # título da figura inteira
    "rotulo_x",  # rótulo do eixo x do primeiro painel
    "rotulo_y",
    "xlim",  # [min, max]
    "ylim",
    "escala_y",  # linear ou log
    "grade",  # false apaga a grade
    "fontes",  # titulo, rotulo, tick, legenda, titulo_geral (pontos); null mantém o desenhado
    "legenda",  # mostrar, posicao ("abaixo" ou loc do matplotlib), colunas, moldura
    "linha",  # largura, marcador_tamanho
    "paleta",  # categorica e rampa: listas de cores
    "cores_linguagem",  # {clojure: "#...", ...}
    "linhas_horizontais",  # [{y, rotulo, cor, estilo, largura, eixo}]
    "linhas_verticais",  # [{x, rotulo, cor, estilo, largura, eixo}]
    "textos",  # [{x, y, texto, tamanho, cor, eixo}]
    "eixos",  # {indice: {titulo, rotulo_x, rotulo_y, xlim, ylim}} para painéis além do primeiro
}


def _nome() -> str:
    """Nome da linguagem atual, com a população se não for a de todos."""
    return fb.LING.atual.nome + ESTADO.sufixo


def _mescla(base: dict, extra: dict) -> dict:
    """`extra` por cima de `base`, entrando nos dicionários em vez de trocá-los."""
    saida = dict(base)
    for chave, valor in extra.items():
        if isinstance(valor, dict) and isinstance(saida.get(chave), dict):
            saida[chave] = _mescla(saida[chave], valor)
        else:
            saida[chave] = valor
    return saida


class _Estado:
    """Estilo carregado e o estilo do gráfico que está sendo desenhado."""

    def __init__(self) -> None:
        self.estilo: dict[str, Any] = {}
        self.atual: dict[str, Any] = {}
        self.sufixo = ""  # " (só quem codou)", no fim do nome da linguagem


ESTADO = _Estado()


def estilo_da(chave: str) -> dict[str, Any]:
    """Estilo efetivo de um gráfico: o `global` com o da figura por cima."""
    todos = ESTADO.estilo
    return _mescla(todos.get("global") or {}, (todos.get("figuras") or {}).get(chave) or {})


def carrega_estilo(sobrepostos: list[str]) -> None:
    """Lê o yaml, aplica cada `figura:chave=valor` de `--estilo` e confere os nomes."""
    estilo = yaml.safe_load(YAML_ESTILO.read_text()) or {}
    estilo.setdefault("global", {})
    estilo.setdefault("figuras", {})
    for item in sobrepostos:
        alvo, igual, texto = item.partition("=")
        chave_figura, doispontos, caminho = alvo.partition(":")
        if not igual or not doispontos:
            raise SystemExit(f"--estilo {item!r}: use figura:chave=valor (ou global:chave=valor).")
        destino = estilo["global"] if chave_figura == "global" else None
        if destino is None:
            destino = estilo["figuras"].setdefault(chave_figura, {})
        partes = caminho.split(".")
        for parte in partes[:-1]:
            destino = destino.setdefault(parte, {})
        destino[partes[-1]] = _valor(texto)
    _confere(estilo)
    ESTADO.estilo = estilo
    ESTADO.atual = estilo_da("global")


def _valor(texto: str) -> Any:
    """Texto da linha de comando como yaml (número, lista, true). Título com `{` fica texto."""
    try:
        return yaml.safe_load(texto)
    except yaml.YAMLError:
        return texto


def _confere(estilo: dict[str, Any]) -> None:
    """Falha alto em figura inexistente ou opção desconhecida: erro de digitação não passa."""
    existentes = {f"{m}.{f}" for m, figuras in FIGURAS.items() for f in figuras}
    for chave, opcoes in estilo["figuras"].items():
        if chave not in existentes:
            raise SystemExit(f"estilo: figura {chave!r} não existe. Veja `--lista`.")
        _confere_opcoes(chave, opcoes)
    _confere_opcoes("global", estilo["global"])


def _confere_opcoes(onde: str, opcoes: dict[str, Any]) -> None:
    desconhecidas = sorted(set(opcoes) - CHAVES_DE_ESTILO)
    if desconhecidas:
        raise SystemExit(f"estilo ({onde}): opção desconhecida {desconhecidas}.")


def categorica() -> list[str]:
    return ESTADO.atual["paleta"]["categorica"]


def rampa(n: int) -> list[str]:
    """`n` passos espalhados pela rampa ordinal, do mais claro ao mais escuro."""
    cores = ESTADO.atual["paleta"]["rampa"]
    if n == 1:
        return [cores[-1]]
    passos: list[str] = []
    for i in range(n):
        passos.append(cores[round(i * (len(cores) - 1) / (n - 1))])
    return passos


def cor_da(slug: str) -> str:
    """Cor da linguagem: a do yaml se houver, senão a do resto do repositório."""
    return (ESTADO.atual.get("cores_linguagem") or {}).get(slug) or carga_fonte.cor_da_linguagem(
        slug
    )


def desenha(chave: str, funcao: Callable, ctx: Any, dados: Dados) -> None:
    """Desenha um gráfico com o estilo dele. `salva` aplica o estilo antes de gravar."""
    ESTADO.atual = estilo_da(chave)
    try:
        funcao(ctx, dados)
    finally:
        ESTADO.atual = estilo_da("global")


def _texto(modelo: str, linguagem: str) -> str:
    return str(modelo).replace("{linguagem}", linguagem)


def _aplica_eixo(ax: Any, opcoes: dict[str, Any], linguagem: str) -> None:
    if opcoes.get("titulo") is not None:
        ax.set_title(_texto(opcoes["titulo"], linguagem))
    if opcoes.get("rotulo_x") is not None:
        ax.set_xlabel(_texto(opcoes["rotulo_x"], linguagem))
    if opcoes.get("rotulo_y") is not None:
        ax.set_ylabel(_texto(opcoes["rotulo_y"], linguagem))
    if opcoes.get("xlim") is not None:
        ax.set_xlim(*opcoes["xlim"])
    if opcoes.get("ylim") is not None:
        ax.set_ylim(*opcoes["ylim"])
    if opcoes.get("escala_y") is not None:
        ax.set_yscale(opcoes["escala_y"])


def _e_referencia(traco: Any) -> bool:
    """Linha de referência (axhline, axvline): dois pontos, horizontal ou vertical."""
    x, y = traco.get_xdata(), traco.get_ydata()
    return len(x) == 2 and (x[0] == x[1] or y[0] == y[1])


def _aplica_fontes(fig: Any, eixos: list, fontes: dict[str, Any]) -> None:
    for ax in eixos:
        if fontes.get("titulo"):
            ax.title.set_fontsize(fontes["titulo"])
        if fontes.get("rotulo"):
            ax.xaxis.label.set_fontsize(fontes["rotulo"])
            ax.yaxis.label.set_fontsize(fontes["rotulo"])
        if fontes.get("tick"):
            ax.tick_params(labelsize=fontes["tick"])
        legenda = ax.get_legend()
        if fontes.get("legenda") and legenda is not None:
            for texto in legenda.get_texts():
                texto.set_fontsize(fontes["legenda"])
    titulo_geral = getattr(fig, "_suptitle", None)  # sem getter público para o objeto
    if fontes.get("titulo_geral") and titulo_geral is not None:
        titulo_geral.set_fontsize(fontes["titulo_geral"])


def _aplica_legenda(eixos: list, opcoes: dict[str, Any]) -> None:
    """Refaz a legenda com os mesmos itens, na posição e colunas pedidas."""
    for ax in eixos:
        legenda = ax.get_legend()
        if legenda is None:
            continue
        if opcoes.get("mostrar") is False:
            legenda.remove()
            continue
        if not any(k in opcoes for k in ("posicao", "colunas", "moldura")):
            continue
        itens = legenda.legend_handles
        rotulos = [t.get_text() for t in legenda.get_texts()]
        posicao = opcoes.get("posicao", "best")
        ancora = None
        if posicao == "abaixo":
            posicao, ancora = "upper center", (0.5, -0.13)
        titulo = legenda.get_title().get_text() or None
        ax.legend(
            itens,
            rotulos,
            loc=posicao,
            bbox_to_anchor=ancora,
            ncol=opcoes.get("colunas", getattr(legenda, "_ncols", 1)),
            frameon=opcoes.get("moldura", False),
            title=titulo,
        )


def _aplica_extras(eixos: list, e: dict[str, Any]) -> None:
    """Linhas de referência e textos pedidos no yaml, em coordenadas dos dados."""
    for item in e.get("linhas_horizontais") or []:
        ax = eixos[item.get("eixo", 0)]
        ax.axhline(
            item["y"],
            color=item.get("cor", "#888888"),
            linestyle=item.get("estilo", "--"),
            linewidth=item.get("largura", 1),
        )
        if item.get("rotulo"):
            ax.text(
                1.0,
                item["y"],
                item["rotulo"],
                transform=ax.get_yaxis_transform(),
                ha="right",
                va="bottom",
            )
    for item in e.get("linhas_verticais") or []:
        ax = eixos[item.get("eixo", 0)]
        ax.axvline(
            item["x"],
            color=item.get("cor", "#888888"),
            linestyle=item.get("estilo", "--"),
            linewidth=item.get("largura", 1),
        )
        if item.get("rotulo"):
            ax.text(
                item["x"],
                1.0,
                item["rotulo"],
                transform=ax.get_xaxis_transform(),
                rotation=90,
                ha="right",
                va="top",
            )
    for item in e.get("textos") or []:
        eixos[item.get("eixo", 0)].text(
            item["x"],
            item["y"],
            item["texto"],
            fontsize=item.get("tamanho"),
            color=item.get("cor"),
        )


def aplica_estilo(fig: Any, e: dict[str, Any]) -> None:
    """Aplica na figura pronta tudo que o estilo `e` pede. Opção ausente não muda nada."""
    eixos = [ax for ax in fig.axes if ax.get_visible() and ax.get_label() != "<colorbar>"]
    linguagem = _nome()
    if e.get("figsize"):
        fig.set_size_inches(*e["figsize"])
    por_painel = e.get("eixos") or {}
    for i, ax in enumerate(eixos):
        opcoes = {
            k: e[k]
            for k in ("titulo", "rotulo_x", "rotulo_y", "xlim", "ylim", "escala_y")
            if k in e
        }
        _aplica_eixo(ax, opcoes if i == 0 else {}, linguagem)
        _aplica_eixo(ax, por_painel.get(i) or {}, linguagem)
        if e.get("grade") is False:
            ax.grid(False)
        linha = e.get("linha") or {}
        for traco in ax.get_lines():
            if _e_referencia(traco):
                continue
            if linha.get("largura") is not None:
                traco.set_linewidth(linha["largura"])
            if linha.get("marcador_tamanho") is not None:
                traco.set_markersize(linha["marcador_tamanho"])
    if e.get("titulo_geral") is not None:
        fig.suptitle(_texto(e["titulo_geral"], linguagem))
    _aplica_fontes(fig, eixos, e.get("fontes") or {})
    _aplica_legenda(eixos, e.get("legenda") or {})
    _aplica_extras(eixos, e)


def salva(fig: Any, nome: str, geral: bool = False) -> None:
    """Aplica o estilo do gráfico atual e grava. `geral` grava na pasta das comparações."""
    e = ESTADO.atual
    aplica_estilo(fig, e)
    formato = e.get("formato") or "png"
    nome = str(Path(nome).with_suffix(f".{formato}"))
    if geral:
        caminho = fb._caminho_geral(f"{PASTA}/{nome}")
    else:
        caminho = fb.CFG.saida / PASTA / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho, dpi=e.get("dpi") or 200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


# --- Gráficos ------------------------------------------------------------------


@figura("tamanho", "anual", padrao=True)
def figura_anual(ctx: Any, d: Dados) -> None:
    """Ativos, novatos, saídas e voltas por ano, e o crescimento natural embaixo."""
    t = d["anual"]
    nome = _nome()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    series = [
        ("ativos", "ativos"),
        ("novatos", "novatos"),
        ("saidas", "saídas"),
        ("voltas", "voltas"),
    ]
    for (coluna, rotulo), cor in zip(series, categorica(), strict=False):
        ax1.plot(
            t["ano"], t[coluna], color=cor, linewidth=2, marker="o", markersize=4, label=rotulo
        )
    ax1.set_ylabel("pessoas")
    ax1.set_title(f"{nome}: entradas e saídas por ano (saída = 12 meses sem contribuir)")
    ax1.legend(loc="upper left", frameon=False)

    ax2.axhline(0, color="#888888", linewidth=0.8)
    ax2.plot(
        t["ano"],
        t["crescimento_natural_pct"],
        color="black",
        linewidth=2,
        marker="o",
        markersize=4,
        label="natural: (novatos - saídas) / ativos",
    )
    if "crescimento_liquido_pct" in t:
        ax2.plot(
            t["ano"],
            t["crescimento_liquido_pct"],
            color=categorica()[0],
            linewidth=2,
            marker="o",
            markersize=4,
            label="líquido: (novatos + voltas - saídas) / ativos",
        )
    ax2.set_ylabel("% dos ativos")
    ax2.set_xlabel("ano")
    ax2.set_title("crescimento (anos sem saída decidida ficam de fora)")
    ax2.legend(loc="lower left", frameon=False)
    for ax in (ax1, ax2):
        plots._theme(ax)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, "anual.png")


def _desenha_piramides(ctx: Any, d: Dados, em_pct: bool) -> None:
    comp = d["composicao"]
    anos = [a for a in ctx.p.anos_piramide if a in set(comp["ano"])]
    codigo = {faixa: i for i, faixa in enumerate(vitalidade.FAIXAS)}
    lados = ["non_coding", "moved", "coding"]
    quadros = []
    for ano in anos:
        q = comp[comp["ano"] == ano].copy()
        q["band"] = q["faixa"].map(codigo).astype(int)
        if em_pct:
            q[lados] = 100 * q[lados] / q[lados].to_numpy().sum()
        quadros.append(q)
    xmax = 1.0
    for q in quadros:
        xmax = max(xmax, float(q["non_coding"].max()), float((q["moved"] + q["coding"]).max()))

    fig, eixos = plt.subplots(1, len(anos), figsize=(3.4 * len(anos), 3.8), sharey=True)
    for ax, ano, q in zip(eixos, anos, quadros, strict=True):
        plots.draw_pyramid(ax, q, xmax=xmax)
        ax.set_ylim(-0.6, len(vitalidade.FAIXAS) - 0.4)
        ax.set_yticks(range(len(vitalidade.FAIXAS)), minor=False)
        ax.set_yticks([], minor=True)
        ax.set_yticklabels([f"{f} anos" for f in vitalidade.FAIXAS])
        ax.set_title(str(ano))
        ax.set_xlabel("% dos ativos do ano" if em_pct else "ativos", fontsize=8)
    unidade = "% dos ativos" if em_pct else "ativos"
    fig.suptitle(f"{_nome()}: {unidade} por tempo de casa (esquerda discussão, direita código)")
    fb._legenda_discussion(fig, plots)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    salva(fig, "piramides_faixa_pct.png" if em_pct else "piramides_faixa.png")


@figura("composicao", "piramides", padrao=True)
def figura_piramides(ctx: Any, d: Dados) -> None:
    """Pirâmides por faixa nos `anos_piramide`, em % dos ativos do ano (`piramide_em_pct`)."""
    _desenha_piramides(ctx, d, ctx.p.piramide_em_pct)


@figura("composicao", "piramides_contagem")
def figura_piramides_contagem(ctx: Any, d: Dados) -> None:
    """As mesmas pirâmides em número de pessoas."""
    _desenha_piramides(ctx, d, False)


@figura("composicao", "indice", padrao=True)
def figura_indice(ctx: Any, d: Dados) -> None:
    """Índice de envelhecimento por ano."""
    ind = d["indice_envelhecimento"]
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.plot(ind["ano"], ind["indice"], color=categorica()[0], linewidth=2, marker="o", markersize=4)
    ax.set_ylabel("ativos 5+ anos / ativos 0-1 ano")
    ax.set_xlabel("ano")
    ax.set_title(f"{_nome()}: índice de envelhecimento")
    plots._theme(ax)
    salva(fig, "indice_envelhecimento.png")


@figura("saida_por_faixa", "linhas", padrao=True)
def figura_taxa_saida(ctx: Any, d: Dados) -> None:
    """Uma linha por faixa; ponto vazado marca célula com poucas saídas."""
    taxa = d["taxa_saida_faixa"]
    saidas_estavel = ctx.p.saidas_estavel
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for faixa, cor in zip(vitalidade.FAIXAS, rampa(len(vitalidade.FAIXAS)), strict=True):
        f = taxa[(taxa["faixa"] == faixa) & taxa["taxa_saida"].notna()]
        if f.empty:
            continue
        ax.plot(f["ano"], f["taxa_saida"], color=cor, linewidth=2, label=f"{faixa} anos")
        estavel = f["saidas"] >= saidas_estavel
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
        f"{_nome()}: taxa de saída por faixa (ponto vazado = menos de {saidas_estavel} saídas)"
    )
    ax.legend(loc="upper right", frameon=False, ncol=3)
    plots._theme(ax)
    salva(fig, "taxa_saida_faixa.png")


@figura("retencao", "sobrevivencia", padrao=True)
def figura_tabua(ctx: Any, d: Dados) -> None:
    """S(x) de cada coorte em `coortes_tabua`."""
    tabuas = d["tabua_coortes"]
    coortes = [c for c in ctx.p.coortes_tabua if c in set(tabuas["coorte"])]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for coorte, cor in zip(coortes, rampa(len(coortes)), strict=True):
        t = tabuas[tabuas["coorte"] == coorte]
        ax.plot(t["x"], t["S"], color=cor, linewidth=2, marker="o", markersize=4, label=str(coorte))
    ax.set_ylim(0, 1)
    ax.set_xlabel("anos desde a primeira contribuição (x)")
    ax.set_ylabel("fração da coorte que chega em x, S(x)")
    ax.set_title(f"{_nome()}: tábua de vida por coorte de entrada")
    ax.legend(title="coorte", frameon=False)
    plots._theme(ax)
    salva(fig, "tabua_coortes.png")


def figura_backtest(bt: pd.DataFrame, teto: bool, pasta: str, rotulo: str) -> None:
    t = bt[(bt["faixa"] == "total") & (bt["teto"] == teto)]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.fill_between(
        t["ano"],
        t["pessimista"],
        t["otimista"],
        color=categorica()[0],
        alpha=0.15,
        label="pessimista a otimista",
    )
    ax.plot(t["ano"], t["real"], color="black", linewidth=2, marker="o", markersize=4, label="real")
    for metodo, cor in [
        ("ingenuo", categorica()[1]),
        ("coorte", categorica()[2]),
        ("conservador", categorica()[0]),
    ]:
        ax.plot(t["ano"], t[metodo], color=cor, linewidth=2, label=metodo)
    ax.set_ylabel("ativos no ano")
    ax.set_xlabel("ano previsto")
    rotulo_teto = "com teto em 1" if teto else "sem teto"
    ax.set_title(
        f"{_nome()}: backtest um ano à frente, permanência {rotulo_teto}\ncenários: {rotulo}"
    )
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3, frameon=False)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, f"{pasta}/projecao_backtest.png")


def figura_futuro(
    anual: pd.DataFrame, futuro: pd.DataFrame, ultimo: int, teto: bool, pasta: str, rotulo: str
) -> None:
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
        color=categorica()[0],
        alpha=0.15,
        label="pessimista a otimista",
    )
    for metodo, cor in [
        ("ingenuo", categorica()[1]),
        ("coorte", categorica()[2]),
        ("conservador", categorica()[0]),
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
    ax.set_title(
        f"{_nome()}: projeção a partir de {ultimo}, permanência {rotulo_teto}\ncenários: {rotulo}"
    )
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3, frameon=False)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, f"{pasta}/projecao_futuro.png")


def _figura_transicao(f: pd.DataFrame, nome: str) -> None:
    """Natalidade e mortalidade com a área entre elas; população ao fundo, eixo da direita."""
    fechado = f[f["obitos"].notna()]
    # Cada ponto e cada barra no meio do seu período.
    meio = f["periodo"].dt.start_time + (f["periodo"].dt.end_time - f["periodo"].dt.start_time) / 2
    x = meio[f["obitos"].notna()]
    nat = fechado["natalidade_pct"]
    mort = fechado["mortalidade_pct"]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    plots._theme(ax)

    # População ao fundo, no segundo eixo (pedido do usuário).
    fundo = ax.twinx()
    largura = 300 if nome == "anual" else 75
    fundo.bar(meio, f["populacao"], width=largura, color="#9a9a9a", alpha=0.35, label="população")
    fundo.set_ylabel("população (barras)")
    fundo.grid(False)
    # Linhas na frente das barras: o fundo pega a cor do tema e o eixo das linhas fica vazado.
    fundo.set_facecolor(ax.get_facecolor())
    ax.set_zorder(fundo.get_zorder() + 1)
    ax.patch.set_visible(False)

    ax.fill_between(
        x,
        nat,
        mort,
        where=nat >= mort,
        interpolate=True,
        color=categorica()[0],
        alpha=0.2,
        label="crescimento natural",
    )
    ax.fill_between(
        x,
        nat,
        mort,
        where=nat < mort,
        interpolate=True,
        color=categorica()[1],
        alpha=0.2,
        label="queda natural",
    )
    # A natalidade já é conhecida até o último período completo; a mortalidade, só onde fechou.
    ax.plot(
        meio,
        f["natalidade_pct"],
        color=categorica()[0],
        linewidth=2,
        label="natalidade (novatos / população)",
    )
    aberto = f[f["obitos"].isna()]
    if not aberto.empty:
        ax.axvspan(
            aberto["periodo"].iloc[0].start_time,
            aberto["periodo"].iloc[-1].end_time,
            facecolor="none",
            edgecolor="#9a9a9a",
            hatch="//",
            linewidth=0,
            label="saídas ainda indecididas (12 meses de espera)",
        )
    ax.plot(x, mort, color=categorica()[1], linewidth=2, label="mortalidade (saídas / população)")
    passo = "ano" if nome == "anual" else "trimestre"
    ax.set_ylabel(f"% da população no {passo} (linhas)")
    ax.set_xlabel("ano")
    ax.set_title(f"{_nome()}: natalidade e mortalidade, passo {nome}")

    linhas, rotulos = ax.get_legend_handles_labels()
    linhas_fundo, rotulos_fundo = fundo.get_legend_handles_labels()
    ax.legend(
        linhas + linhas_fundo,
        rotulos + rotulos_fundo,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.13),
        ncol=3,
        frameon=False,
    )
    salva(fig, f"transicao_{nome}.png")


def figura_variantes(bts: dict[str, pd.DataFrame], teto: bool) -> None:
    """Uma variante de cenário por painel: real, conservador e o intervalo, no mesmo eixo."""
    linhas_painel = (len(bts) + 1) // 2
    fig, eixos = plt.subplots(
        linhas_painel, 2, figsize=(12, 4 * linhas_painel), sharex=True, squeeze=False
    )
    for ax in eixos.flat[len(bts) :]:
        ax.set_visible(False)
    for ax, (rotulo, bt) in zip(eixos.flat, bts.items(), strict=False):
        t = bt[(bt["faixa"] == "total") & (bt["teto"] == teto)].dropna(subset=["conservador"])
        # Barra vertical por ano: continua legível quando o backtest tem um ano só (Zig).
        ax.vlines(
            t["ano"],
            t["pessimista"],
            t["otimista"],
            color=categorica()[0],
            alpha=0.35,
            linewidth=10,
            label="pessimista a otimista",
        )
        ax.plot(
            t["ano"], t["real"], color="black", linewidth=2, marker="o", markersize=5, label="real"
        )
        ax.plot(
            t["ano"],
            t["conservador"],
            color=categorica()[0],
            linewidth=2,
            marker="s",
            markersize=5,
            label="conservador",
        )
        cobertura = t["cobre"].mean()
        anos = "1 ano" if len(t) == 1 else f"{len(t)} anos"
        ax.set_title(f"{rotulo}\ncobertura {cobertura:.0%} em {anos}")
        plots._theme(ax)
        ax.set_xlim(t["ano"].min() - 0.7, t["ano"].max() + 0.7)
        ax.set_xticks(t["ano"].tolist())
    for ax in eixos[:, 0]:
        ax.set_ylabel("ativos no ano")
    linhas, rotulos = eixos[0, 0].get_legend_handles_labels()
    fig.legend(linhas, rotulos, loc="lower center", ncol=3, frameon=False)
    fig.suptitle(f"{_nome()}: backtest dos cenários, uma regra por painel")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    salva(fig, "cenarios_comparados.png")


@figura("significancia", "km", padrao=True)
def figura_km(ctx: Any, d: Dados) -> None:
    """Curva de Kaplan-Meier por linguagem."""
    curvas = d["kaplan_meier"]
    linguagens = ctx.p.linguagens_rq2
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for slug in linguagens:
        c = curvas[curvas["linguagem"] == slug]
        ax.step(
            c["anos"],
            c["S"],
            where="post",
            color=cor_da(slug),
            linewidth=2,
            label=carga_fonte.LINGUAGENS[slug].nome,
        )
    ax.set_ylim(0, 1)
    ax.set_xlabel("anos desde a primeira contribuição")
    ax.set_ylabel("fração ainda ativa, S(t)")
    ax.set_title("Kaplan-Meier por linguagem (último evento a 12 meses do fim = censura)")
    ax.legend(frameon=False)
    plots._theme(ax)
    salva(fig, "kaplan_meier.png", geral=True)


@figura("comparacao_corrigida", "tres_paineis", padrao=True)
def figura_padronizacao(ctx: Any, d: Dados) -> None:
    """Taxa bruta, padronizada e SMR, um painel cada."""
    pad = d["padronizacao"]
    linguagens = ctx.p.linguagens_rq2
    ano_pesos = ctx.p.ano_pesos
    fig, eixos = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    paineis = [
        ("taxa_bruta", "taxa de saída bruta"),
        ("taxa_padronizada", f"taxa padronizada (pesos de {ano_pesos})"),
        ("smr", "SMR (saídas reais / esperadas)"),
    ]
    for ax, (coluna, rotulo) in zip(eixos, paineis, strict=True):
        for slug in linguagens:
            t = pad[(pad["linguagem"] == slug) & pad[coluna].notna()]
            ax.plot(
                t["ano"],
                t[coluna],
                color=cor_da(slug),
                linewidth=2,
                marker="o",
                markersize=4,
                label=carga_fonte.LINGUAGENS[slug].nome,
            )
        ax.set_ylabel(rotulo)
        plots._theme(ax)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    eixos[2].axhline(1, color="#888888", linewidth=0.8)
    eixos[0].legend(loc="upper left", frameon=False)
    eixos[0].set_title("Taxa de saída corrigida pela composição por tempo de casa")
    eixos[2].set_xlabel("ano")
    salva(fig, "padronizacao.png", geral=True)


@figura("tamanho", "transicao_anual", padrao=True)
def figura_transicao_anual(ctx: Any, d: Dados) -> None:
    """Natalidade e mortalidade por ano, população ao fundo."""
    _figura_transicao(d["transicao_anual"], "anual")


@figura("tamanho", "transicao_trimestral", padrao=True)
def figura_transicao_trimestral(ctx: Any, d: Dados) -> None:
    """Natalidade e mortalidade por trimestre, população ao fundo."""
    _figura_transicao(d["transicao_trimestral"], "trimestral")


@figura("tamanho", "fluxo")
def figura_fluxo(ctx: Any, d: Dados) -> None:
    """Barras por ano: novatos e voltas para cima, saídas para baixo."""
    t = d["anual"]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.axhline(0, color="#888888", linewidth=0.8)
    ax.bar(t["ano"], t["novatos"], color=categorica()[1], label="novatos")
    ax.bar(t["ano"], t["voltas"], bottom=t["novatos"], color=categorica()[3], label="voltas")
    ax.bar(t["ano"], -t["saidas"].fillna(0), color=categorica()[2], label="saídas (para baixo)")
    ax.set_ylabel("pessoas")
    ax.set_xlabel("ano")
    ax.set_title(f"{_nome()}: entradas e saídas por ano")
    ax.legend(loc="upper left", frameon=False)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, "fluxo.png")


@figura("composicao", "proporcao")
def figura_proporcao(ctx: Any, d: Dados) -> None:
    """Área empilhada: parcela de cada faixa de tempo de casa nos ativos do ano."""
    c = d["composicao"].copy()
    c["total"] = c["non_coding"] + c["moved"] + c["coding"]
    t = c.groupby(["ano", "faixa"], observed=False)["total"].sum().unstack()[vitalidade.FAIXAS]
    t = t.div(t.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    rotulos = [f"{faixa} anos" for faixa in vitalidade.FAIXAS]
    ax.stackplot(
        t.index,
        [t[faixa] for faixa in vitalidade.FAIXAS],
        colors=rampa(len(vitalidade.FAIXAS)),
        labels=rotulos,
    )
    ax.set_ylim(0, 1)
    ax.set_ylabel("parcela dos ativos")
    ax.set_xlabel("ano")
    ax.set_title(f"{_nome()}: composição por tempo de casa")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=6, frameon=False)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, "composicao_proporcao.png")


@figura("retencao", "esperanca")
def figura_esperanca(ctx: Any, d: Dados) -> None:
    """e(x), o tempo médio que ainda resta, por coorte. Piso: a cauda censurada fica de fora."""
    tabuas = d["tabua_coortes"]
    coortes = [c for c in ctx.p.coortes_tabua if c in set(tabuas["coorte"])]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for coorte, cor in zip(coortes, rampa(len(coortes)), strict=True):
        t = tabuas[tabuas["coorte"] == coorte]
        ax.plot(t["x"], t["e"], color=cor, linewidth=2, label=str(coorte))
    ax.set_xlabel("anos desde a primeira contribuição (x)")
    ax.set_ylabel("anos que ainda restam, e(x)")
    ax.set_title(f"{_nome()}: esperança de permanência por coorte (piso)")
    ax.legend(title="coorte", frameon=False)
    plots._theme(ax)
    salva(fig, "tabua_esperanca.png")


@figura("saida_por_faixa", "calor")
def figura_calor(ctx: Any, d: Dados) -> None:
    """Mapa de calor: faixa nas linhas, ano nas colunas, cor = taxa de saída."""
    taxa = d["taxa_saida_faixa"]
    m = taxa.pivot(index="faixa", columns="ano", values="taxa_saida").reindex(vitalidade.FAIXAS)
    fig, ax = plt.subplots(figsize=(10, 3.8))
    imagem = ax.imshow(m.to_numpy(dtype=float), aspect="auto", cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(m.columns)), [str(a) for a in m.columns], rotation=90)
    ax.set_yticks(range(len(m.index)), [f"{f} anos" for f in m.index])
    fig.colorbar(imagem, ax=ax, label="saídas / ativos da faixa")
    ax.set_title(f"{_nome()}: taxa de saída por faixa e ano")
    salva(fig, "taxa_saida_calor.png")


@figura("cenarios", "backtest", padrao=True)
def figura_cenarios_backtest(ctx: Any, d: Dados) -> None:
    """Real contra projetado um ano à frente, uma figura por regra de `variantes`."""
    for chave, (rotulo, _janela, _por_taxa) in ctx.p.variantes.items():
        pasta = f"cenarios-{chave}"
        figura_backtest(d[f"{pasta}/projecao_backtest"], ctx.p.teto, pasta, rotulo)


@figura("cenarios", "futuro", padrao=True)
def figura_cenarios_futuro(ctx: Any, d: Dados) -> None:
    """Projeção dos próximos `horizonte` anos, uma figura por regra de `variantes`."""
    for chave, (rotulo, _janela, _por_taxa) in ctx.p.variantes.items():
        pasta = f"cenarios-{chave}"
        futuro = d[f"{pasta}/projecao_futuro"]
        futuro = futuro[futuro["teto"] == ctx.p.teto]
        figura_futuro(ctx.anual, futuro, ctx.fim.year - 1, ctx.p.teto, pasta, rotulo)


@figura("cenarios", "comparadas", padrao=True)
def figura_cenarios_comparadas(ctx: Any, d: Dados) -> None:
    """Todas as regras de `variantes` lado a lado, um painel por regra."""
    if len(ctx.p.variantes) < 2:
        return
    bts = {}
    for chave, (rotulo, _janela, _por_taxa) in ctx.p.variantes.items():
        bts[rotulo] = d[f"cenarios-{chave}/projecao_backtest"]
    figura_variantes(bts, ctx.p.teto)


@figura("ccr_ncr", "dispersao", padrao=True)
def figura_ccr_ncr_dispersao(ctx: Any, d: Dados) -> None:
    """CCR x NCR por trimestre, um ponto por trimestre, eixos de -1 a 1."""
    t = d["ccr_ncr"]
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    ax.axhline(0, color="#888888", linewidth=0.7)
    ax.axvline(0, color="#888888", linewidth=0.7)
    ax.scatter(t["ccr"], t["ncr"], color="black", s=22, zorder=3)
    for _, linha in t.iloc[::8].iterrows():  # um rótulo a cada 8 trimestres, 2 em 2 anos
        ano = str(pd.Timestamp(linha["snapshot"]).year)
        ax.annotate(
            ano, (linha["ccr"], linha["ncr"]), fontsize=7, textcoords="offset points", xytext=(5, 5)
        )
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_xlabel("CCR")
    ax.set_ylabel("NCR")
    ax.set_title(f"{_nome()}: CCR x NCR por trimestre")
    salva(fig, "ccr_ncr_dispersao.png")


@figura("ccr_ncr", "serie")
def figura_ccr_ncr_serie(ctx: Any, d: Dados) -> None:
    """CCR e NCR ao longo dos trimestres, duas linhas."""
    t = d["ccr_ncr"]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.axhline(0, color="#888888", linewidth=0.8)
    ax.plot(t["snapshot"], t["ccr"], color=categorica()[0], linewidth=2, label="CCR")
    ax.plot(t["snapshot"], t["ncr"], color=categorica()[1], linewidth=2, label="NCR")
    ax.set_ylim(-1.05, 1.05)
    ax.set_title(f"{_nome()}: CCR e NCR por trimestre")
    ax.legend(loc="lower right", frameon=False)
    plots._theme(ax)
    salva(fig, "ccr_ncr_serie.png")


@figura("stickiness", "barras", padrao=True)
def figura_stickiness_barras(ctx: Any, d: Dados) -> None:
    """Uma barra por ano."""
    t = d["stickiness_ano"].dropna(subset=["stickiness"]).sort_values("year")
    fig, ax = plt.subplots(figsize=(max(7.0, 0.45 * len(t)), 4))
    ax.bar(t["year"].astype(int).astype(str), t["stickiness"], color="black")
    ax.tick_params(axis="x", rotation=90)  # senão o rótulo de ano cola um no outro
    ax.set_ylabel("stickiness")
    ax.set_title(f"{_nome()}: stickiness por ano")
    salva(fig, "stickiness_barras.png")


@figura("stickiness", "linha")
def figura_stickiness_linha(ctx: Any, d: Dados) -> None:
    """Stickiness por ano, em linha."""
    t = d["stickiness_ano"].dropna(subset=["stickiness"])
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.plot(
        t["year"], t["stickiness"], color=categorica()[0], linewidth=2, marker="o", markersize=4
    )
    ax.set_ylim(0, 1)
    ax.set_xlabel("ano")
    ax.set_ylabel("quem volta no ano seguinte / ativos")
    ax.set_title(f"{_nome()}: stickiness por ano")
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, "stickiness_linha.png")


@figura("significancia", "logrank")
def figura_logrank(ctx: Any, d: Dados) -> None:
    """Estatística do log-rank de cada comparação, com o p ao lado da barra."""
    t = d["logrank"]
    fig, ax = plt.subplots(figsize=(7, 1.2 + 0.6 * len(t)))
    ax.barh(t["comparacao"], t["estatistica"], color=categorica()[0])
    for i, (estatistica, p) in enumerate(zip(t["estatistica"], t["p"], strict=True)):
        ax.text(estatistica, i, f"  p = {p:.1e}", va="center")
    ax.set_xlabel("estatística do log-rank")
    ax.set_title("Log-rank contra a linguagem de referência")
    plots._theme(ax)
    salva(fig, "logrank.png", geral=True)


@figura("comparacao_corrigida", "smr")
def figura_smr(ctx: Any, d: Dados) -> None:
    """SMR de cada linguagem por ano, em um painel só."""
    pad = d["padronizacao"]
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.axhline(1, color="#888888", linewidth=0.8)
    for slug in ctx.p.linguagens_rq2:
        t = pad[(pad["linguagem"] == slug) & pad["smr"].notna()]
        cor = cor_da(slug)
        ax.plot(t["ano"], t["smr"], color=cor, linewidth=2, label=carga_fonte.LINGUAGENS[slug].nome)
    ax.set_ylabel("SMR (saídas reais / esperadas)")
    ax.set_xlabel("ano")
    ax.set_title(f"SMR com a referência de {ctx.p.ano_pesos}")
    ax.legend(frameon=False)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, "smr.png", geral=True)


@figura("magnetismo", "linhas", padrao=True)
def figura_magnetismo(ctx: Any, d: Dados) -> None:
    """Magnetismo de cada linguagem por ano."""
    m = d["magnetismo"].dropna(subset=["magnetism"])
    fig, ax = plt.subplots(figsize=(9, 4))
    for slug in ctx.p.linguagens_rq2:
        t = m[m["linguagem"] == slug]
        cor = cor_da(slug)
        ax.plot(
            t["year"],
            t["magnetism"],
            color=cor,
            linewidth=2,
            label=carga_fonte.LINGUAGENS[slug].nome,
        )
    ax.set_ylim(0, 1)
    ax.set_ylabel("novatos da linguagem / novatos de todas")
    ax.set_xlabel("ano")
    ax.set_title("Magnetismo por ano")
    ax.legend(frameon=False)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, "magnetismo.png", geral=True)


@figura("magnetismo", "dispersao")
def figura_magnetismo_dispersao(ctx: Any, d: Dados) -> None:
    """Magnetismo x stickiness, um ponto por (linguagem, ano), como na tipologia do MSR14."""
    m = d["magnetismo"].dropna(subset=["magnetism", "stickiness"])
    fig, ax = plt.subplots(figsize=(6.5, 6))
    for slug in ctx.p.linguagens_rq2:
        t = m[m["linguagem"] == slug]
        cor = cor_da(slug)
        ax.scatter(
            t["magnetism"],
            t["stickiness"],
            color=cor,
            s=28,
            label=carga_fonte.LINGUAGENS[slug].nome,
        )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("magnetismo")
    ax.set_ylabel("stickiness")
    ax.set_title("Magnetismo x stickiness, um ponto por ano")
    ax.legend(frameon=False)
    plots._theme(ax)
    salva(fig, "magnetismo_dispersao.png", geral=True)


# --- Comparação de trajetória entre linguagens -----------------------------------


def _linhas_por_linguagem(ax: Any, t: pd.DataFrame, coluna: str, desde: int) -> None:
    for slug in t["slug"].drop_duplicates():
        f = t[(t["slug"] == slug) & (t["ano"] >= desde) & t[coluna].notna()]
        nome = carga_fonte.LINGUAGENS[slug].nome
        ax.plot(
            f["ano"],
            f[coluna],
            color=cor_da(slug),
            linewidth=2,
            marker="o",
            markersize=4,
            label=nome,
        )
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))


@figura("trajetoria", "indice", padrao=True)
def figura_indice_de_ativos(ctx: Any, d: Dados) -> None:
    """Ativos de cada linguagem, índice 100 em `ano_base_indice`: tira o tamanho da comparação."""
    base = ctx.p.ano_base_indice
    fig, ax = plt.subplots(figsize=(9, 4.5))
    _linhas_por_linguagem(ax, d["trajetoria"], "indice", base)
    ax.axhline(100, color="#888888", linewidth=0.8)
    ax.set_ylabel(f"ativos no ano (índice, {base} = 100)")
    ax.set_xlabel("ano")
    ax.set_title("Evolução do número de ativos, cada linguagem contra o próprio tamanho")
    ax.legend(frameon=False)
    salva(fig, "trajetoria_indice.png", geral=True)


@figura("trajetoria", "crescimento", padrao=True)
def figura_crescimento_liquido(ctx: Any, d: Dados) -> None:
    """Crescimento líquido por ano, (novatos + voltas - saídas) / ativos, em %."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    _linhas_por_linguagem(ax, d["trajetoria"], "crescimento_liquido_pct", ctx.p.ano_base_indice)
    ax.axhline(0, color="#888888", linewidth=0.8)
    ax.set_ylabel("crescimento líquido, % dos ativos")
    ax.set_xlabel("ano")
    ax.set_title("Crescimento líquido da comunidade (positivo: entra mais gente do que sai)")
    ax.legend(frameon=False)
    salva(fig, "trajetoria_crescimento.png", geral=True)


@figura("trajetoria", "taxas")
def figura_taxas_de_saida_e_volta(ctx: Any, d: Dados) -> None:
    """Saídas e voltas de cada ano, em % dos ativos, em dois painéis."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    _linhas_por_linguagem(ax1, d["trajetoria"], "saida_pct", ctx.p.ano_base_indice)
    _linhas_por_linguagem(ax2, d["trajetoria"], "volta_pct", ctx.p.ano_base_indice)
    ax1.set_ylabel("saídas, % dos ativos")
    ax2.set_ylabel("voltas, % dos ativos")
    ax2.set_xlabel("ano")
    ax1.set_title("Quem saiu no ano e quem voltou depois de 12 meses")
    ax1.legend(frameon=False, ncol=5)
    salva(fig, "trajetoria_taxas.png", geral=True)


@figura("trajetoria", "piramides", padrao=True)
def figura_piramides_entre_linguagens(ctx: Any, d: Dados) -> None:
    """Uma pirâmide por linguagem em `ano_comparacao`, em % dos ativos, na mesma escala."""
    ano = ctx.p.ano_comparacao
    comp = d["composicao_pct"]
    comp = comp[comp["ano"] == ano]
    codigo = {faixa: i for i, faixa in enumerate(vitalidade.FAIXAS)}
    slugs = [s for s in ctx.p.linguagens_rq2 if s in set(comp["slug"])]
    quadros = []
    for slug in slugs:
        q = comp[comp["slug"] == slug].copy()
        q["band"] = q["faixa"].map(codigo).astype(int)
        quadros.append(q)
    xmax = 1.0
    for q in quadros:
        xmax = max(xmax, float(q["non_coding"].max()), float((q["moved"] + q["coding"]).max()))
    fig, eixos = plt.subplots(1, len(slugs), figsize=(3.4 * len(slugs), 3.8), sharey=True)
    for ax, slug, q in zip(eixos, slugs, quadros, strict=True):
        plots.draw_pyramid(ax, q, xmax=xmax)
        ax.set_ylim(-0.6, len(vitalidade.FAIXAS) - 0.4)
        ax.set_yticks(range(len(vitalidade.FAIXAS)), minor=False)
        ax.set_yticks([], minor=True)
        ax.set_yticklabels([f"{f} anos" for f in vitalidade.FAIXAS])
        ax.set_title(carga_fonte.LINGUAGENS[slug].nome)
        ax.set_xlabel("% dos ativos do ano", fontsize=8)
    fig.suptitle(f"Composição por tempo de casa em {ano} (esquerda discussão, direita código)")
    fb._legenda_discussion(fig, plots)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    salva(fig, "trajetoria_piramides.png", geral=True)


carrega_estilo([])  # estilo padrão do yaml; `main` recarrega com os `--estilo`
