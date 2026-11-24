"""Distribuição do ABRE e outras medidas de erro dos cinco métodos do artigo, sem recalcular nenhuma projeção.

Lê `<pasta>/unidades/<l>_<cenario>_pares.csv.gz` e `_R3_pares.csv.gz` (previsto e real por origem), com as mesmas origens das tabelas de ABRE (`tabelas_cenarios.origens`).
Grava em `<saida>`:
  - `medidas_por_origem.csv`: previsto, real, ABRE, MRE, MER e erro absoluto em pessoas de cada origem e método;
  - `caixas_<cenario>.pdf`: uma figura por cenário, uma linha por linguagem, com pontos por origem, caixa, média (losango) e mediana (traço);
  - `histogramas_<cenario>.pdf` e `qq_<cenario>.pdf`: diferenças pareadas de ABRE contra a Ingênua (o que o Wilcoxon testa), uma linha por linguagem e uma coluna por método;
  - `shapiro_wilk.csv` e `.md`: Shapiro-Wilk dessas diferenças;
  - `medidas_por_cenario.md` e `.csv`: média e mediana de cada medida por linguagem, método e cenário;
  - `ordem_dos_metodos.md`: a ordem dos métodos por medida e se ela muda em relação ao ABRE.

Medidas (P é o previsto e R o real): ABRE = |P - R| / min(P, R); MRE = |P - R| / R; MER = |P - R| / P; erro absoluto = |P - R| em pessoas.
Se faltar arquivo, método ou valor numa origem escolhida, para e mostra onde.

Uso (na raiz do repo): uv run --no-project --with pandas --with numpy --with scipy --with matplotlib python scripts/granularidade/distribuicao_erros.py <projecao-cenarios-v3b> <saida>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import probplot, shapiro

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tabelas_cenarios import LINGUAS, METODOS, NOMES, origens

PASTA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
NOME_DO_CENARIO = {
    "S1": "Curto e amplo",
    "S3h": "Longo e amplo",
    "S4": "Longo, não casuais",
    "S5": "Curto, não casuais",
    "S2": "Anual",
}
# cenário -> só dezembro?
SO_DEZEMBRO = {"S1": False, "S3h": False, "S4": True, "S5": False, "S2": True}
# colunas das tabelas: o Curto não casuais aparece também só com dezembro
COLUNAS_TABELA = [
    ("S1", False),
    ("S3h", False),
    ("S4", True),
    ("S5", False),
    ("S5", True),
    ("S2", True),
]
MEDIDAS = {"abre": "ABRE", "mre": "MRE", "mer": "MER", "erro_abs": "Erro absoluto (pessoas)"}
INTERNOS = list(METODOS)  # ingenua, coorte_R0, coorte_R3, conservador_R3, C3_R3
NOME_DO_METODO = list(METODOS.values())
COR = {
    "Ingênua": "#7f7f7f",
    "Coorte": "#1f77b4",
    "Coorte^R": "#d62728",
    "Conservador^R": "#2ca02c",
    "Ingênua-Coorte^R": "#9467bd",
}
CONTRA_A_INGENUA = [m for m in NOME_DO_METODO if m != "Ingênua"]

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
    }
)


def dec(x: float, casas: int = 3) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


def milhar(x: float) -> str:
    return "n/d" if pd.isna(x) else f"{x:,.0f}".replace(",", ".")


def le_pares(cenario: str, lingua: str) -> pd.DataFrame:
    caminhos = [
        PASTA / "unidades" / f"{lingua}_{cenario}_pares.csv.gz",
        PASTA / "unidades" / f"{lingua}_{cenario}_R3_pares.csv.gz",
    ]
    for caminho in caminhos:
        if not caminho.exists():
            sys.exit(f"falta o arquivo {caminho}")
    t = pd.concat([pd.read_csv(c) for c in caminhos], ignore_index=True)
    t = t[t["metodo"].isin(INTERNOS)].drop_duplicates(["k", "metodo"])
    faltam = [m for m in INTERNOS if m not in set(t["metodo"])]
    if faltam:
        sys.exit(f"{lingua} {cenario}: faltam os métodos {faltam}")
    return t


# 1. Pares por origem, só nas origens das tabelas de ABRE
linhas = []
excluidas = []
for cenario in NOME_DO_CENARIO:
    for lingua in LINGUAS:
        t = le_pares(cenario, lingua)
        abre = t.pivot(index="k", columns="metodo", values="abre")[INTERNOS]
        abre["origem"] = pd.to_datetime(t.drop_duplicates("k").set_index("k")["origem"])
        escolhidas = origens(abre, SO_DEZEMBRO[cenario])
        fora = abre[
            (abre["origem"] >= pd.Timestamp("2017-01-01")) & ~abre.index.isin(escolhidas.index)
        ]
        if SO_DEZEMBRO[cenario]:
            fora = fora[fora["origem"].dt.month == 12]
        for _, x in fora.iterrows():
            excluidas.append(
                (
                    cenario,
                    lingua,
                    x["origem"].date().isoformat(),
                    "ABRE indefinido em: " + ", ".join(m for m in INTERNOS if pd.isna(x[m])),
                )
            )
        for k in escolhidas.index:
            for interno in INTERNOS:
                x = t[(t["k"] == k) & (t["metodo"] == interno)].iloc[0]
                if (
                    pd.isna(x["previsto"])
                    or pd.isna(x["real"])
                    or x["previsto"] <= 0
                    or x["real"] <= 0
                ):
                    sys.exit(
                        f"par faltando: {lingua} {cenario} origem {x['origem']} método {interno}: previsto {x['previsto']}, real {x['real']}"
                    )
                p, r = float(x["previsto"]), float(x["real"])
                linhas.append(
                    {
                        "linguagem": lingua,
                        "cenario": cenario,
                        "origem": x["origem"],
                        "metodo": METODOS[interno],
                        "nome_interno": interno,
                        "previsto": p,
                        "real": r,
                        "abre": abs(p - r) / min(p, r),
                        "mre": abs(p - r) / r,
                        "mer": abs(p - r) / p,
                        "erro_abs": abs(p - r),
                    }
                )
medidas = pd.DataFrame(linhas)
medidas.to_csv(SAIDA / "medidas_por_origem.csv", index=False, float_format="%.10g")
pd.DataFrame(excluidas, columns=["cenario", "linguagem", "origem", "motivo"]).to_csv(
    SAIDA / "origens_fora.csv", index=False
)

# conferência: o ABRE recalculado dos pares bate com o `abre` salvo
for (lingua, cenario), grupo in medidas.groupby(["linguagem", "cenario"]):
    t = le_pares(cenario, lingua)
    salvo = t.set_index(["origem", "metodo"])["abre"]
    maior = 0.0
    for _, x in grupo.iterrows():
        maior = max(maior, abs(salvo.loc[(x["origem"], x["nome_interno"])] - x["abre"]))
    assert maior < 1e-8, f"{lingua} {cenario}: o ABRE dos pares difere do salvo em {maior}"


def selecao(cenario: str, so_dezembro: bool, lingua: str) -> pd.DataFrame:
    s = medidas[(medidas["cenario"] == cenario) & (medidas["linguagem"] == lingua)]
    if cenario == "S5" and so_dezembro:
        s = s[pd.to_datetime(s["origem"]).dt.month == 12]
    return s


# 2. Caixas por cenário, uma linha por linguagem
for cenario, nome_cenario in NOME_DO_CENARIO.items():
    fig, eixos = plt.subplots(
        len(LINGUAS), 1, figsize=(7.2, 9.2), sharex=True, constrained_layout=True
    )
    gerador = np.random.default_rng(0)
    for eixo, lingua in zip(eixos, LINGUAS, strict=True):
        s = selecao(cenario, False, lingua)
        n_origens = s["origem"].nunique()
        for i, metodo in enumerate(NOME_DO_METODO):
            v = s[s["metodo"] == metodo].sort_values("origem")["abre"].to_numpy()
            caixa = eixo.boxplot(
                v,
                positions=[i],
                widths=0.5,
                showfliers=False,
                patch_artist=True,
                medianprops={"color": "black", "linewidth": 1.8},
                whiskerprops={"color": "#555555"},
                capprops={"color": "#555555"},
                boxprops={"edgecolor": "#555555"},
            )
            caixa["boxes"][0].set_facecolor(COR[metodo])
            caixa["boxes"][0].set_alpha(0.35)
            eixo.scatter(
                i + gerador.uniform(-0.17, 0.17, len(v)),
                v,
                s=9,
                color=COR[metodo],
                edgecolor="none",
                alpha=0.9,
                zorder=3,
            )
            eixo.scatter(
                [i],
                [v.mean()],
                marker="D",
                s=26,
                color="white",
                edgecolor="black",
                linewidth=1.0,
                zorder=4,
            )
        eixo.set_title(f"{NOMES[lingua]} ({n_origens} origens)", loc="left", fontsize=8)
        eixo.set_ylabel("ABRE")
        eixo.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: dec(v, 2)))
        eixo.set_ylim(bottom=0)
    eixos[-1].set_xticks(range(len(NOME_DO_METODO)))
    eixos[-1].set_xticklabels(NOME_DO_METODO)
    fig.suptitle(
        f"Cenário {nome_cenario}: ABRE por método (cada ponto é uma origem; losango = média; traço = mediana)",
        fontsize=8.5,
    )
    fig.savefig(SAIDA / f"caixas_{cenario}.pdf")
    plt.close(fig)

# 3. Diferenças pareadas de ABRE contra a Ingênua: histograma, Q-Q e Shapiro-Wilk
shapiro_linhas = []
for cenario, nome_cenario in NOME_DO_CENARIO.items():
    figuras = {}
    for tipo in ("hist", "qq"):
        figuras[tipo] = plt.subplots(
            len(LINGUAS), len(CONTRA_A_INGENUA), figsize=(7.2, 8.6), constrained_layout=True
        )
    for linha, lingua in enumerate(LINGUAS):
        s = selecao(cenario, False, lingua)
        base = s[s["metodo"] == "Ingênua"].set_index("origem")["abre"]
        for coluna, metodo in enumerate(CONTRA_A_INGENUA):
            outro = s[s["metodo"] == metodo].set_index("origem")["abre"]
            d = (outro - base).dropna().to_numpy()
            if len(d) >= 3 and np.ptp(d) > 0:
                w, p = shapiro(d)
            else:
                w, p = np.nan, np.nan
            shapiro_linhas.append(
                {
                    "cenario": cenario,
                    "linguagem": lingua,
                    "metodo": metodo,
                    "n": len(d),
                    "W": w,
                    "p": p,
                    "media_da_diferenca": d.mean(),
                    "mediana_da_diferenca": float(np.median(d)),
                }
            )
            rotulo = f"{metodo}\nShapiro-Wilk p = {dec(p, 3)} (n = {len(d)})"
            eixo = figuras["hist"][1][linha, coluna]
            eixo.hist(
                d, bins=min(8, max(3, len(d) // 2)), color=COR[metodo], alpha=0.6, edgecolor="white"
            )
            eixo.axvline(0, color="black", linewidth=0.8)
            eixo.set_title(rotulo, fontsize=6.5)
            eixo.tick_params(labelsize=6)
            if coluna == 0:
                eixo.set_ylabel(f"{NOMES[lingua]}\norigens", fontsize=7)
            eixo = figuras["qq"][1][linha, coluna]
            probplot(d, dist="norm", plot=eixo)
            eixo.get_lines()[0].set(color=COR[metodo], markersize=3)
            eixo.get_lines()[1].set(color="black", linewidth=0.8)
            eixo.set_title(rotulo, fontsize=6.5)
            eixo.set_xlabel("")
            eixo.tick_params(labelsize=6)
            if coluna == 0:
                eixo.set_ylabel(f"{NOMES[lingua]}\ndiferença de ABRE", fontsize=7)
            else:
                eixo.set_ylabel("")
    figuras["hist"][0].suptitle(
        f"Cenário {nome_cenario}: histograma de (ABRE do método menos ABRE da Ingênua) por origem",
        fontsize=8,
    )
    figuras["qq"][0].suptitle(
        f"Cenário {nome_cenario}: Q-Q normal de (ABRE do método menos ABRE da Ingênua) por origem",
        fontsize=8,
    )
    figuras["hist"][0].savefig(SAIDA / f"histogramas_{cenario}.pdf")
    figuras["qq"][0].savefig(SAIDA / f"qq_{cenario}.pdf")
    plt.close(figuras["hist"][0])
    plt.close(figuras["qq"][0])
shapiro_tabela = pd.DataFrame(shapiro_linhas)
shapiro_tabela.to_csv(SAIDA / "shapiro_wilk.csv", index=False, float_format="%.6g")
T = [
    "# Shapiro-Wilk das diferenças pareadas de ABRE contra a Ingênua",
    "",
    "Diferença = ABRE do método menos ABRE da Ingênua, por origem. Hipótese nula: as diferenças vêm de uma distribuição normal. O Wilcoxon não exige normalidade, então o teste serve só para descrever.",
    "",
    "Aviso: com 7 origens (cenários só de dezembro, 4 em Elixir) o Shapiro-Wilk tem pouco poder e quase nunca rejeita. p alto com n pequeno não mostra normalidade. Nos cenários com todos os trimestres, origens vizinhas são dependentes.",
    "",
    "| Cenário | Linguagem | Método | n | W | p | Rejeita a 0,05? |",
    "|---|---|---|---|---|---|---|",
]
for _, x in shapiro_tabela.iterrows():
    rejeita = "n/d" if pd.isna(x["p"]) else ("sim" if x["p"] < 0.05 else "não")
    T.append(
        f"| {NOME_DO_CENARIO[x['cenario']]} | {NOMES[x['linguagem']]} | {x['metodo']} | {x['n']} | {dec(x['W'])} | {dec(x['p'], 3)} | {rejeita} |"
    )
resumo = (
    shapiro_tabela.assign(rejeita=shapiro_tabela["p"] < 0.05)
    .groupby("cenario")
    .agg(testes=("p", "count"), rejeitados=("rejeita", "sum"), n_minimo=("n", "min"))
)
T += [
    "",
    "## Quantos testes rejeitam, por cenário",
    "",
    "| Cenário | Testes | Rejeitam a 0,05 | Menor n |",
    "|---|---|---|---|",
]
for cenario, nome_cenario in NOME_DO_CENARIO.items():
    x = resumo.loc[cenario]
    T.append(
        f"| {nome_cenario} | {int(x['testes'])} | {int(x['rejeitados'])} | {int(x['n_minimo'])} |"
    )
(SAIDA / "shapiro_wilk.md").write_text("\n".join(T) + "\n", encoding="utf-8")

# 4. Média e mediana de cada medida por linguagem, método e cenário
linhas_resumo = []
for lingua in LINGUAS:
    for cenario, so_dezembro in COLUNAS_TABELA:
        s = selecao(cenario, so_dezembro, lingua)
        nome_coluna = (
            f"{NOME_DO_CENARIO[cenario]} (dezembro)"
            if cenario == "S5" and so_dezembro
            else NOME_DO_CENARIO[cenario]
        )
        for metodo in NOME_DO_METODO:
            v = s[s["metodo"] == metodo]
            registro = {
                "linguagem": lingua,
                "cenario": nome_coluna,
                "metodo": metodo,
                "origens": len(v),
            }
            for chave in MEDIDAS:
                registro[f"{chave}_media"] = v[chave].mean()
                registro[f"{chave}_mediana"] = v[chave].median()
            linhas_resumo.append(registro)
resumo_medidas = pd.DataFrame(linhas_resumo)
resumo_medidas.to_csv(SAIDA / "medidas_por_cenario.csv", index=False, float_format="%.10g")
nomes_das_colunas = [
    f"{NOME_DO_CENARIO[c]} (dezembro)" if c == "S5" and d else NOME_DO_CENARIO[c]
    for c, d in COLUNAS_TABELA
]
M = [
    "# Média / mediana de cada medida de erro por linguagem, método e cenário",
    "",
    "ABRE = |P − R| / min(P, R). MRE = |P − R| / R. MER = |P − R| / P. Erro absoluto = |P − R| em pessoas. P é o previsto e R o real. Menor é melhor em todas. Cada célula traz média / mediana sobre as origens do cenário (as mesmas das tabelas de ABRE).",
    "",
]
for chave, rotulo in MEDIDAS.items():
    M += [f"## {rotulo}", ""]
    for lingua in LINGUAS:
        M += [
            f"### {NOMES[lingua]}",
            "",
            "| Método | " + " | ".join(nomes_das_colunas) + " |",
            "|---|" + "---|" * len(nomes_das_colunas),
        ]
        for metodo in NOME_DO_METODO:
            celulas = []
            for nome_coluna in nomes_das_colunas:
                x = resumo_medidas[
                    (resumo_medidas["linguagem"] == lingua)
                    & (resumo_medidas["cenario"] == nome_coluna)
                    & (resumo_medidas["metodo"] == metodo)
                ].iloc[0]
                formato = milhar if chave == "erro_abs" else dec
                celulas.append(f"{formato(x[f'{chave}_media'])} / {formato(x[f'{chave}_mediana'])}")
            M.append(f"| {metodo} | " + " | ".join(celulas) + " |")
        M.append("")
(SAIDA / "medidas_por_cenario.md").write_text("\n".join(M) + "\n", encoding="utf-8")

# 5. A ordem dos métodos muda com a medida?
ORDEM = [
    "# Ordem dos métodos por medida (do menor para o maior erro médio)",
    "",
    "A coluna `ABRE` é a referência. Cada outra coluna traz a ordem e, entre parênteses, `igual` ou `muda` em relação à do ABRE. Em seguida vem a mesma conta pela mediana.",
    "",
]
contagem_muda = {
    "media": {c: 0 for c in MEDIDAS if c != "abre"},
    "mediana": {c: 0 for c in MEDIDAS if c != "abre"},
}
total_de_celulas = 0
for estatistica, titulo in (("media", "Pela média"), ("mediana", "Pela mediana")):
    ORDEM += [
        f"## {titulo}",
        "",
        "| Linguagem | Cenário | " + " | ".join(MEDIDAS.values()) + " |",
        "|---|---|" + "---|" * len(MEDIDAS),
    ]
    for lingua in LINGUAS:
        for nome_coluna in nomes_das_colunas:
            s = resumo_medidas[
                (resumo_medidas["linguagem"] == lingua) & (resumo_medidas["cenario"] == nome_coluna)
            ]
            ordens = {
                chave: list(s.sort_values(f"{chave}_{estatistica}")["metodo"]) for chave in MEDIDAS
            }
            celulas = []
            for chave in MEDIDAS:
                texto = " < ".join(ordens[chave])
                if chave != "abre":
                    igual = ordens[chave] == ordens["abre"]
                    texto += " (igual)" if igual else " (muda)"
                    if not igual:
                        contagem_muda[estatistica][chave] += 1
                celulas.append(texto)
            ORDEM.append(f"| {NOMES[lingua]} | {nome_coluna} | " + " | ".join(celulas) + " |")
            if estatistica == "media":
                total_de_celulas += 1
    ORDEM.append("")
ORDEM += [
    "## Quantas ordens mudam em relação ao ABRE",
    "",
    f"Total de combinações de linguagem e cenário: {total_de_celulas}.",
    "",
    "| Medida | Muda pela média | Muda pela mediana |",
    "|---|---|---|",
]
for chave in contagem_muda["media"]:
    ORDEM.append(
        f"| {MEDIDAS[chave]} | {contagem_muda['media'][chave]} | {contagem_muda['mediana'][chave]} |"
    )
(SAIDA / "ordem_dos_metodos.md").write_text("\n".join(ORDEM) + "\n", encoding="utf-8")

# 6. Leia-me
LEIA = [
    "# Leia-me: distribuição dos erros de projeção",
    "",
    "Nenhuma projeção foi recalculada. Tudo vem dos pares previsto e real por origem de `projecao-cenarios-v3b/unidades/`, nas mesmas origens das tabelas de ABRE. O ABRE recalculado dos pares bate com o salvo (diferença abaixo de 1e-8).",
    "",
    "## Métodos do artigo e nome interno nos arquivos",
    "",
    "| Nome no artigo | Nome interno em `pares` |",
    "|---|---|",
]
for interno, nome in METODOS.items():
    LEIA.append(f"| {nome} | `{interno}` |")
LEIA += [
    "",
    "Os nomes internos terminam em `R0` (sem previsão de repositórios) ou `R3` (com previsão de repositórios e saída por parada). A Coorte é a `coorte_R0`, que é a coorte V0.",
    "",
    "## Cenários",
    "",
    "| Nome | Arquivos | Origens usadas |",
    "|---|---|---|",
]
for cenario, nome in NOME_DO_CENARIO.items():
    origem_txt = (
        "dezembro de 2017 em diante" if SO_DEZEMBRO[cenario] else "todo trimestre de 2017 em diante"
    )
    LEIA.append(f"| {nome} | `*_{cenario}_*` | {origem_txt} |")
LEIA += [
    "",
    "Nos nomes de arquivo `S1` é Curto e amplo, `S3h` é Longo e amplo, `S4` é Longo, não casuais, `S5` é Curto, não casuais e `S2` é Anual. As figuras usam esses mesmos códigos no sufixo. Origens em que algum dos cinco métodos fica sem ABRE definido ficam fora e estão listadas em `origens_fora.csv`.",
    "",
    "## Medidas",
    "",
    "- ABRE: |P − R| / min(P, R). Pune igual errar para cima e para baixo.",
    "- MRE: |P − R| / R (erro relativo ao real).",
    "- MER: |P − R| / P (erro relativo ao previsto).",
    "- Erro absoluto: |P − R| em pessoas.",
    "",
    "## Arquivos",
    "",
    "- `caixas_<cenário>.pdf`: uma figura por cenário, uma linha por linguagem. Pontos são as origens, a caixa é o intervalo interquartil, o traço preto é a mediana e o losango branco é a média.",
    "- `histogramas_<cenário>.pdf` e `qq_<cenário>.pdf`: diferença de ABRE de cada método contra a Ingênua por origem (a que o Wilcoxon testa). Uma linha por linguagem, uma coluna por método. O título de cada painel traz o p do Shapiro-Wilk.",
    "- `shapiro_wilk.md` e `.csv`: Shapiro-Wilk de todas as diferenças. Com 7 origens (4 em Elixir) o teste quase nunca rejeita, então p alto não mostra normalidade.",
    "- `medidas_por_cenario.md` e `.csv`: média e mediana de ABRE, MRE, MER e erro absoluto.",
    "- `ordem_dos_metodos.md`: a ordem dos métodos em cada medida e se ela muda em relação ao ABRE.",
    "- `medidas_por_origem.csv`: base de tudo, uma linha por linguagem, cenário, origem e método.",
    "",
    "Os pares do Curto, não casuais com todos os trimestres são dependentes entre si (a janela do alvo compartilha 9 dos 12 meses), assim como os dos cenários trimestrais amplos. Zig fica fora porque não entra na RQ3.",
]
(SAIDA / "LEIA-ME.md").write_text("\n".join(LEIA) + "\n", encoding="utf-8")
print("\n".join(ORDEM[-12:]))
print(f"origens fora: {len(excluidas)}; linhas: {len(medidas)}")
print("\n".join(T[-9:]))
