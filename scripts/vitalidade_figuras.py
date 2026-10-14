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

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from matplotlib.ticker import FuncFormatter, MaxNLocator, NullFormatter

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


def _ate_o_ano_decidido(ctx: Any) -> int:
    """Último ano completo antes do fim do acompanhamento: o último com saída (provisória)."""
    return int(ctx.fim_acompanhamento.year - 1)


def _ultimo_ano_de_contagem(ctx: Any) -> int:
    """Último ano inteiro com ativos e novatos: o do fim do estudo, se ele cai em 31/12."""
    fim = ctx.fim
    return int(fim.year if fim >= pd.Timestamp(year=fim.year, month=12, day=31) else fim.year - 1)


def _primeiro_provisorio(ctx: Any) -> int:
    """Primeiro ano com saída provisória: a que tem menos de `carencia_anos` anos de coleta depois.

    Um ano é firme quando `fim_acompanhamento.year - ano >= carencia_anos`. Com o acompanhamento
    indo até 2026 e carência 2, 2025 sai tracejado e 2024 e antes saem firmes.
    """
    return int(ctx.fim_acompanhamento.year - ctx.p.carencia_anos + 1)


def _plota_datas(
    ax: Any, x: Any, y: Any, anos: Any, primeiro_provisorio: int, **estilo: Any
) -> None:
    """Como `_plota`, com o eixo em datas e a decisão de provisório pelo ano de cada ponto."""
    x = pd.Series(list(x))
    y = pd.Series(list(y))
    anos = pd.Series(list(anos))
    firme = (anos < primeiro_provisorio).to_numpy()
    cauda = (anos >= primeiro_provisorio).to_numpy().copy()
    if firme.any() and cauda.any():
        ultimo_firme = np.flatnonzero(firme).max()
        cauda[ultimo_firme] = True  # a ponte entre o traço cheio e o tracejado
    rotulo = estilo.pop("label", None)
    if firme.any():
        ax.plot(x[firme], y[firme], label=rotulo, **estilo)
        rotulo = None
    if cauda.any() and (anos[cauda] >= primeiro_provisorio).any():
        ax.plot(x[cauda], y[cauda], linestyle="--", label=rotulo, **estilo)


def _plota(ax: Any, x: Any, y: Any, primeiro_provisorio: int, **estilo: Any) -> None:
    """Traço cheio até o último ano firme e tracejado dali em diante, na mesma cor."""
    x = pd.Series(list(x))
    y = pd.Series(list(y))
    firme = (x < primeiro_provisorio).to_numpy()
    cauda = (x >= primeiro_provisorio - 1).to_numpy()
    rotulo = estilo.pop("label", None)
    if firme.any():
        ax.plot(x[firme], y[firme], label=rotulo, **estilo)
        rotulo = None
    if (x[cauda] >= primeiro_provisorio).any():
        ax.plot(x[cauda], y[cauda], linestyle="--", label=rotulo, **estilo)


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
        self.sufixo = ""  # texto no fim do nome da linguagem; a população não usa mais


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


def salva(fig: Any, nome: str, geral: bool = False, ajusta: bool = True) -> None:
    """Aplica o estilo do gráfico atual e grava. `geral` grava na pasta das comparações.

    `ajusta=False` mantém o tamanho e as margens que a figura já tem, para dois gráficos da
    mesma sequência de slides ficarem com o eixo no mesmo lugar.
    """
    e = ESTADO.atual
    aplica_estilo(fig, e)
    formato = e.get("formato") or "png"
    nome = str(Path(nome).with_suffix(f".{formato}"))
    if geral:
        caminho = fb._caminho_geral(f"{PASTA}/{nome}")
    else:
        caminho = fb.CFG.saida / PASTA / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho, dpi=e.get("dpi") or 200, bbox_inches="tight" if ajusta else None)
    plt.close(fig)
    print(f"salvo: {caminho}")


# --- Gráficos ------------------------------------------------------------------


@figura("tamanho", "anual", padrao=True)
def figura_anual(ctx: Any, d: Dados) -> None:
    """Ativos, novatos, saídas e voltas por ano, até o último ano."""
    t = d["anual"]
    decidido = t[t["ano"] <= _ate_o_ano_decidido(ctx)]
    t = t[t["ano"] <= _ultimo_ano_de_contagem(ctx)]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    series = [
        ("ativos", "ativos"),
        ("novatos", "novatos"),
        ("saidas", "saídas"),
        ("voltas", "voltas"),
    ]
    prov = _primeiro_provisorio(ctx)
    for (coluna, rotulo), cor in zip(series, categorica(), strict=False):
        base = decidido if coluna == "saidas" else t
        _plota(
            ax,
            base["ano"],
            base[coluna],
            prov if coluna == "saidas" else 10_000,
            color=cor,
            linewidth=2,
            marker="o",
            markersize=4,
            label=rotulo,
        )
    ax.set_ylabel("pessoas")
    ax.set_xlabel("ano")
    ax.set_title(f"{_nome()}: ativos, novatos, saídas e voltas por ano")
    ax.legend(loc="upper left", frameon=False)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, "anual.png")


@figura("tamanho", "crescimento", padrao=True)
def figura_crescimento_anual(ctx: Any, d: Dados) -> None:
    """Crescimento natural do ano: tudo que entra menos tudo que sai, em % dos ativos do ano."""
    t = d["anual"]
    decidido = t[t["ano"] <= _ate_o_ano_decidido(ctx)]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.axhline(0, color="#888888", linewidth=0.8)
    _plota(
        ax,
        decidido["ano"],
        decidido["crescimento_natural_pct"],
        _primeiro_provisorio(ctx),
        color="black",
        linewidth=2,
        marker="o",
        markersize=4,
    )
    ax.set_ylabel(f"% da {TERMO_POPULACAO}")
    ax.set_xlabel("ano")
    ax.set_title(f"{_nome()}: crescimento natural, todo mundo que entrou menos todo mundo que saiu")
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, "crescimento.png")


# Como os gráficos chamam o conjunto de pessoas que contribuíram no ano.
TERMO_POPULACAO = "população do ano"


def _figura_natalidade(ctx: Any, d: Dados, com_populacao: bool) -> None:
    """Natalidade e mortalidade com a área entre elas; com `com_populacao`, as barras da população.

    Natalidade = todo mundo que entrou (novatos e voltas) / população do ano. Mortalidade = todo
    mundo que saiu (saídas e pausas) / população do ano. A área entre as duas é o crescimento
    natural. Os dois gráficos têm o mesmo tamanho, as mesmas margens e o mesmo eixo dos anos,
    para o segundo ser o primeiro com as barras a mais.
    """
    from matplotlib.patches import Patch

    t = d["anual"]
    t = t[(t["ano"] <= _ate_o_ano_decidido(ctx)) & (t["ativos"] >= MIN_PESSOAS)]
    t = t[t["mortalidade_pct"].notna()]
    fig = plt.figure(figsize=(10, 5.5))
    ax = fig.add_axes((0.08, 0.22, 0.80, 0.68))
    plots._theme(ax)
    if com_populacao:
        fundo = ax.twinx()
        fundo.bar(
            t["ano"], t["ativos"], width=0.8, color="#9a9a9a", alpha=0.35, label=TERMO_POPULACAO
        )
        fundo.set_ylabel(f"pessoas na {TERMO_POPULACAO}")
        fundo.grid(False)
        for borda in fundo.spines.values():
            borda.set_visible(False)  # sem moldura: o eixo da esquerda fica como no outro gráfico
        fundo.set_facecolor(ax.get_facecolor())
        ax.set_zorder(fundo.get_zorder() + 1)
        ax.patch.set_visible(False)
    ax.fill_between(
        t["ano"],
        t["natalidade_pct"],
        t["mortalidade_pct"],
        where=t["natalidade_pct"] >= t["mortalidade_pct"],
        interpolate=True,
        color=categorica()[0],
        alpha=0.2,
        label="crescimento natural",
    )
    ax.fill_between(
        t["ano"],
        t["natalidade_pct"],
        t["mortalidade_pct"],
        where=t["natalidade_pct"] < t["mortalidade_pct"],
        interpolate=True,
        color=categorica()[1],
        alpha=0.2,
        label="queda natural",
    )
    primeiro = _primeiro_provisorio(ctx)
    _plota(
        ax,
        t["ano"],
        t["natalidade_pct"],
        primeiro,
        color=categorica()[0],
        linewidth=2,
        label=f"natalidade: todo mundo que entrou / {TERMO_POPULACAO}",
    )
    _plota(
        ax,
        t["ano"],
        t["mortalidade_pct"],
        primeiro,
        color=categorica()[1],
        linewidth=2,
        label=f"mortalidade: todo mundo que saiu / {TERMO_POPULACAO}",
    )
    ax.set_xlim(t["ano"].min() - 0.6, t["ano"].max() + 0.6)
    ax.set_ylim(bottom=0)
    ax.set_ylabel(f"% da {TERMO_POPULACAO}")
    ax.set_xlabel("ano")
    ax.set_title(f"{_nome()}: natalidade, mortalidade e crescimento natural por ano")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    linhas, rotulos = ax.get_legend_handles_labels()
    if com_populacao:
        extra, rotulos_extra = fundo.get_legend_handles_labels()
    else:
        # A entrada da população existe e fica invisível: a legenda tem o mesmo tamanho e a mesma
        # posição nos dois gráficos.
        extra, rotulos_extra = [Patch(alpha=0)], [TERMO_POPULACAO]
    legenda = fig.legend(
        linhas + extra,
        rotulos + rotulos_extra,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.0),
        ncol=3,
        frameon=False,
        fontsize=10,
    )
    if not com_populacao:
        legenda.get_texts()[-1].set_alpha(0)
    arquivo = (
        "natalidade_mortalidade_com_populacao.png"
        if com_populacao
        else "natalidade_mortalidade.png"
    )
    salva(fig, arquivo, ajusta=False)


@figura("tamanho", "natalidade_mortalidade", padrao=True)
def figura_natalidade_mortalidade(ctx: Any, d: Dados) -> None:
    """Natalidade, mortalidade e a área entre elas, sem as barras da população."""
    _figura_natalidade(ctx, d, com_populacao=False)


@figura("tamanho", "natalidade_mortalidade_com_populacao", padrao=True)
def figura_natalidade_mortalidade_com_populacao(ctx: Any, d: Dados) -> None:
    """O mesmo gráfico com a população de cada ano em barras ao fundo."""
    _figura_natalidade(ctx, d, com_populacao=True)


# O que cada `piramide_lado` deixa à vista (categorias de `vitalidade.LADOS`).
LADOS_VISTOS = {
    "todos": ["non_coding", "moved_to_discussion", "moved", "coding"],
    "moved_para_discussao": ["moved_to_discussion"],
    "moved_para_codigo": ["moved"],
    "codigo": ["moved", "coding"],
    "discussao": ["non_coding", "moved_to_discussion"],
}
ROTULO_LADO = {
    "non_coding": "discussion",
    "moved_to_discussion": "moved to discussion",
    "moved": "moved to coding",
    "coding": "coding",
}


def _em_pct(q: pd.DataFrame) -> pd.DataFrame:
    """Cada categoria em % do total das quatro: a base são os ativos do ano todo."""
    q = q.copy()
    q[vitalidade.LADOS] = 100 * q[vitalidade.LADOS] / q[vitalidade.LADOS].to_numpy().sum()
    return q


def _so_o_lado(q: pd.DataFrame, lado: str) -> pd.DataFrame:
    """Zera as categorias que `lado` não mostra, sem mudar a base da porcentagem."""
    if lado not in LADOS_VISTOS:
        raise SystemExit(f"piramide_lado {lado!r}: use {list(LADOS_VISTOS)}.")
    q = q.copy()
    for categoria in vitalidade.LADOS:
        if categoria not in LADOS_VISTOS[lado]:
            q[categoria] = 0
    return q


def _xmax_das_piramides(quadros: list[pd.DataFrame], minimo: float = 1.0) -> float:
    """A maior barra de cada lado entre os painéis: escala comum para comparar."""
    xmax = minimo
    for q in quadros:
        esquerda = q["non_coding"] + q["moved_to_discussion"]
        direita = q["moved"] + q["coding"]
        xmax = max(xmax, float(esquerda.max()), float(direita.max()))
    return xmax


def _legenda_piramide(fig: Any, lado: str, com_moved_to_discussion: bool) -> None:
    """Legenda das categorias que o `lado` mostra, sem moved to discussion se ela não existe."""
    from matplotlib.patches import Patch

    handles = []
    for categoria in vitalidade.LADOS:
        if categoria == "moved_to_discussion" and not com_moved_to_discussion:
            continue
        if categoria in LADOS_VISTOS[lado]:
            handles.append(
                Patch(
                    facecolor=plots.FILL[categoria],
                    hatch=plots.HATCH[categoria],
                    edgecolor="#4D4D4D",
                    label=ROTULO_LADO[categoria],
                )
            )
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), frameon=False, fontsize=8)


def _desenha_piramides(ctx: Any, d: Dados, em_pct: bool) -> None:
    comp = d["composicao"]
    anos = [a for a in ctx.p.anos_piramide if a in set(comp["ano"])]
    codigo = {faixa: i for i, faixa in enumerate(vitalidade.FAIXAS)}
    lado = ctx.p.piramide_lado
    quadros = []
    for ano in anos:
        q = comp[comp["ano"] == ano].copy()
        q["band"] = q["faixa"].map(codigo).astype(int)
        if em_pct:
            q = _em_pct(q)
        quadros.append(_so_o_lado(q, lado))
    xmax = _xmax_das_piramides(quadros)

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
    fig.suptitle(f"{_nome()}: {unidade} por tempo de casa")
    _legenda_piramide(fig, lado, ctx.p.usa_moved_to_discussion)
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


@figura("composicao", "piramides_trimestrais", padrao=True)
def figura_piramides_trimestrais(ctx: Any, d: Dados) -> None:
    """Pirâmides como as do artigo: idade em bandas de 3 meses, no fim dos `anos_piramide`.

    Em % dos ativos do ano quando `piramide_em_pct`. Só para olhar; as métricas usam as faixas
    de 1 ano.
    """
    comp = d["composicao_trimestral"]
    em_pct = ctx.p.piramide_em_pct
    anos = [a for a in ctx.p.anos_piramide if a in set(comp["ano"])]
    lado = ctx.p.piramide_lado
    quadros = []
    for ano in anos:
        q = comp[comp["ano"] == ano].copy()
        if em_pct:
            q = _em_pct(q)
        quadros.append(_so_o_lado(q, lado))
    xmax = _xmax_das_piramides(quadros)
    ymax = max(int(q["band"].max()) for q in quadros)
    fig, eixos = plt.subplots(1, len(anos), figsize=(3.4 * len(anos), 5), sharey=True)
    for ax, ano, q in zip(eixos, anos, quadros, strict=True):
        plots.draw_pyramid(ax, q, xmax=xmax, ymax=ymax)
        ax.set_title(str(ano))
        ax.set_xlabel("% dos ativos do ano" if em_pct else "ativos", fontsize=8)
    unidade = "% dos ativos" if em_pct else "ativos"
    fig.suptitle(f"{_nome()}: {unidade} por tempo de casa, bandas de 3 meses")
    _legenda_piramide(fig, lado, ctx.p.usa_moved_to_discussion)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    salva(fig, "piramides_trimestrais.png")


@figura("composicao", "indice", padrao=True)
def figura_indice(ctx: Any, d: Dados) -> None:
    """Índice de envelhecimento por ano."""
    ind = d["indice_envelhecimento"]
    ind = ind[ind["veteranos"] > 0]  # antes do primeiro veterano o índice é 0 por definição
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.plot(ind["ano"], ind["indice"], color=categorica()[0], linewidth=2, marker="o", markersize=4)
    ax.set_ylabel("ativos com 5 anos ou mais de casa\npara cada ativo com menos de 1 ano")
    ax.set_xlabel("ano")
    ax.set_title(f"{_nome()}: índice de envelhecimento")
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, "indice_envelhecimento.png")


@figura("saida_por_faixa", "linhas", padrao=True)
def figura_taxa_saida(ctx: Any, d: Dados) -> None:
    """Uma linha por faixa; ponto vazado marca célula com poucas saídas."""
    taxa = d["taxa_saida_faixa"]
    taxa = taxa[taxa["ano"] <= _ate_o_ano_decidido(ctx)]
    saidas_estavel = ctx.p.saidas_estavel
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for faixa, cor in zip(vitalidade.FAIXAS, rampa(len(vitalidade.FAIXAS)), strict=True):
        f = taxa[(taxa["faixa"] == faixa) & taxa["taxa_saida"].notna()]
        if f.empty:
            continue
        _plota(
            ax,
            f["ano"],
            f["taxa_saida"],
            _primeiro_provisorio(ctx),
            color=cor,
            linewidth=2,
            label=f"{faixa} anos",
        )
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
    ax.set_ylabel(f"saídas / ativos da faixa\nponto vazado = menos de {saidas_estavel} saídas")
    ax.set_xlabel("ano")
    ax.set_title(f"{_nome()}: taxa de saída por faixa de tempo de casa")
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
    ax.set_xlabel("anos desde a primeira contribuição")
    ax.set_ylabel("fração do grupo ainda ativa")
    ax.set_title(
        f"{_nome()}: de cada 100 pessoas que entram, quantas seguem ativas depois de x anos"
    )
    ax.legend(title="ano de entrada", frameon=False)
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
    ax.set_title(f"{_nome()}: previsão de um ano à frente contra o real\nregra: {rotulo}")
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
    ax.set_title(f"{_nome()}: projeção de ativos a partir de {ultimo}\nregra: {rotulo}")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3, frameon=False)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, f"{pasta}/projecao_futuro.png")


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
        if t.empty:  # linguagem com pouca história: nenhum ano com backtest nesta regra
            ax.set_title(f"{rotulo}\nsem anos suficientes para o backtest")
            plots._theme(ax)
            continue
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
        ax.set_title(f"{rotulo}\no real cai dentro da faixa em {cobertura:.0%} dos {anos}")
        plots._theme(ax)
        ax.set_xlim(t["ano"].min() - 0.7, t["ano"].max() + 0.7)
        ax.set_xticks(t["ano"].tolist())
    for ax in eixos[:, 0]:
        ax.set_ylabel("ativos no ano")
    linhas, rotulos = eixos[0, 0].get_legend_handles_labels()
    fig.legend(linhas, rotulos, loc="lower center", ncol=3, frameon=False)
    fig.suptitle(f"{_nome()}: previsão de um ano à frente contra o real, uma regra por painel")
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
        c = c[c["em_risco"] >= MIN_EXPOSICAO]  # além disso a curva depende de pouca gente
        ax.step(
            c["anos"],
            c["S"],
            where="post",
            color=cor_da(slug),
            linewidth=2,
            label=carga_fonte.LINGUAGENS[slug].nome,
        )
    ax.set_ylim(0, 1)
    ax.set_xlabel(f"anos desde a primeira contribuição, curva até restarem {MIN_EXPOSICAO} pessoas")
    ax.set_ylabel("fração das pessoas ainda ativas")
    ax.set_title("Quanto tempo as pessoas seguem ativas, por linguagem\nmétodo Kaplan-Meier")
    ax.legend(frameon=False)
    plots._theme(ax)
    salva(fig, "kaplan_meier.png", geral=True)


@figura("tabua_comparada", "esperanca", padrao=True)
def figura_tabua_esperanca(ctx: Any, d: Dados) -> None:
    """e(x), a vida restante de quem chegou a x anos de casa, uma linha por linguagem."""
    t = d["tabua_comparada"]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for slug in ctx.p.linguagens_rq2:
        c = t[t["linguagem"] == slug]
        ax.plot(
            c["x"],
            c["e"],
            marker="o",
            color=cor_da(slug),
            linewidth=2,
            label=carga_fonte.LINGUAGENS[slug].nome,
        )
    ax.set_xlabel("anos desde a primeira contribuição")
    ax.set_ylabel("vida restante, e(x), em anos")
    ax.set_title("Quem chegou a x anos, quantos anos ainda restam")
    ax.legend(frameon=False)
    plots._theme(ax)
    salva(fig, "tabua_esperanca_comparada.png", geral=True)


@figura("tabua_comparada", "chegar_e_ficar")
def figura_tabua_chegar_e_ficar(ctx: Any, d: Dados) -> None:
    """Dois painéis: chegar a x anos, S(x), e ficar mais 1 ano tendo chegado, 1 - q(x)."""
    t = d["tabua_comparada"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    for slug in ctx.p.linguagens_rq2:
        c = t[t["linguagem"] == slug]
        nome = carga_fonte.LINGUAGENS[slug].nome
        ax1.plot(c["x"], c["S"], marker="o", color=cor_da(slug), linewidth=2, label=nome)
        ax2.plot(c["x"], 1 - c["q"], marker="o", color=cor_da(slug), linewidth=2, label=nome)
        pouco = c[c["n_efetivo"] < MIN_EXPOSICAO]
        ax2.scatter(
            pouco["x"], 1 - pouco["q"], s=45, facecolor="white", edgecolor=cor_da(slug), zorder=4
        )
    ax1.set_title("Chegar: fração que chega a x anos, S(x)")
    ax2.set_title("Ficar: quem chegou a x segue mais 1 ano, 1 - q(x)")
    ax1.set_ylim(0, 1)
    ax2.set_ylim(0, 1)
    for ax in (ax1, ax2):
        ax.set_xlabel("anos de casa x")
        plots._theme(ax)
    ax2.set_xlabel(f"anos de casa x, ponto vazado = menos de {MIN_EXPOSICAO} pessoas observadas")
    ax1.legend(frameon=False)
    fig.suptitle("Chegar à senioridade e permanecer nela")
    fig.tight_layout()
    salva(fig, "tabua_chegar_e_ficar.png", geral=True)


@figura("comparacao_corrigida", "tres_paineis", padrao=True)
def figura_padronizacao(ctx: Any, d: Dados) -> None:
    """Taxa bruta, padronizada e SMR, um painel cada, uma figura por rodada.

    A padronizada usa as faixas de 0 a 5 anos, que existem em todas as linguagens cinco anos
    depois do nascimento delas. Cada linha começa quando a linguagem tem `MIN_PESSOAS` ativos.
    """
    ano_pesos = ctx.p.ano_pesos
    for rodada, linguagens in ctx.p.rodadas_padronizacao.items():
        pad = d["padronizacao"]
        pad = pad[(pad["rodada"] == rodada) & (pad["ativos"] >= MIN_PESSOAS)]
        fig, eixos = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
        paineis = [
            ("taxa_bruta", "1. Taxa de saída como foi observada", "saídas / ativos"),
            (
                "taxa_padronizada_ate_5a",
                f"2. Taxa de saída com a composição de {ano_pesos} para todas, 0 a 5 anos de casa",
                "saídas / ativos",
            ),
            (
                "smr",
                "3. SMR, saídas observadas divididas pelas esperadas, 1 = igual à referência",
                "SMR",
            ),
        ]
        for ax, (coluna, titulo, rotulo) in zip(eixos, paineis, strict=True):
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
            ax.set_title(titulo, fontsize=10)
            plots._theme(ax)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        eixos[2].axhline(1, color="#888888", linewidth=0.8)
        eixos[0].legend(loc="upper left", frameon=False)
        fig.suptitle("Taxa de saída por ano com a mesma mistura de novatos e veteranos")
        eixos[2].set_xlabel("ano")
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        salva(fig, f"padronizacao_{rodada}.png", geral=True)


@figura("tamanho", "fluxo")
def figura_fluxo(ctx: Any, d: Dados) -> None:
    """Barras por ano: novatos e voltas para cima, saídas para baixo, até o último ano."""
    t = d["anual"]
    t = t[t["ano"] <= _ultimo_ano_de_contagem(ctx)]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.axhline(0, color="#888888", linewidth=0.8)
    ax.bar(t["ano"], t["novatos"], color=categorica()[1], label="novatos")
    ax.bar(t["ano"], t["voltas"], bottom=t["novatos"], color=categorica()[3], label="voltas")
    saidas = -t["saidas"].fillna(0)
    firme = t["ano"] < _primeiro_provisorio(ctx)
    ax.bar(t.loc[firme, "ano"], saidas[firme], color=categorica()[2], label="saídas (para baixo)")
    ax.bar(
        t.loc[~firme, "ano"],
        saidas[~firme],
        color=categorica()[2],
        alpha=0.5,
        hatch="//",
        edgecolor="white",
        label="saídas provisórias",
    )
    ax.set_ylabel("pessoas")
    ax.set_xlabel("ano")
    ax.set_title(f"{_nome()}: novatos, voltas e saídas por ano")
    ax.legend(loc="upper left", frameon=False)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, "fluxo.png")


@figura("tamanho", "troca_de_papel", padrao=True)
def figura_troca_de_papel(ctx: Any, d: Dados) -> None:
    """Quem troca de lado por ano, em % dos ativos: discussão para código (moved) e a volta.

    Para no último ano com futuro: no ano final o último commit é o último da coleta, e quem
    ainda vai codar entra como quem deixou o código.
    """
    t = d["anual"]
    t = t[t["ano"] <= _ate_o_ano_decidido(ctx)]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ida = 100 * t["moved"] / t["ativos"]
    volta = 100 * t["deixou_codigo"] / t["ativos"]
    primeiro = _primeiro_provisorio(ctx)
    _plota(
        ax,
        t["ano"],
        ida,
        primeiro,
        color=categorica()[0],
        marker="o",
        label="discussão para código (moved)",
    )
    _plota(
        ax,
        t["ano"],
        volta,
        primeiro,
        color=categorica()[1],
        marker="o",
        label="código para discussão",
    )
    ax.set_ylabel("% dos ativos do ano")
    ax.set_xlabel("ano")
    ax.set_title(f"{_nome()}: troca de papel por ano")
    ax.legend(frameon=False)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, "troca_de_papel.png")


@figura("composicao", "proporcao")
def figura_proporcao(ctx: Any, d: Dados) -> None:
    """Área empilhada: parcela de cada faixa de tempo de casa nos ativos do ano."""
    c = d["composicao"].copy()
    c["total"] = c[vitalidade.LADOS].sum(axis=1)
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
    ax.set_xlabel("anos desde a primeira contribuição")
    ax.set_ylabel("anos que ainda restam")
    ax.set_title(f"{_nome()}: anos que ainda restam, por coorte de entrada")
    ax.legend(title="coorte", frameon=False)
    plots._theme(ax)
    salva(fig, "tabua_esperanca.png")


@figura("saida_por_faixa", "calor")
def figura_calor(ctx: Any, d: Dados) -> None:
    """Mapa de calor: faixa nas linhas, ano nas colunas, cor = taxa de saída."""
    taxa = d["taxa_saida_faixa"]
    taxa = taxa[taxa["ano"] <= _ate_o_ano_decidido(ctx)]
    m = taxa.pivot(index="faixa", columns="ano", values="taxa_saida").reindex(vitalidade.FAIXAS)
    fig, ax = plt.subplots(figsize=(10, 3.8))
    imagem = ax.imshow(m.to_numpy(dtype=float), aspect="auto", cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(m.columns)), [str(a) for a in m.columns], rotation=90)
    ax.set_yticks(range(len(m.index)), [f"{f} anos" for f in m.index])
    provisorios = [i for i, a in enumerate(m.columns) if a >= _primeiro_provisorio(ctx)]
    if provisorios:
        ax.axvspan(
            provisorios[0] - 0.5,
            provisorios[-1] + 0.5,
            facecolor="none",
            edgecolor="#555555",
            hatch="//",
            linewidth=0,
        )
    fig.colorbar(imagem, ax=ax, label="saídas / ativos da faixa (hachurado = provisório)")
    ax.set_title(f"{_nome()}: taxa de saída por faixa e ano")
    salva(fig, "taxa_saida_calor.png")


@figura("cenarios", "backtest", padrao=True)
def figura_cenarios_backtest(ctx: Any, d: Dados) -> None:
    """Real contra projetado um ano à frente, uma figura por regra de `variantes`."""
    for chave, valores in ctx.p.variantes.items():
        rotulo = valores[0]
        pasta = f"cenarios-{chave}"
        figura_backtest(d[f"{pasta}/projecao_backtest"], ctx.p.teto, pasta, rotulo)


@figura("cenarios", "futuro", padrao=True)
def figura_cenarios_futuro(ctx: Any, d: Dados) -> None:
    """Projeção dos próximos `horizonte` anos, uma figura por regra de `variantes`."""
    for chave, valores in ctx.p.variantes.items():
        rotulo = valores[0]
        pasta = f"cenarios-{chave}"
        futuro = d[f"{pasta}/projecao_futuro"]
        futuro = futuro[futuro["teto"] == ctx.p.teto]
        figura_futuro(ctx.anual, futuro, ctx.fim.year - 1, ctx.p.teto, pasta, rotulo)


def figura_tres_cenarios(
    anual: pd.DataFrame, futuro: pd.DataFrame, ultimo: int, pasta: str, rotulo: str
) -> None:
    """Pessimista, conservador e otimista como três linhas, com o valor final de cada uma."""
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
    cenarios = [
        ("otimista", categorica()[2]),
        ("conservador", categorica()[0]),
        ("pessimista", categorica()[1]),
    ]
    linhas = {}
    for nome, cor in cenarios:
        m = total[total["metodo"] == nome]
        linhas[nome] = pd.concat(
            [
                pd.DataFrame({"ano": ponto["ano"], "previsto": ponto["ativos"]}),
                m[["ano", "previsto"]],
            ]
        )
        ax.plot(
            linhas[nome]["ano"],
            linhas[nome]["previsto"],
            color=cor,
            linewidth=2.5,
            marker="o",
            markersize=4,
            label=nome,
        )
        final = linhas[nome].iloc[-1]
        ax.annotate(
            f"{final['previsto']:,.0f}".replace(",", "."),
            (final["ano"], final["previsto"]),
            textcoords="offset points",
            xytext=(8, 0),
            va="center",
            color=cor,
            fontsize=10,
        )
    ax.fill_between(
        linhas["pessimista"]["ano"],
        linhas["pessimista"]["previsto"],
        linhas["otimista"]["previsto"],
        color="#888888",
        alpha=0.12,
    )
    ax.set_xlim(observado["ano"].min() - 0.5, linhas["otimista"]["ano"].max() + 1.2)
    ax.set_ylabel("ativos no ano")
    ax.set_xlabel("ano")
    ax.set_title(f"{_nome()}: três cenários a partir de {ultimo}\nregra: {rotulo}")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=4, frameon=False)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, f"{pasta}/tres_cenarios.png")


@figura("cenarios", "tres_cenarios", padrao=True)
def figura_cenarios_tres(ctx: Any, d: Dados) -> None:
    """Pessimista, conservador e otimista da projeção, uma figura por regra de `variantes`."""
    for chave, valores in ctx.p.variantes.items():
        rotulo = valores[0]
        pasta = f"cenarios-{chave}"
        futuro = d[f"{pasta}/projecao_futuro"]
        futuro = futuro[futuro["teto"] == ctx.p.teto]
        figura_tres_cenarios(ctx.anual, futuro, ctx.fim.year - 1, pasta, rotulo)
    # A regra principal também fica na pasta da linguagem, onde é fácil de achar.
    principal = next(iter(ctx.p.variantes))
    origem = fb.CFG.saida / PASTA / f"cenarios-{principal}" / "tres_cenarios.png"
    if origem.exists():
        shutil.copy(origem, fb.CFG.saida / PASTA / "tres_cenarios.png")


@figura("cenarios", "comparadas", padrao=True)
def figura_cenarios_comparadas(ctx: Any, d: Dados) -> None:
    """Todas as regras de `variantes` lado a lado, um painel por regra."""
    if len(ctx.p.variantes) < 2:
        return
    bts = {}
    for chave, valores in ctx.p.variantes.items():
        rotulo = valores[0]
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


# shortcut: com menos pessoas que isso as razões (CCR, NCR, taxas, SMR) saltam sem dizer nada, e
# a figura começa quando a comunidade tem 100. Vira parâmetro se alguém precisar de outro corte.
MIN_PESSOAS = 100

# Uma taxa de saída de uma idade só vale com pelo menos isto de exposição efetiva (`n_efetivo`).
MIN_EXPOSICAO = 30


def _ccr_ncr_com_massa(t: pd.DataFrame) -> pd.DataFrame:
    """Só os trimestres em que a comunidade já tem `MIN_PESSOAS` ativos."""
    return t[t["total"] >= MIN_PESSOAS].dropna(subset=["ccr", "ncr"])


@figura("ccr_ncr_comparado", "dispersao", padrao=True)
def figura_ccr_ncr_comparado(ctx: Any, d: Dados) -> None:
    """CCR x NCR no fim de cada ano de `anos_piramide`, um ponto por linguagem em cada painel."""
    t = _ccr_ncr_com_massa(d["ccr_ncr_comparado"])
    t = t[pd.to_datetime(t["snapshot"]).dt.month == 12].copy()
    t["ano"] = pd.to_datetime(t["snapshot"]).dt.year
    anos = list(ctx.p.anos_piramide)
    colunas = min(3, len(anos))
    linhas = -(-len(anos) // colunas)
    fig, eixos = plt.subplots(linhas, colunas, figsize=(5 * colunas, 4.8 * linhas), squeeze=False)
    for ax, ano in zip(eixos.flat, anos, strict=False):
        ax.axhline(0, color="#888888", linewidth=0.7)
        ax.axvline(0, color="#888888", linewidth=0.7)
        for _, ponto in t[t["ano"] == ano].iterrows():
            cor = cor_da(ponto["slug"])
            ax.scatter(
                [ponto["ccr"]], [ponto["ncr"]], color=cor, s=130, edgecolor="white", zorder=3
            )
            ax.annotate(
                carga_fonte.LINGUAGENS[ponto["slug"]].nome,
                (ponto["ccr"], ponto["ncr"]),
                fontsize=9,
                textcoords="offset points",
                xytext=(8, 6),
            )
        ax.set_xlim(-1.05, 1.05)
        ax.set_ylim(-1.05, 1.05)
        ax.set_title(str(ano))
        for texto, x, y in (("A", 0.9, 0.9), ("B", -0.9, 0.9), ("C", 0.9, -0.9), ("D", -0.9, -0.9)):
            ax.text(x, y, texto, fontsize=12, color="#999999", ha="center", va="center")
        plots._theme(ax)
    for ax in eixos.flat[len(anos) :]:
        ax.set_visible(False)
    for ax in eixos[-1]:
        ax.set_xlabel("CCR, código contra discussão")
    for ax in eixos[:, 0]:
        ax.set_ylabel("NCR, novatos contra experientes")
    fig.suptitle("CCR x NCR no fim de cada ano, uma linguagem por ponto")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    salva(fig, "ccr_ncr_dispersao.png", geral=True)


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
    """SMR de cada linguagem por ano, em um painel só, uma figura por rodada."""
    for rodada, linguagens in ctx.p.rodadas_padronizacao.items():
        pad = d["padronizacao"]
        pad = pad[pad["rodada"] == rodada]
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.axhline(1, color="#888888", linewidth=0.8)
        for slug in linguagens:
            t = pad[(pad["linguagem"] == slug) & pad["smr"].notna()]
            nome = carga_fonte.LINGUAGENS[slug].nome
            ax.plot(t["ano"], t["smr"], color=cor_da(slug), linewidth=2, label=nome)
        ax.set_ylabel("SMR (saídas reais / esperadas)")
        ax.set_xlabel("ano")
        ax.set_title(f"SMR, rodada {rodada}, referência de {ctx.p.ano_pesos}")
        ax.legend(frameon=False)
        plots._theme(ax)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        salva(fig, f"smr_{rodada}.png", geral=True)


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


def _linhas_por_linguagem(
    ax: Any, t: pd.DataFrame, coluna: str, desde: int, com_cauda: bool = False
) -> None:
    """Uma linha por linguagem; com `com_cauda`, os anos provisórios saem tracejados.

    Cada linha começa quando a linguagem tem `MIN_PESSOAS` ativos, e nunca antes de `desde`.
    """
    t = t[t["ativos"] >= MIN_PESSOAS]
    for slug in t["slug"].drop_duplicates():
        f = t[(t["slug"] == slug) & (t["ano"] >= desde) & t[coluna].notna()]
        nome = carga_fonte.LINGUAGENS[slug].nome
        estilo = {"color": cor_da(slug), "linewidth": 2, "marker": "o", "markersize": 4}
        if not com_cauda:
            ax.plot(f["ano"], f[coluna], label=nome, **estilo)
            continue
        firme = f[~f["provisorio"]]
        ax.plot(firme["ano"], firme[coluna], label=nome, **estilo)
        cauda = f[f["provisorio"] | (f["ano"] == firme["ano"].max())]
        if len(cauda) > 1:
            ax.plot(cauda["ano"], cauda[coluna], linestyle="--", **estilo)
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))


@figura("trajetoria", "indice", padrao=True)
def figura_indice_de_ativos(ctx: Any, d: Dados) -> None:
    """Ativos de cada linguagem, índice 100 em `ano_base_indice`: tira o tamanho da comparação."""
    base = ctx.p.ano_base_indice
    fig, ax = plt.subplots(figsize=(9, 4.5))
    _linhas_por_linguagem(ax, d["trajetoria"], "indice", base)
    ax.axhline(100, color="#888888", linewidth=0.8)
    ax.set_yscale("log")  # o Zig cresce 10 vezes, o Clojure cai 30%: só a escala log mostra os dois
    ax.yaxis.set_major_formatter(FuncFormatter(lambda valor, _: f"{valor:g}"))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_yticks([50, 100, 200, 400, 800])
    ax.set_ylabel(f"ativos no ano, índice com {base} = 100")
    ax.set_xlabel("ano")
    ax.set_title("Número de ativos de cada linguagem, com 100 no ano base")
    ax.legend(frameon=False)
    salva(fig, "trajetoria_indice.png", geral=True)


@figura("trajetoria", "crescimento", padrao=True)
def figura_crescimento_comparado(ctx: Any, d: Dados) -> None:
    """Crescimento natural do ano: tudo que entra menos tudo que sai, em % dos ativos do ano."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    _linhas_por_linguagem(
        ax, d["trajetoria"], "crescimento_natural_pct", ctx.p.ano_inicio_comparacao, com_cauda=True
    )
    ax.axhline(0, color="#888888", linewidth=0.8)
    ax.set_ylabel(f"% da {TERMO_POPULACAO}")
    ax.set_xlabel("ano")
    ax.set_title("Crescimento natural por ano, todo mundo que entrou menos todo mundo que saiu")
    ax.legend(frameon=False)
    salva(fig, "trajetoria_crescimento.png", geral=True)


@figura("trajetoria", "linha_do_tempo", padrao=True)
def figura_piramides_linha_do_tempo(ctx: Any, d: Dados) -> None:
    """Pirâmides em % de cada linguagem (linhas) em cada ano de `anos_piramide` (colunas)."""
    comp = d["composicao_pct"]
    ativos = d["trajetoria"].set_index(["slug", "ano"])["ativos"]
    anos = list(ctx.p.anos_piramide)
    slugs = list(ctx.p.linguagens_rq2)
    codigo = {faixa: i for i, faixa in enumerate(vitalidade.FAIXAS)}
    lado = ctx.p.piramide_lado
    # Escala comum só entre os painéis desenhados: um ano com 3 ativos tem barra de 100%.
    # Nenhuma passa de 50% dos ativos; se passar, a escala cresce junto.
    mostrados = []
    for _, linha in comp.iterrows():
        grande = ativos.get((linha["slug"], linha["ano"]), 0) >= MIN_PESSOAS
        mostrados.append(bool(grande and linha["slug"] in slugs and linha["ano"] in anos))
    xmax = _xmax_das_piramides([_so_o_lado(comp[mostrados], lado)], minimo=50.0)
    fig, eixos = plt.subplots(
        len(slugs), len(anos), figsize=(3.0 * len(anos), 2.5 * len(slugs)), sharey=True
    )
    for i, slug in enumerate(slugs):
        for j, ano in enumerate(anos):
            ax = eixos[i][j]
            q = comp[(comp["slug"] == slug) & (comp["ano"] == ano)].copy()
            tem = (slug, ano) in ativos.index and ativos[(slug, ano)] >= MIN_PESSOAS
            if tem:
                q["band"] = q["faixa"].map(codigo).astype(int)
                plots.draw_pyramid(ax, _so_o_lado(q, lado), xmax=xmax)
            else:
                ax.text(0.5, 0.5, "menos de 100 ativos", ha="center", va="center", color="#999999")
                ax.set_xticks([])
            ax.set_ylim(-0.6, len(vitalidade.FAIXAS) - 0.4)
            ax.set_yticks(range(len(vitalidade.FAIXAS)))
            ax.set_yticklabels([f"{f} anos" for f in vitalidade.FAIXAS], fontsize=7)
            if i == 0:
                ax.set_title(str(ano))
            if j == 0:
                ax.set_ylabel(carga_fonte.LINGUAGENS[slug].nome, fontsize=11)
            if i == len(slugs) - 1 and tem:
                ax.set_xlabel("% dos ativos do ano", fontsize=7)
    fig.suptitle("Pirâmides por tempo de casa, linha do tempo por linguagem")
    _legenda_piramide(fig, lado, ctx.p.usa_moved_to_discussion)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    salva(fig, "trajetoria_linha_do_tempo.png", geral=True)


@figura("trajetoria", "reposicao", padrao=True)
def figura_reposicao(ctx: Any, d: Dados) -> None:
    """Todo mundo que entrou para cada pessoa que saiu, por ano. Acima de 1 há crescimento."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    _linhas_por_linguagem(ax, d["trajetoria"], "reposicao", 0, com_cauda=True)
    ax.axhline(1, color="#888888", linewidth=0.8)
    # Escala log: dobrar e cortar pela metade ficam à mesma distância de 1.
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda valor, _: f"{valor:g}"))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_yticks([0.25, 0.5, 1, 2, 4, 8, 12])
    ax.set_ylabel("entrou para cada pessoa que saiu")
    ax.set_xlabel("ano")
    ax.set_title("Reposição: todo mundo que entrou dividido por todo mundo que saiu")
    ax.legend(frameon=False)
    salva(fig, "trajetoria_reposicao.png", geral=True)


def lados_por_ano(d: Dados) -> pd.DataFrame:
    """% dos ativos do ano do lado do código (moved e coding) e do lado da discussão, por ano."""
    c = d["composicao_pct"]
    por_ano = c.groupby(["slug", "ano"])[vitalidade.LADOS].sum().reset_index()
    por_ano["codigo_pct"] = por_ano["moved"] + por_ano["coding"]
    por_ano["discussao_pct"] = por_ano["non_coding"] + por_ano["moved_to_discussion"]
    ativos = d["trajetoria"][["slug", "ano", "ativos"]]
    por_ano = por_ano.merge(ativos, on=["slug", "ano"])
    return por_ano[por_ano["ativos"] >= MIN_PESSOAS]


@figura("trajetoria", "lados", padrao=True)
def figura_lados(ctx: Any, d: Dados) -> None:
    """Parcela da população do ano que já fez commit ou PR (lado do código), por linguagem."""
    t = lados_por_ano(d)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.axhline(50, color="#888888", linewidth=0.8)
    for slug in ctx.p.linguagens_rq2:
        f = t[(t["slug"] == slug) & (t["ano"] >= ctx.p.ano_inicio_comparacao)]
        ax.plot(
            f["ano"],
            f["codigo_pct"],
            color=cor_da(slug),
            linewidth=2,
            marker="o",
            markersize=4,
            label=carga_fonte.LINGUAGENS[slug].nome,
        )
    ax.set_ylim(0, 100)
    ax.set_ylabel(f"% da {TERMO_POPULACAO} do lado do código")
    ax.set_xlabel("ano")
    ax.set_title("Lado do código: quem já fez commit ou PR, o resto discute")
    ax.legend(frameon=False, ncol=5, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    plots._theme(ax)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    salva(fig, "trajetoria_lados.png", geral=True)


@figura("trajetoria", "taxas")
def figura_taxas_de_saida_e_volta(ctx: Any, d: Dados) -> None:
    """Saídas e voltas de cada ano, em % dos ativos, em dois painéis."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    _linhas_por_linguagem(
        ax1, d["trajetoria"], "saida_pct", ctx.p.ano_inicio_comparacao, com_cauda=True
    )
    _linhas_por_linguagem(ax2, d["trajetoria"], "volta_pct", ctx.p.ano_inicio_comparacao)
    ax1.set_ylabel("saídas, % dos ativos")
    ax2.set_ylabel("voltas, % dos ativos")
    ax2.set_xlabel("ano")
    ax1.set_title("Saídas por ano e voltas depois de 12 meses sem contribuir")
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
    lado = ctx.p.piramide_lado
    for slug in slugs:
        q = comp[comp["slug"] == slug].copy()
        q["band"] = q["faixa"].map(codigo).astype(int)
        quadros.append(_so_o_lado(q, lado))
    xmax = _xmax_das_piramides(quadros)
    fig, eixos = plt.subplots(1, len(slugs), figsize=(3.4 * len(slugs), 3.8), sharey=True)
    for ax, slug, q in zip(eixos, slugs, quadros, strict=True):
        plots.draw_pyramid(ax, q, xmax=xmax)
        ax.set_ylim(-0.6, len(vitalidade.FAIXAS) - 0.4)
        ax.set_yticks(range(len(vitalidade.FAIXAS)), minor=False)
        ax.set_yticks([], minor=True)
        ax.set_yticklabels([f"{f} anos" for f in vitalidade.FAIXAS])
        ax.set_title(carga_fonte.LINGUAGENS[slug].nome)
        ax.set_xlabel("% dos ativos do ano", fontsize=8)
    fig.suptitle(f"Composição por tempo de casa em {ano}")
    _legenda_piramide(fig, lado, ctx.p.usa_moved_to_discussion)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    salva(fig, "trajetoria_piramides.png", geral=True)


carrega_estilo([])  # estilo padrão do yaml; `main` recarrega com os `--estilo`
