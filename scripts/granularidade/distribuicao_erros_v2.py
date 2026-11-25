"""Distribuição dos erros da projeção por método e linguagem: histograma do erro com sinal e do ABRE, com curva normal, e tabelas. Sem projeção nova.

Cenários: Longo, não casuais (dezembro), Curto, não casuais (todos os trimestres) e Curto, não casuais (só dezembro). Linguagens: Clojure, Elixir, Zig, OCaml e Python.
Métodos: Ingênua, Coorte, Coorte^R, Conservador^R e Ingênua-Coorte^R (nomes internos `ingenua`, `coorte_R0`, `coorte_R3`, `conservador_R3`, `C3_R3`).
Erro com sinal = (previsto - real) / real, em %. ABRE = |previsto - real| / min(previsto, real).
Uma figura por cenário, método e medida, com um painel por linguagem, o mesmo eixo x nos cinco painéis, histograma, curva normal com a mesma média e o mesmo desvio, linha no zero,
média (traço cheio) e mediana (tracejado), e o n e o p do Shapiro-Wilk escritos no painel. Uma tabela por cenário.
Se faltar arquivo, método, par ou teste de vazamento de Zig, para e mostra onde.

Uso (na raiz do repo): uv run --no-project --with pandas --with numpy --with scipy --with matplotlib python scripts/granularidade/distribuicao_erros_v2.py <projecao-cenarios-v3b> <saida>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm, shapiro

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tabelas_cenarios import METODOS, origens

PASTA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
LINGUAS = ["clojure", "elixir", "zig", "ocaml", "python"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "ocaml": "OCaml",
    "python": "Python",
}
# nome do cenário -> (código nos arquivos, só dezembro?, parte do nome de arquivo)
CENARIOS = {
    "Longo, não casuais": ("S4", True, "longo_nao_casuais"),
    "Curto, não casuais (todos os trimestres)": ("S5", False, "curto_nao_casuais_trimestres"),
    "Curto, não casuais (só dezembro)": ("S5", True, "curto_nao_casuais_dezembro"),
}
INTERNOS = list(METODOS)
ARQUIVO_DO_METODO = {
    "Ingênua": "ingenua",
    "Coorte": "coorte",
    "Coorte^R": "coorte_r",
    "Conservador^R": "conservador_r",
    "Ingênua-Coorte^R": "ingenua_coorte_r",
}
COR = {
    "Ingênua": "#7f7f7f",
    "Coorte": "#1f77b4",
    "Coorte^R": "#d62728",
    "Conservador^R": "#2ca02c",
    "Ingênua-Coorte^R": "#9467bd",
}
MEDIDAS = {"sinal": "Erro com sinal (previsto − real) / real (%)", "abre": "ABRE"}

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 7,
        "axes.labelsize": 7,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
    }
)


def dec(x: float, casas: int = 1) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def p_texto(p: float) -> str:
    if pd.isna(p):
        return "n/d"
    return "< 0,001" if p < 0.001 else dec(p, 3)


# Zig: confere o teste de vazamento que já existe nos dois cenários
vazamento_zig = []
for codigo in ("S4", "S5"):
    arquivo = PASTA / "unidades" / f"zig_{codigo}_vazamento.csv"
    if not arquivo.exists():
        sys.exit(f"falta o teste de vazamento de Zig: {arquivo}")
    v = pd.read_csv(arquivo)
    ok = (
        bool(v["estados_iguais"].all())
        and bool((v["maior_diferenca_relativa"] < 1e-9).all())
        and bool(v["controle_eventos_futuros_difere"].any())
        and bool(v["controle_promocoes_difere"].any())
    )
    if not ok:
        sys.exit(f"o teste de vazamento de Zig falhou em {codigo}: {arquivo}")
    vazamento_zig.append(
        f"{codigo}: {len(v)} origens testadas, estados iguais, diferença zero, controle com eventos futuros difere em {int(v['controle_eventos_futuros_difere'].sum())}"
    )

# Pares por cenário e linguagem
linhas = []
fora = []
for nome_cenario, (codigo, so_dezembro, _) in CENARIOS.items():
    for lingua in LINGUAS:
        caminhos = [
            PASTA / "unidades" / f"{lingua}_{codigo}_pares.csv.gz",
            PASTA / "unidades" / f"{lingua}_{codigo}_R3_pares.csv.gz",
        ]
        for caminho in caminhos:
            if not caminho.exists():
                sys.exit(f"falta o arquivo {caminho}")
        t = pd.concat([pd.read_csv(c) for c in caminhos], ignore_index=True)
        t = t[t["metodo"].isin(INTERNOS)].drop_duplicates(["k", "metodo"])
        faltam = [m for m in INTERNOS if m not in set(t["metodo"])]
        if faltam:
            sys.exit(f"{lingua} {codigo}: faltam os métodos {faltam}")
        abre = t.pivot(index="k", columns="metodo", values="abre")[INTERNOS]
        abre["origem"] = pd.to_datetime(t.drop_duplicates("k").set_index("k")["origem"])
        escolhidas = origens(abre, so_dezembro)
        candidatas = abre[abre["origem"] >= pd.Timestamp("2017-01-01")]
        if so_dezembro:
            candidatas = candidatas[candidatas["origem"].dt.month == 12]
        for k in candidatas.index.difference(escolhidas.index):
            fora.append((nome_cenario, lingua, candidatas.loc[k, "origem"].date().isoformat()))
        base = t.set_index(["k", "metodo"])
        for k in escolhidas.index:
            for interno in INTERNOS:
                x = base.loc[(k, interno)]
                p, r = float(x["previsto"]), float(x["real"])
                if not (p > 0 and r > 0):
                    sys.exit(
                        f"par faltando: {lingua} {codigo} origem {x['origem']} método {interno}: previsto {p}, real {r}"
                    )
                linhas.append(
                    {
                        "cenario": nome_cenario,
                        "linguagem": lingua,
                        "origem": x["origem"],
                        "metodo": METODOS[interno],
                        "previsto": p,
                        "real": r,
                        "sinal": 100 * (p - r) / r,
                        "abre": abs(p - r) / min(p, r),
                        "erro_pessoas": abs(p - r),
                    }
                )
pares = pd.DataFrame(linhas)
pares.to_csv(SAIDA / "erros_por_origem.csv", index=False, float_format="%.10g")
pd.DataFrame(fora, columns=["cenario", "linguagem", "origem"]).to_csv(
    SAIDA / "origens_fora.csv", index=False
)


def shapiro_p(v: np.ndarray) -> float:
    if len(v) < 3 or np.ptp(v) == 0:
        return float("nan")
    return float(shapiro(v).pvalue)


# Figuras: um arquivo por cenário, método e medida, com um painel por linguagem
for nome_cenario, (_, _, arquivo_cenario) in CENARIOS.items():
    for metodo in list(ARQUIVO_DO_METODO):
        for medida, rotulo_x in MEDIDAS.items():
            dados = {
                lingua: pares[
                    (pares["cenario"] == nome_cenario)
                    & (pares["linguagem"] == lingua)
                    & (pares["metodo"] == metodo)
                ][medida].to_numpy()
                for lingua in LINGUAS
            }
            todos = np.concatenate([v for v in dados.values() if len(v)])
            menor, maior = float(todos.min()), float(todos.max())
            if medida == "sinal":  # o zero tem de aparecer
                menor, maior = min(menor, 0.0), max(maior, 0.0)
            else:
                menor = 0.0
            folga = 0.08 * (maior - menor)
            limite = (menor - (folga if medida == "sinal" else 0.0), maior + folga)
            bordas = np.linspace(limite[0], limite[1], 13)
            largura = bordas[1] - bordas[0]
            fig, eixos = plt.subplots(
                1, len(LINGUAS), figsize=(7.2, 2.1), sharex=True, constrained_layout=True
            )
            for eixo, lingua in zip(eixos, LINGUAS, strict=True):
                v = dados[lingua]
                eixo.set_xlim(*limite)
                eixo.set_title(NOMES[lingua], fontsize=7.5)
                if len(v) == 0:
                    eixo.text(
                        0.5,
                        0.5,
                        "n = 0\nsem origem com os\ncinco métodos\ncom projeção",
                        transform=eixo.transAxes,
                        ha="center",
                        va="center",
                        fontsize=6,
                    )
                    continue
                eixo.hist(
                    v, bins=bordas, color=COR[metodo], alpha=0.55, edgecolor="white", linewidth=0.4
                )
                media, mediana = float(v.mean()), float(np.median(v))
                if len(v) >= 2 and v.std(ddof=1) > 0:
                    x = np.linspace(limite[0], limite[1], 300)
                    eixo.plot(
                        x,
                        len(v) * largura * norm.pdf(x, media, v.std(ddof=1)),
                        color="black",
                        linewidth=0.8,
                    )
                eixo.axvline(0, color="black", linewidth=0.6, linestyle=":")
                eixo.axvline(media, color="black", linewidth=1.3)
                eixo.axvline(mediana, color="black", linewidth=1.3, linestyle="--")
                eixo.set_xlim(*limite)
                eixo.set_title(NOMES[lingua], fontsize=7.5)
                eixo.text(
                    0.97,
                    0.97,
                    f"n = {len(v)}\nShapiro-Wilk\np = {p_texto(shapiro_p(v))}",
                    transform=eixo.transAxes,
                    ha="right",
                    va="top",
                    fontsize=5.8,
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.2, "alpha": 0.8},
                )
                eixo.yaxis.get_major_locator().set_params(integer=True)
            eixos[0].set_ylabel("Origens")
            eixos[len(LINGUAS) // 2].set_xlabel(rotulo_x)
            legenda = [
                plt.Line2D([], [], color="black", linewidth=1.3, label="média"),
                plt.Line2D([], [], color="black", linewidth=1.3, linestyle="--", label="mediana"),
                plt.Line2D([], [], color="black", linewidth=0.6, linestyle=":", label="zero"),
                plt.Line2D(
                    [],
                    [],
                    color="black",
                    linewidth=0.8,
                    label="curva normal (mesma média e desvio)",
                ),
            ]
            fig.legend(handles=legenda, loc="outside lower center", ncol=4, frameon=False)
            fig.suptitle(f"{nome_cenario}, {metodo}", fontsize=7.5)
            fig.savefig(SAIDA / f"hist_{arquivo_cenario}_{ARQUIVO_DO_METODO[metodo]}_{medida}.pdf")
            plt.close(fig)
    print(f"{nome_cenario}: figuras prontas", flush=True)

# Tabelas
colunas_csv = []
for nome_cenario, (_, _, arquivo_cenario) in CENARIOS.items():
    T = [
        f"# {nome_cenario}: medidas de erro por método e linguagem",
        "",
        "Erro com sinal = (previsto − real) / real, em %. Viés = média do erro com sinal. Desvio = desvio padrão (n − 1) do erro com sinal. Raiz do erro quadrático médio relativo = raiz da média de ((previsto − real) / real)², em %. Erro absoluto = |previsto − real| em pessoas. p = Shapiro-Wilk, do erro com sinal e do ABRE. n d quando n < 3.",
        "",
        "| Método | Linguagem | Origens | Viés (%) | Desvio (%) | Raiz do erro quadrático médio relativo (%) | Erro absoluto médio (pessoas) | ABRE médio | ABRE mediano | p Shapiro-Wilk, erro com sinal | p Shapiro-Wilk, ABRE |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for metodo in ARQUIVO_DO_METODO:
        for lingua in LINGUAS:
            s = pares[
                (pares["cenario"] == nome_cenario)
                & (pares["linguagem"] == lingua)
                & (pares["metodo"] == metodo)
            ]
            sinal = s["sinal"].to_numpy()
            if len(s) == 0:
                T.append(
                    f"| {metodo} | {NOMES[lingua]} | 0 | n/d | n/d | n/d | n/d | n/d | n/d | n/d | n/d |"
                )
                continue
            registro = {
                "cenario": nome_cenario,
                "metodo": metodo,
                "linguagem": lingua,
                "origens": len(s),
                "vies_pct": sinal.mean(),
                "desvio_pct": sinal.std(ddof=1) if len(s) > 1 else float("nan"),
                "raiz_erro_quadratico_medio_relativo_pct": float(np.sqrt(np.mean(sinal**2))),
                "erro_absoluto_medio_pessoas": s["erro_pessoas"].mean(),
                "abre_medio": s["abre"].mean(),
                "abre_mediano": s["abre"].median(),
                "p_shapiro_erro_com_sinal": shapiro_p(sinal),
                "p_shapiro_abre": shapiro_p(s["abre"].to_numpy()),
            }
            colunas_csv.append(registro)
            T.append(
                f"| {metodo} | {NOMES[lingua]} | {len(s)} | {dec(registro['vies_pct'])} | {dec(registro['desvio_pct'])} | {dec(registro['raiz_erro_quadratico_medio_relativo_pct'])} | {milhar(registro['erro_absoluto_medio_pessoas'])} | {dec(registro['abre_medio'], 3)} | {dec(registro['abre_mediano'], 3)} | {p_texto(registro['p_shapiro_erro_com_sinal'])} | {p_texto(registro['p_shapiro_abre'])} |"
            )
    T.append("")
    (SAIDA / f"tabela_{arquivo_cenario}.md").write_text("\n".join(T) + "\n", encoding="utf-8")
pd.DataFrame(colunas_csv).to_csv(SAIDA / "tabelas.csv", index=False, float_format="%.10g")

n_por = (
    pares.groupby(["cenario", "linguagem"])["origem"]
    .nunique()
    .unstack()
    .reindex(columns=LINGUAS)
    .fillna(0)
)
LEIA = [
    "# Leia-me: distribuição dos erros da projeção (Longo e Curto, não casuais)",
    "",
    "Nenhuma projeção foi calculada de novo. Tudo vem dos pares previsto e real por origem de `projecao-cenarios-v3b/unidades/`, nas mesmas origens das tabelas de ABRE (de 2017 em diante, só origens em que os cinco métodos têm ABRE definido).",
    "",
    "## Cenários, linguagens e métodos",
    "",
    "- Longo, não casuais: saída de 12 meses, horizonte de 12 meses, recortes trimestrais, só origens de dezembro (arquivos `*_S4_*`).",
    "- Curto, não casuais (todos os trimestres) e (só dezembro): saída de 12 meses, horizonte de 3 meses, recortes trimestrais (arquivos `*_S5_*`).",
    "- Linguagens: Clojure, Elixir, Zig, OCaml e Python. Os pares de Zig já existiam nesses dois cenários, com o teste de vazamento: "
    + "; ".join(vazamento_zig)
    + ".",
    "- Zig: os pares existem, mas só a Ingênua tem ABRE (nas 32 origens do Longo e nas 35 do Curto). Coorte, Coorte^R e Ingênua-Coorte^R ficam sem projeção em todas as origens, e o Conservador^R em todas menos uma (Longo, dezembro de 2023) ou quatro (Curto, de dezembro de 2023 em diante), porque a pirâmide de Zig sempre tem faixa com gente e sem taxa de permanência (comunidade jovem). Sem origem com os cinco métodos definidos, os painéis de Zig ficam vazios (n = 0) e as linhas de Zig nas tabelas saem com n = 0. Nada foi rodado de novo, porque o vazio vem do método e não de dado faltando.",
    "- Métodos e nomes internos: Ingênua (`ingenua`), Coorte (`coorte_R0`), Coorte^R (`coorte_R3`), Conservador^R (`conservador_R3`) e Ingênua-Coorte^R (`C3_R3`).",
    "",
    "## Origens por painel",
    "",
    "| Cenário | " + " | ".join(NOMES[x] for x in LINGUAS) + " |",
    "|---|" + "---|" * len(LINGUAS),
]
for nome_cenario in CENARIOS:
    LEIA.append(
        f"| {nome_cenario} | "
        + " | ".join(str(int(n_por.loc[nome_cenario, x])) for x in LINGUAS)
        + " |"
    )
LEIA += [
    "",
    "Origens que ficaram de fora (algum método sem ABRE definido, em geral porque a linguagem ainda tinha pouca história) estão em `origens_fora.csv`.",
    "",
    "## Medidas",
    "",
    "- Erro com sinal: (previsto − real) / real, em %. Positivo é superestimar.",
    "- ABRE: |previsto − real| / min(previsto, real).",
    "- Raiz do erro quadrático médio relativo: raiz da média de ((previsto − real) / real)², em %.",
    "- Erro absoluto: |previsto − real| em pessoas.",
    "",
    "## Figuras",
    "",
    "`hist_<cenário>_<método>_<medida>.pdf`, com cenário `longo_nao_casuais`, `curto_nao_casuais_trimestres` ou `curto_nao_casuais_dezembro`, método `ingenua`, `coorte`, `coorte_r`, `conservador_r` ou `ingenua_coorte_r`, e medida `sinal` ou `abre`. Cada figura tem 5 painéis, um por linguagem, com o mesmo eixo x. O histograma conta origens; a curva normal tem a mesma média e o mesmo desvio (n − 1) e é escalada para contagens; o traço cheio é a média, o tracejado é a mediana e o pontilhado é o zero. Cada painel traz o n e o p do Shapiro-Wilk.",
    "",
    "## Avisos",
    "",
    "- No Curto, não casuais com todos os trimestres, origens vizinhas compartilham 9 dos 12 meses da janela de atividade e os alvos se sobrepõem. As origens não são independentes, então o histograma e o Shapiro-Wilk descrevem e não servem de teste.",
    "- Com 7 origens (dezembro) o Shapiro-Wilk quase nunca rejeita a normalidade. p alto com n pequeno não mostra normalidade. Elixir e Zig têm menos origens ainda.",
    "- A curva normal em n pequeno é só uma referência de escala.",
]
(SAIDA / "LEIA-ME.md").write_text("\n".join(LEIA) + "\n", encoding="utf-8")
print(n_por)
print(f"origens fora: {len(fora)}; linhas: {len(pares)}")
