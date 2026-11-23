"""Resumo da cobertura do intervalo pessimista-otimista no S2 (RQ3.3). Ver `hipoteses.md`.

Lê `<saida>/unidades/` (S2 com pessimista e otimista em R0 a R3). Confere R0 e R1 contra `intervalos.csv` da granularidade
e as previsões antigas contra `projecao-rq3/unidades/`; para se algo diferir.
Grava `por_origem.csv`, `tabelas.md` e `resumo.md` em `<saida>`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/resumo_cobertura.py <saida> <projecao-rq3> <projecao-granularidade>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from util_resumo import num

SAIDA = Path(sys.argv[1])
ANTIGA = Path(sys.argv[2])
GRAN = Path(sys.argv[3])
UNIDADES = SAIDA / "unidades"
LINGUAS = ["clojure", "elixir", "ocaml", "python"]
NOMES = {"clojure": "Clojure", "elixir": "Elixir", "ocaml": "OCaml", "python": "Python"}
COMMIT = (SAIDA / "commit.txt").read_text(encoding="utf-8").strip()
# métodos que definem as origens da Parte 2 de projecao-rq3
PARTE2 = ["ingenua", "coorte_R0", "coorte_R3", "C3_R3", "conservador_R3", "conservador_R0"]
PONTUAIS = [
    ("coorte", 0, "Coorte R0"),
    ("coorte", 3, "Coorte R3"),
    ("conservador", 3, "Conservador R3"),
]


def carrega(pasta: Path, lingua: str) -> pd.DataFrame:
    partes = [pd.read_csv(pasta / "unidades" / f"{lingua}_S2_pares.csv.gz")]
    for r in (1, 2, 3):
        partes.append(pd.read_csv(pasta / "unidades" / f"{lingua}_S2_R{r}_pares.csv.gz"))
    return pd.concat(partes, ignore_index=True)


def posicao(valor: float, pess: float, otim: float) -> str:
    if np.isnan(valor) or np.isnan(pess) or np.isnan(otim):
        return "indefinido"
    if valor < pess:
        return "abaixo"
    if valor > otim:
        return "acima"
    return "dentro"


def inteiro(x: float) -> str:
    return "n/d" if pd.isna(x) else f"{x:.0f}"


def pct(x: float) -> str:
    return f"{100 * x:.1f}".replace(".", ",") + "%"


linhas_csv = []
resumo_por_lingua = {}
conferencia = []
vazamento = []
origens_usadas = {}

for lingua in LINGUAS:
    nova = carrega(SAIDA, lingua)
    previsto = nova.pivot(index="k", columns="metodo", values="previsto")
    abre = nova.pivot(index="k", columns="metodo", values="abre")
    origem = nova[nova["metodo"] == "ingenua"].set_index("k")["origem"]
    real = nova[nova["metodo"] == "ingenua"].set_index("k")["real"]

    # 1. as previsões antigas não mudaram
    antiga = carrega(ANTIGA, lingua)
    antiga_prev = antiga.pivot(index="k", columns="metodo", values="previsto")
    comparados, diferentes = 0, 0
    for m in antiga_prev.columns:
        if m not in previsto.columns:
            continue
        for k in antiga_prev.index:
            a, b = antiga_prev.loc[k, m], previsto.loc[k, m]
            comparados += 1
            if np.isnan(a) and np.isnan(b):
                continue
            if np.isnan(a) != np.isnan(b) or abs(a - b) > 1e-9 * max(1.0, abs(a)):
                diferentes += 1
    conferencia.append(
        f"- {NOMES[lingua]}: {comparados} previsões de projecao-rq3 comparadas com esta rodada, {diferentes} diferentes."
    )
    if diferentes:
        sys.exit(f"{lingua}: previsões antigas mudaram ({diferentes}). Parei.")

    # 2. origens da Parte 2: os seis métodos têm ABRE definido
    base = abre[PARTE2].notna().all(axis=1)
    ks = list(abre.index[base])
    origens_usadas[lingua] = f"{origem[ks[0]]} a {origem[ks[-1]]} ({len(ks)})"

    # 3. intervalos, largura relativa e posição dos métodos pontuais
    blocos = []
    for r in range(4):
        pess = previsto[f"pessimista_R{r}"]
        otim = previsto[f"otimista_R{r}"]
        for k in ks:
            linha = {
                "linguagem": lingua,
                "k": k,
                "origem": origem[k],
                "intervalo": f"R{r}",
                "ingenua": previsto.loc[k, "ingenua"],
                "real": real[k],
                "pessimista": pess[k],
                "otimista": otim[k],
            }
            definido = not (np.isnan(pess[k]) or np.isnan(otim[k]))
            linha["definido"] = definido
            linha["real_dentro"] = bool(pess[k] <= real[k] <= otim[k]) if definido else False
            linha["real_abaixo"] = bool(real[k] < pess[k]) if definido else False
            linha["real_acima"] = bool(real[k] > otim[k]) if definido else False
            linha["largura_relativa"] = (
                (otim[k] - pess[k]) / previsto.loc[k, "ingenua"] if definido else np.nan
            )
            for base_nome in ("coorte", "conservador"):
                valor = previsto.loc[k, f"{base_nome}_R{r}"]
                linha[f"{base_nome}_R{r}"] = valor
                linha[f"{base_nome}_posicao"] = posicao(valor, pess[k], otim[k])
            blocos.append(linha)
    por_origem = pd.DataFrame(blocos)
    linhas_csv.append(por_origem)
    resumo_por_lingua[lingua] = por_origem

    # 4. vazamento
    v = pd.read_csv(UNIDADES / f"{lingua}_S2_vazamento.csv")
    vazamento.append(
        f"- {NOMES[lingua]}: {len(v)} origens testadas, estados iguais {bool(v['estados_iguais'].all())}, maior diferença das previsões {v['maior_diferenca_relativa'].max():.1e}, controle de eventos futuros difere em {int(v['controle_eventos_futuros_difere'].sum())} de {len(v)}, controle de promoções difere em {int(v['controle_promocoes_difere'].sum())} de {len(v)}."
    )
    assert v["estados_iguais"].all() and (v["maior_diferenca_relativa"] < 1e-9).all()
    assert v["controle_eventos_futuros_difere"].any() and v["controle_promocoes_difere"].any()

tudo = pd.concat(linhas_csv, ignore_index=True)
tudo.to_csv(SAIDA / "por_origem.csv", index=False, float_format="%.10g")


# conferência de R0 e R1 contra intervalos.csv da granularidade
def mede(por_origem: pd.DataFrame, r: str) -> tuple[int, int, float, float]:
    d = por_origem[(por_origem["intervalo"] == r) & por_origem["definido"]]
    return (
        len(d),
        int(d["real_dentro"].sum()),
        float(d["real_dentro"].mean()),
        float(d["largura_relativa"].median()),
    )


antigos = pd.read_csv(GRAN / "intervalos.csv")
antigos = antigos[(antigos["populacao"] == "P1") & (antigos["passo_meses"] == 12)]
linhas_conf = ["| Linguagem | Intervalo | Pares | Cobertura (esta rodada) | Cobertura (intervalos.csv) | Largura mediana (esta rodada) | Largura mediana (intervalos.csv) |", "|---|---|---|---|---|---|---|"]  # fmt: skip
for lingua in LINGUAS:
    for r, variante in [("R0", "V0"), ("R1", "V2")]:
        n, dentro, fracao, largura = mede(resumo_por_lingua[lingua], r)
        ref = antigos[(antigos["linguagem"] == lingua) & (antigos["variante"] == variante)].iloc[0]
        linhas_conf.append(
            f"| {NOMES[lingua]} | {r} contra {variante} | {n} de {int(ref['pares'])} | {dentro} de {n} ({num(fracao, 4)}) | {num(ref['cobertura'], 4)} | {num(largura, 4)} | {num(ref['largura_relativa_mediana'], 4)} |"
        )
        igual = (
            n == int(ref["pares"])
            and abs(fracao - ref["cobertura"]) < 1e-5
            and abs(largura - ref["largura_relativa_mediana"]) < 1e-5
        )
        if not igual:
            sys.exit(
                f"{lingua} {r}: não reproduz intervalos.csv ({n}, {fracao}, {largura} contra {dict(ref)}). Parei."
            )


# tabelas
T = [
    "# Tabelas da cobertura do intervalo no S2",
    "",
    f"Código: commit `{COMMIT}`. Totais de ativos arredondados para inteiro.",
    "",
]
L = [
    "# Cobertura do intervalo pessimista-otimista no S2 (RQ3.3)",
    "",
    f"Código: commit `{COMMIT}` (previsão e teste de vazamento). Protocolo em `hipoteses.md`, escrito antes de rodar. Tabelas em `tabelas.md`, uma linha por origem em `por_origem.csv`.",
    "",
    "## Definições",
    "",
    "- Cobertura: anos em que o real ficou entre o pessimista e o otimista, inclusive.",
    "- Largura relativa: (otimista menos pessimista) dividida pela ingênua da origem, como em `intervalos.csv`.",
    "- R0: pessimista e otimista da V0. R1: da V2. R2: parada de repositórios nas taxas, novatos como no R0. R3: taxas como no R2 e novatos como no R1.",
    "",
    "## Origens",
    "",
]
for lingua in LINGUAS:
    L.append(f"- {NOMES[lingua]}: {origens_usadas[lingua]}.")
L += ["", "## Vazamento", "", *vazamento]
L += [
    "",
    "## Conferência",
    "",
    "Previsões que já existiam em `projecao-rq3/unidades/`:",
    "",
    *conferencia,
]
L += ["", "R0 e R1 contra `projecao-granularidade/intervalos.csv` (P1, 12 meses, V0 e V2):", ""]
L += [*linhas_conf, ""]
L += ["## Cobertura e largura mediana por linguagem", ""]

for lingua in LINGUAS:
    d = resumo_por_lingua[lingua]
    ks_ordem = list(dict.fromkeys(d["k"]))
    T += [
        f"## {NOMES[lingua]}",
        "",
        f"Origens: {origens_usadas[lingua]}.",
        "",
        "### Cobertura por intervalo",
        "",
    ]
    T += ["| Intervalo | Origens | Real dentro | Cobertura | Real abaixo do pessimista | Real acima do otimista | Largura relativa mediana | Largura relativa máxima |", "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    partes_resumo = []
    for r in range(4):
        g = d[(d["intervalo"] == f"R{r}")]
        gd = g[g["definido"]]
        n = len(gd)
        dentro = int(gd["real_dentro"].sum())
        sem = len(g) - n
        origens_txt = str(n) if sem == 0 else f"{n} ({sem} sem intervalo)"
        T.append(
            f"| R{r} | {origens_txt} | {dentro} de {n} | {pct(dentro / n) if n else 'n/d'} | {int(gd['real_abaixo'].sum())} | {int(gd['real_acima'].sum())} | {num(gd['largura_relativa'].median(), 4)} | {num(gd['largura_relativa'].max(), 4)} |"
        )
        partes_resumo.append(f"R{r} {dentro} de {n} ({num(gd['largura_relativa'].median(), 3)})")
    L.append(
        f"- {NOMES[lingua]}: cobertura (largura relativa mediana) em "
        + ", ".join(partes_resumo)
        + "."
    )
    T += ["", "### Métodos pontuais dentro do intervalo do mesmo R", "", "| Método | Origens | Dentro | Abaixo do pessimista | Acima do otimista |", "|---|---|---|---|---|"]  # fmt: skip
    for base_nome, r, rotulo in PONTUAIS:
        g = d[(d["intervalo"] == f"R{r}") & d["definido"]]
        pos = g[f"{base_nome}_posicao"]
        T.append(
            f"| {rotulo} | {len(g)} | {int((pos == 'dentro').sum())} | {int((pos == 'abaixo').sum())} | {int((pos == 'acima').sum())} |"
        )
    T.append("")
    for r in range(4):
        g = d[d["intervalo"] == f"R{r}"].set_index("k")
        pontuais = [p for p in PONTUAIS if p[1] == r]
        cab = ["Origem", "Pessimista", "Otimista", "Real", "Posição do real"]
        for _, _, rotulo in pontuais:
            cab += [rotulo, f"{rotulo}: posição"]
        T += [
            f"### Intervalo R{r}, por origem",
            "",
            "| " + " | ".join(cab) + " |",
            "|" + "---|" * len(cab),
        ]
        for k in ks_ordem:
            x = g.loc[k]
            if x["definido"]:
                dentro_txt = (
                    "dentro" if x["real_dentro"] else ("abaixo" if x["real_abaixo"] else "acima")
                )
            else:
                dentro_txt = "sem intervalo"
            celulas = [
                str(x["origem"]),
                inteiro(x["pessimista"]),
                inteiro(x["otimista"]),
                inteiro(x["real"]),
                dentro_txt,
            ]
            for base_nome, _, _ in pontuais:
                celulas += [inteiro(x[f"{base_nome}_R{r}"]), x[f"{base_nome}_posicao"]]
            T.append("| " + " | ".join(celulas) + " |")
        T.append("")

(SAIDA / "tabelas.md").write_text("\n".join(T) + "\n", encoding="utf-8")
(SAIDA / "resumo.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
