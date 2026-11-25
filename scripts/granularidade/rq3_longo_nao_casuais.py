"""RQ3 com o cenário Longo, não casuais em todo trimestre (`projecao-longo-nao-casuais/hipoteses.md`). Sem projeção nova além do `cenarios.py --cenarios S4`.

Lê `<novas>/<l>_S4_pares.csv.gz`, `_R1..R3_pares.csv.gz` e `_detalhe.csv.gz`. Origens: todo fim de trimestre, da primeira em que os cinco métodos têm ABRE definido até 31/12/2023.
Confere que as previsões de dezembro são as do cálculo anterior (`<antigas>`). Grava em `<saida>`: `pares_por_origem.csv`, `erros_por_origem.csv`, `origens.md`, `tabela_abre.md` e `.tex`,
`wilcoxon.md` e `.csv`, `cobertura.md` e `.tex`, `faixa_2024_clojure.md` e `numeros_rq3.md` (cada número da seção RQ3 do artigo, antes e depois).
O código das tabelas de cobertura é validado contra a tabela do artigo com as origens do cenário Anual.

Uso (na raiz do repo): uv run --no-project --with pandas --with numpy --with scipy python scripts/granularidade/rq3_longo_nao_casuais.py <novas unidades> <antigas unidades> <saida> [<unidades do Anual>]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

NOVAS, ANTIGAS, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
ANUAL = Path(sys.argv[4]) if len(sys.argv) > 4 else None
SAIDA.mkdir(parents=True, exist_ok=True)
LINGUAS = ["clojure", "elixir", "ocaml", "python"]
NOMES = {"clojure": "Clojure", "elixir": "Elixir", "ocaml": "OCaml", "python": "Python"}
METODOS = {
    "ingenua": "Ingênua",
    "coorte_R0": "Coorte",
    "coorte_R3": "Coorte^R",
    "conservador_R3": "Conservador^R",
    "C3_R3": "Ingênua-Coorte^R",
}
SEM = ("pessimista_R0", "otimista_R0")  # sem previsão de repositórios
COM = ("pessimista_nova_R3", "otimista_nova_R3")  # com previsão de repositórios (regra nova)
CENARIO = "Longo, não casuais (todo trimestre)"
FIM_ULTIMA_ORIGEM = pd.Timestamp("2023-12-31")


def dec(x: float, casas: int = 3) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def p_texto(p: float) -> str:
    if pd.isna(p):
        return "n/d"
    return f"{p:.1e}".replace(".", ",") if p < 0.001 else dec(p, 3)


def le_pares(pasta: Path, codigo: str, lingua: str) -> pd.DataFrame:
    partes = []
    for sufixo in ("", "_R1", "_R2", "_R3"):
        caminho = pasta / f"{lingua}_{codigo}{sufixo}_pares.csv.gz"
        if not caminho.exists():
            sys.exit(f"falta o arquivo {caminho}")
        partes.append(pd.read_csv(caminho))
    t = pd.concat(partes, ignore_index=True).drop_duplicates(["k", "metodo"])
    t["origem"] = pd.to_datetime(t["origem"])
    return t


def escolhe_origens(
    t: pd.DataFrame,
    piso: pd.Timestamp | None,
    so_dezembro: bool = False,
    teto: pd.Timestamp | None = None,
) -> list[int]:
    """Origens em que os cinco métodos têm ABRE definido (e, se pedido, só dezembro, a partir de `piso`)."""
    abre = t[t["metodo"].isin(METODOS)].pivot(index="k", columns="metodo", values="abre")[
        list(METODOS)
    ]
    origem = t.drop_duplicates("k").set_index("k")["origem"]
    boa = abre.notna().all(axis=1)
    if piso is not None:
        boa &= origem.reindex(abre.index) >= piso
    if so_dezembro:
        boa &= origem.reindex(abre.index).dt.month == 12
    if teto is not None:
        boa &= origem.reindex(abre.index) <= teto
    return list(abre.index[boa])


# 1. Carrega, confere contra o cálculo anterior e escolhe as origens
dados = {}
origens_por_lingua = {}
origens_com_piso = {}
for lingua in LINGUAS:
    t = le_pares(NOVAS, "S4", lingua)
    antigo = le_pares(ANTIGAS, "S4", lingua).set_index(["k", "metodo"])["previsto"]
    novo = t.set_index(["k", "metodo"])["previsto"]
    comuns = novo.index.intersection(antigo.index)
    if len(comuns) == 0:
        sys.exit(f"{lingua}: nenhuma previsão em comum com o cálculo anterior")
    a, b = novo.loc[comuns].to_numpy(), antigo.loc[comuns].to_numpy()
    iguais = (np.isnan(a) & np.isnan(b)) | (np.abs(a - b) <= 1e-8 * np.maximum(1.0, np.abs(b)))
    if not iguais.all():
        sys.exit(
            f"{lingua}: o cálculo novo difere do anterior em {int((~iguais).sum())} de {len(comuns)} previsões, por exemplo {comuns[~iguais][:3].tolist()}"
        )
    dados[lingua] = t
    origens_por_lingua[lingua] = escolhe_origens(t, None, teto=FIM_ULTIMA_ORIGEM)
    origens_com_piso[lingua] = escolhe_origens(
        t, pd.Timestamp("2017-01-01"), teto=FIM_ULTIMA_ORIGEM
    )
    assert t["origem"].max() == FIM_ULTIMA_ORIGEM, (
        f"{lingua}: a última origem é {t['origem'].max()} e não 31/12/2023"
    )
    assert (t[t["k"].isin(origens_por_lingua[lingua])]["origem"].dt.is_quarter_end).all(), (
        f"{lingua}: origem fora de fim de trimestre"
    )

# 2. Pares e erros por origem
pares_linhas, erros = [], []
for lingua in LINGUAS:
    t = dados[lingua]
    escolhidas = t[t["k"].isin(origens_por_lingua[lingua])]
    for _, x in escolhidas.iterrows():
        pares_linhas.append(
            {
                "linguagem": lingua,
                "origem": x["origem"].date().isoformat(),
                "k": x["k"],
                "metodo": x["metodo"],
                "previsto": x["previsto"],
                "real": x["real"],
                "abre": x["abre"],
            }
        )
        if x["metodo"] in METODOS:
            p, r = float(x["previsto"]), float(x["real"])
            erros.append(
                {
                    "cenario": CENARIO,
                    "linguagem": lingua,
                    "origem": x["origem"].date().isoformat(),
                    "metodo": METODOS[x["metodo"]],
                    "previsto": p,
                    "real": r,
                    "sinal": 100 * (p - r) / r,
                    "abre": abs(p - r) / min(p, r),
                    "erro_pessoas": abs(p - r),
                }
            )
pd.DataFrame(pares_linhas).sort_values(["linguagem", "k", "metodo"]).to_csv(
    SAIDA / "pares_por_origem.csv", index=False, float_format="%.10g"
)
erros = pd.DataFrame(erros)
erros.to_csv(SAIDA / "erros_por_origem.csv", index=False, float_format="%.10g")

# 3. Origens
ORIGENS = [
    f"# Origens do cenário {CENARIO}",
    "",
    "Todo fim de trimestre, da primeira origem com os cinco métodos projetando até 31/12/2023 (alvo até 31/12/2024).",
    "",
    "| Linguagem | Origens | Primeira | Última | Origens com piso de 2017 | Primeira com piso |",
    "|---|---|---|---|---|---|",
]
for lingua in LINGUAS:
    t = dados[lingua].drop_duplicates("k").set_index("k")["origem"]
    ks, kp = origens_por_lingua[lingua], origens_com_piso[lingua]
    ORIGENS.append(
        f"| {NOMES[lingua]} | {len(ks)} | {t.loc[ks].min().date()} | {t.loc[ks].max().date()} | {len(kp)} | {t.loc[kp].min().date()} |"
    )
ORIGENS.append("")
(SAIDA / "origens.md").write_text("\n".join(ORIGENS) + "\n", encoding="utf-8")


# 4. Tabela de ABRE no formato do artigo
def tabela_abre(escolha: dict, titulo: str, arquivo: str) -> dict:
    medias, medianas = {}, {}
    for lingua in LINGUAS:
        e = (
            erros[erros["linguagem"] == lingua]
            if escolha is None
            else erros[(erros["linguagem"] == lingua) & erros["origem"].isin(escolha[lingua])]
        )
        for metodo in METODOS.values():
            v = e[e["metodo"] == metodo]["abre"]
            medias[(metodo, lingua)], medianas[(metodo, lingua)] = v.mean(), v.median()
    T = [
        f"# {titulo}",
        "",
        "ABRE médio e mediano. Em negrito, o menor valor de cada coluna.",
        "",
        "| Método | "
        + " | ".join(f"{NOMES[x]} (média)" for x in LINGUAS)
        + " | "
        + " | ".join(f"{NOMES[x]} (mediana)" for x in LINGUAS)
        + " |",
        "|---|" + "---|" * 8,
    ]
    menor = {
        (lingua, tipo): min(
            (medias if tipo == "m" else medianas)[(m, lingua)] for m in METODOS.values()
        )
        for lingua in LINGUAS
        for tipo in ("m", "d")
    }
    linhas_tex = []
    for metodo in METODOS.values():
        celulas, celulas_tex = [], []
        for tipo, tabela in (("m", medias), ("d", medianas)):
            for lingua in LINGUAS:
                valor = tabela[(metodo, lingua)]
                texto = dec(valor)
                negrito = abs(valor - menor[(lingua, tipo)]) < 1e-12
                celulas.append(f"**{texto}**" if negrito else texto)
                celulas_tex.append(f"\\textbf{{{texto}}}" if negrito else texto)
        T.append(f"| {metodo} | " + " | ".join(celulas) + " |")
        nome_tex = metodo.replace("^R", "$^R$")
        linhas_tex.append(f"{nome_tex} & " + " & ".join(celulas_tex) + " \\\\")
    T.append("")
    (SAIDA / f"{arquivo}.md").write_text("\n".join(T) + "\n", encoding="utf-8")
    tex = [
        "\\begin{tabular}{l|cccc|cccc}",
        "\\hline",
        " & \\multicolumn{4}{c|}{\\textbf{Média}} & \\multicolumn{4}{c}{\\textbf{Mediana}} \\\\",
        "\\textbf{Método} & Clojure & Elixir & OCaml & Python & Clojure & Elixir & OCaml & Python \\\\",
        "\\hline",
        linhas_tex[0],
        linhas_tex[1],
        "\\hline",
        *linhas_tex[2:],
        "\\hline",
        "\\end{tabular}",
    ]
    (SAIDA / f"{arquivo}.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
    return {"medias": medias, "medianas": medianas}


abre = tabela_abre(None, f"ABRE do cenário {CENARIO}", "tabela_abre")
com_piso = {
    lingua: {
        dados[lingua].drop_duplicates("k").set_index("k").loc[k, "origem"].date().isoformat()
        for k in origens_com_piso[lingua]
    }
    for lingua in LINGUAS
}
abre_piso = tabela_abre(
    com_piso, f"ABRE do cenário {CENARIO}, só com origens a partir de 2017", "tabela_abre_piso_2017"
)

# 5. Wilcoxon pareado (exato, bicaudal) contra a Ingênua e contra a Coorte


def wilcoxon_pareado(a: pd.Series, b: pd.Series) -> dict:
    diferenca = a.to_numpy() - b.to_numpy()
    n_dif = int((diferenca != 0).sum())
    if n_dif == 0:
        return {"pares": len(a), "com_diferenca": 0, "p": float("nan"), "vitorias": 0}
    try:
        p = float(wilcoxon(a.to_numpy(), b.to_numpy(), method="exact").pvalue)
    except ValueError:
        p = float(wilcoxon(a.to_numpy(), b.to_numpy()).pvalue)
    return {"pares": len(a), "com_diferenca": n_dif, "p": p, "vitorias": int((diferenca < 0).sum())}


testes = []
for lingua in LINGUAS:
    e = erros[erros["linguagem"] == lingua].pivot(index="origem", columns="metodo", values="abre")
    comparacoes = [(m, b) for m in METODOS.values() for b in ("Ingênua", "Coorte") if m != b] + [
        ("Ingênua-Coorte^R", "Coorte^R")
    ]
    for metodo, base in comparacoes:
        testes.append(
            {
                "linguagem": lingua,
                "metodo": metodo,
                "contra": base,
                **wilcoxon_pareado(e[metodo], e[base]),
            }
        )
testes = pd.DataFrame(testes)
testes.to_csv(SAIDA / "wilcoxon.csv", index=False)
W = [
    f"# Wilcoxon pareado do cenário {CENARIO}",
    "",
    "Wilcoxon pareado bicaudal exato sobre o ABRE, sem correção para comparações múltiplas. Vitórias: origens em que o método errou menos que a base.",
    "",
    "Aviso: origens vizinhas compartilham 9 dos 12 meses do alvo, então os pares não são independentes e o p só descreve.",
    "",
    "| Linguagem | Método | Contra | Pares | p | Vitórias |",
    "|---|---|---|---|---|---|",
]
for _, x in testes.iterrows():
    W.append(
        f"| {NOMES[x['linguagem']]} | {x['metodo']} | {x['contra']} | {x['pares']} ({x['com_diferenca']}) | {p_texto(x['p'])} | {x['vitorias']} de {x['pares']} |"
    )
W.append("")
(SAIDA / "wilcoxon.md").write_text("\n".join(W) + "\n", encoding="utf-8")


# 6. Cobertura do intervalo pessimista a otimista
def cobertura(pares_da_lingua: pd.DataFrame, ks: list[int], limites: tuple[str, str]) -> dict:
    t = pares_da_lingua[pares_da_lingua["k"].isin(ks)]
    p = t.pivot(index="k", columns="metodo", values="previsto")
    real = t.drop_duplicates("k").set_index("k")["real"]
    pess, otim = p[limites[0]], p[limites[1]]
    if pess.isna().any() or otim.isna().any():
        sys.exit(f"intervalo {limites} indefinido em {list(pess.index[pess.isna() | otim.isna()])}")
    dentro = (pess <= real) & (real <= otim)
    largura = (otim - pess) / p["ingenua"]
    return {"n": len(ks), "dentro": int(dentro.sum()), "largura_mediana": float(largura.median())}


def tabela_cobertura(origens: dict, fonte: dict, titulo: str, arquivo: str) -> dict:
    resultado = {}
    T = [
        f"# {titulo}",
        "",
        "Anos (origens) em que o real fica dentro do intervalo pessimista a otimista, limites incluídos, e largura relativa mediana (otimista menos pessimista, dividido pela projeção da Ingênua).",
        "",
        "| Linguagem | Origens dentro, sem | Origens dentro, com | Largura mediana, sem | Largura mediana, com |",
        "|---|---|---|---|---|",
    ]
    tex = [
        "\\begin{tabular}{l|cc|cc}",
        "\\hline",
        " & \\multicolumn{2}{c|}{\\textbf{Dentro}} & \\multicolumn{2}{c}{\\textbf{Largura mediana}} \\\\",
        "\\textbf{Linguagem} & Sem & Com & Sem & Com \\\\",
        "\\hline",
    ]
    for lingua in LINGUAS:
        s, c = (
            cobertura(fonte[lingua], origens[lingua], SEM),
            cobertura(fonte[lingua], origens[lingua], COM),
        )
        resultado[lingua] = (s, c)
        T.append(
            f"| {NOMES[lingua]} | {s['dentro']} de {s['n']} | {c['dentro']} de {c['n']} | {dec(s['largura_mediana'])} | {dec(c['largura_mediana'])} |"
        )
        tex.append(
            f"{NOMES[lingua]} & {s['dentro']} de {s['n']} & {c['dentro']} de {c['n']} & {dec(s['largura_mediana'])} & {dec(c['largura_mediana'])} \\\\"
        )
    tex += ["\\hline", "\\end{tabular}"]
    T.append("")
    (SAIDA / f"{arquivo}.md").write_text("\n".join(T) + "\n", encoding="utf-8")
    (SAIDA / f"{arquivo}.tex").write_text("\n".join(tex) + "\n", encoding="utf-8")
    return resultado


cob = tabela_cobertura(origens_por_lingua, dados, f"Cobertura do cenário {CENARIO}", "cobertura")

# Validação do código da cobertura: o cenário Anual (origens de dezembro de 2017 a 2023) tem de dar a tabela do artigo
ARTIGO_COBERTURA = {
    "clojure": (4, 7, 7, 7, 0.305, 0.373),
    "elixir": (4, 4, 4, 4, 0.193, 0.353),
    "ocaml": (5, 7, 7, 7, 0.277, 0.361),
    "python": (4, 7, 6, 7, 0.238, 0.343),
}
if ANUAL is not None:
    validacao = ["# Validação da cobertura contra a tabela do artigo (cenário Anual)", ""]
    for lingua in LINGUAS:
        t = le_pares(ANUAL, "S2", lingua)
        ks = escolhe_origens(t, pd.Timestamp("2017-01-01"), so_dezembro=True)
        s, c = cobertura(t, ks, SEM), cobertura(t, ks, COM)
        esperado = ARTIGO_COBERTURA[lingua]
        calculado = (
            s["dentro"],
            s["n"],
            c["dentro"],
            c["n"],
            round(s["largura_mediana"], 3),
            round(c["largura_mediana"], 3),
        )
        validacao.append(f"- {NOMES[lingua]}: artigo {esperado}, calculado {calculado}")
        if (
            esperado[:4] != calculado[:4]
            or abs(esperado[4] - calculado[4]) > 0.0015
            or abs(esperado[5] - calculado[5]) > 0.0015
        ):
            sys.exit(
                f"a cobertura do Anual de {lingua} não reproduz o artigo: {esperado} contra {calculado}"
            )
    (SAIDA / "validacao_cobertura.md").write_text("\n".join(validacao) + "\n", encoding="utf-8")

# 7. Faixa de 2024 de Clojure: origem 31/12/2023, alvo 31/12/2024, faixa de 0 a 12 meses (quatro faixas de 3 meses)
detalhe = pd.read_csv(NOVAS / "clojure_S4_detalhe.csv.gz")
d = detalhe[(detalhe["origem"] == "2023-12-31") & (detalhe["faixa"].between(0, 3))]
faixa_2024 = d.groupby("metodo")[["projecao_faixa", "real_faixa"]].sum()
populacao_2024 = float(
    detalhe[(detalhe["origem"] == "2023-12-31") & (detalhe["metodo"] == "Ingênua")][
        "real_faixa"
    ].sum()
)
F = [
    "# Faixa de 0 a 12 meses de Clojure em 2024 (origem 31/12/2023)",
    "",
    f"Real em 31/12/2024: {milhar(faixa_2024['real_faixa'].iloc[0])} pessoas de 0 a 12 meses (as quatro primeiras faixas de 3 meses) e {milhar(populacao_2024)} no total.",
    "",
    "| Método | Projeção da faixa de 0 a 12 meses |",
    "|---|---|",
]
for metodo in METODOS.values():
    F.append(f"| {metodo} | {milhar(faixa_2024.loc[metodo, 'projecao_faixa'])} |")
F.append("")
(SAIDA / "faixa_2024_clojure.md").write_text("\n".join(F) + "\n", encoding="utf-8")

# 8. numeros_rq3.md: cada número da seção RQ3 do artigo, antes e depois
ARTIGO_ABRE = {  # (média Clojure, Elixir, OCaml, Python, mediana Clojure, Elixir, OCaml, Python)
    "Ingênua": (0.086, 0.025, 0.060, 0.164, 0.076, 0.013, 0.019, 0.195),
    "Coorte": (0.081, 0.037, 0.073, 0.076, 0.060, 0.032, 0.044, 0.049),
    "Coorte^R": (0.068, 0.041, 0.066, 0.061, 0.081, 0.035, 0.049, 0.049),
    "Conservador^R": (0.077, 0.038, 0.060, 0.055, 0.080, 0.036, 0.056, 0.044),
    "Ingênua-Coorte^R": (0.076, 0.026, 0.060, 0.075, 0.078, 0.014, 0.046, 0.061),
}
N = [
    f"# Números da seção RQ3 do artigo com o cenário {CENARIO}",
    "",
    "Antes: valores do artigo (cenário Anual, recortes de 12 meses, 7 origens). Depois: este cenário (recortes trimestrais, horizonte de 12 meses, mesmas regras de população e idade). Os valores de p descrevem: origens vizinhas compartilham 9 dos 12 meses do alvo.",
    "",
    "## Origens (parágrafo do método)",
    "",
    "| Onde aparece | Antes | Depois |",
    "|---|---|---|",
    '| "Avaliamos as projeções que partem do fim de cada ano de 2017 a 2023" (7 origens) | 7 origens por linguagem | '
    + "; ".join(f"{NOMES[x]} {len(origens_por_lingua[x])}" for x in LINGUAS)
    + " origens, todo trimestre até 31/12/2023 |",
    '| "Em Elixir, as projeções partem de 2020 a 2023" | 2020 a 2023 | primeira origem de Elixir: '
    + str(
        dados["elixir"]
        .drop_duplicates("k")
        .set_index("k")["origem"]
        .loc[origens_por_lingua["elixir"]]
        .min()
        .date()
    )
    + " |",
    f'| "a população de Clojure em 2024 na RQ3 (3.024)" | 3.024 | {milhar(populacao_2024)} |',
    "",
    "## Tabela de ABRE (`tab:rq3`, média e mediana)",
    "",
    "| Método | Coluna | Antes | Depois |",
    "|---|---|---|---|",
]
colunas = [f"{NOMES[x]} média" for x in LINGUAS] + [f"{NOMES[x]} mediana" for x in LINGUAS]
for metodo, antes in ARTIGO_ABRE.items():
    for i, coluna in enumerate(colunas):
        lingua = LINGUAS[i % 4]
        tabela = abre["medias"] if i < 4 else abre["medianas"]
        N.append(f"| {metodo} | {coluna} | {dec(antes[i])} | {dec(tabela[(metodo, lingua)])} |")
N += [
    "",
    "## Valores de p (Wilcoxon pareado, ABRE)",
    "",
    "| Onde aparece | Antes | Depois |",
    "|---|---|---|",
]


def p_de(lingua: str, metodo: str, contra: str) -> float:
    x = testes[
        (testes["linguagem"] == lingua)
        & (testes["metodo"] == metodo)
        & (testes["contra"] == contra)
    ]
    return float(x["p"].iloc[0])


def venceu(lingua: str, metodo: str, contra: str) -> str:
    x = testes[
        (testes["linguagem"] == lingua)
        & (testes["metodo"] == metodo)
        & (testes["contra"] == contra)
    ].iloc[0]
    return f"{x['vitorias']} de {x['pares']}"


minimo_clojure = min(
    p_de("clojure", m, b)
    for m in ("Coorte^R", "Conservador^R", "Ingênua-Coorte^R")
    for b in ("Ingênua", "Coorte")
)
N += [
    f'| RQ3.1, Python, Coorte contra Ingênua ("p = 0,016") | 0,016 | {p_texto(p_de("python", "Coorte", "Ingênua"))} |',
    f'| RQ3.1, Python, "A Coorte venceu a Ingênua nos 7 anos" | 7 de 7 | {venceu("python", "Coorte", "Ingênua")} |',
    f'| RQ3.1, Clojure, Coorte contra Ingênua ("p de 0,94") | 0,94 | {p_texto(p_de("clojure", "Coorte", "Ingênua"))} |',
    f'| RQ3.2, Python, Ingênua-Coorte^R contra Ingênua ("p = 0,016") | 0,016 | {p_texto(p_de("python", "Ingênua-Coorte^R", "Ingênua"))} |',
    f'| RQ3.2, Python, Conservador^R contra Ingênua ("p = 0,016") | 0,016 | {p_texto(p_de("python", "Conservador^R", "Ingênua"))} |',
    f'| RQ3.2, Python, Coorte^R contra Ingênua ("p = 0,078") | 0,078 | {p_texto(p_de("python", "Coorte^R", "Ingênua"))} |',
    f'| RQ3.2, Clojure, métodos propostos contra Ingênua e Coorte ("p ≥ 0,47", o menor) | 0,47 | menor p: {p_texto(minimo_clojure)} |',
    f'| RQ3.2, Python, Ingênua-Coorte^R contra Coorte^R ("p = 0,69") | 0,69 | {p_texto(p_de("python", "Ingênua-Coorte^R", "Coorte^R"))} |',
    '| RQ3.1, parâmetros de Onoue et al. ("p < 0,001" e "entre 0,61 e 0,99") e RQ3.2, ablações da previsão de repositórios ("p = 0,016", "p = 0,014", "5 dos 7 anos") | outro cenário ou análise em separado | não recalculado aqui |',
    "",
    "## Frases com valores da tabela de ABRE",
    "",
    "| Onde aparece | Antes | Depois |",
    "|---|---|---|",
]
ingenua_py, coorte_py = abre["medias"][("Ingênua", "python")], abre["medias"][("Coorte", "python")]
pior = erros.groupby(["linguagem", "metodo"])["abre"].max()
diferencas_ic = "; ".join(
    f"{NOMES[x]} {dec(abre['medias'][('Ingênua-Coorte^R', x)] - abre['medias'][('Ingênua', x)], 4)}"
    for x in LINGUAS
)
menor_py = min(METODOS.values(), key=lambda m: abre["medias"][(m, "python")])
menor_cl = min(METODOS.values(), key=lambda m: abre["medias"][(m, "clojure")])
N += [
    f'| RQ3.1, "a Ingênua erra 0,164 e a Coorte 0,076" (Python) | 0,164 e 0,076 | {dec(ingenua_py)} e {dec(coorte_py)} |',
    f'| RQ3.2, "O menor erro de Python é o do Conservador^R (0,055)" | Conservador^R, 0,055 | {menor_py}, {dec(abre["medias"][(menor_py, "python")])} |',
    f'| RQ3.2, "o de Clojure é o da Coorte^R (0,068)" | Coorte^R, 0,068 | {menor_cl}, {dec(abre["medias"][(menor_cl, "clojure")])} |',
    f'| RQ3.2, "o pior ano da Coorte errou 0,188, e o da Coorte^R, 0,127" (Clojure) | 0,188 e 0,127 | {dec(pior[("clojure", "Coorte")])} e {dec(pior[("clojure", "Coorte^R")])} |',
    f'| RQ3.2, OCaml, "0,0600 e 0,0604, contra 0,0603" (Ingênua-Coorte^R, Conservador^R e Ingênua) | 0,0600; 0,0604; 0,0603 | {dec(abre["medias"][("Ingênua-Coorte^R", "ocaml")], 4)}; {dec(abre["medias"][("Conservador^R", "ocaml")], 4)}; {dec(abre["medias"][("Ingênua", "ocaml")], 4)} |',
    f'| RQ3.2, "a Ingênua mantém a menor mediana (0,019)" (OCaml) | 0,019 | Ingênua {dec(abre["medianas"][("Ingênua", "ocaml")])}; menor mediana: {min(METODOS.values(), key=lambda m: abre["medianas"][(m, "ocaml")])} |',
    f'| RQ3.2, Elixir, "a Ingênua continua com o menor erro (0,025), e só a Ingênua-Coorte^R fica perto (0,026)" | 0,025 e 0,026 | Ingênua {dec(abre["medias"][("Ingênua", "elixir")])}; Ingênua-Coorte^R {dec(abre["medias"][("Ingênua-Coorte^R", "elixir")])} |',
    f'| RQ3.2, "nas quatro linguagens, erra no máximo 0,002 acima da Ingênua" (Ingênua-Coorte^R) | 0,002 (Elixir 0,0013) | Ingênua-Coorte^R menos Ingênua (negativo é erro menor): {diferencas_ic} |',
    f'| RQ3.2, "em Python reduz o erro dela de 0,164 para 0,075" | 0,164 e 0,075 | {dec(ingenua_py)} e {dec(abre["medias"][("Ingênua-Coorte^R", "python")])} |',
    "",
    "## Tabela de cobertura (`tab:cobertura`)",
    "",
    "| Linguagem | Coluna | Antes | Depois |",
    "|---|---|---|---|",
]
for lingua in LINGUAS:
    a = ARTIGO_COBERTURA[lingua]
    s, c = cob[lingua]
    N += [
        f"| {NOMES[lingua]} | Anos dentro, sem | {a[0]} de {a[1]} | {s['dentro']} de {s['n']} |",
        f"| {NOMES[lingua]} | Anos dentro, com | {a[2]} de {a[3]} | {c['dentro']} de {c['n']} |",
        f"| {NOMES[lingua]} | Largura mediana, sem | {dec(a[4])} | {dec(s['largura_mediana'])} |",
        f"| {NOMES[lingua]} | Largura mediana, com | {dec(a[5])} | {dec(c['largura_mediana'])} |",
    ]
N += [
    "",
    "## Faixa de 2024 de Clojure",
    "",
    "| Onde aparece | Antes | Depois |",
    "|---|---|---|",
    f'| "Chegaram 588 novatos" (faixa de 0 a 1 ano; aqui, as quatro faixas de 3 meses) | 588 | {milhar(faixa_2024["real_faixa"].iloc[0])} |',
    f'| "a Coorte projetou 1.071" | 1.071 | {milhar(faixa_2024.loc["Coorte", "projecao_faixa"])} |',
    f'| "o Conservador^R 955" | 955 | {milhar(faixa_2024.loc["Conservador^R", "projecao_faixa"])} |',
    f'| "a Ingênua-Coorte^R 895" | 895 | {milhar(faixa_2024.loc["Ingênua-Coorte^R", "projecao_faixa"])} |',
    "",
]
(SAIDA / "numeros_rq3.md").write_text("\n".join(N) + "\n", encoding="utf-8")
print("\n".join(ORIGENS))
print("\n".join(F))
print((SAIDA / "tabela_abre.md").read_text(encoding="utf-8"))
print((SAIDA / "cobertura.md").read_text(encoding="utf-8"))
