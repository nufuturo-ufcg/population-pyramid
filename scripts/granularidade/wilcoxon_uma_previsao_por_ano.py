"""Wilcoxon pareado com uma previsão por ano (31 de dezembro, dentro da sequência contínua), sem refazer nenhuma projeção. Ver `hipoteses.md` da pasta de saída.

Lê `erros_por_origem.csv` das duas janelas (2 e 4 trimestres). Medida principal: erro percentual absoluto |previsto − real| / real, em %. Ao lado, o ABRE.
Dez comparações por recorte (cinco contra a Ingênua, quatro contra a Coorte sem repetir a Ingênua, e Conservador^R contra Conservador), Wilcoxon exato, bilateral, p < 0,05.
Recortes: por linguagem e as quatro linguagens juntas. Mostra, sem decidir nada, se o p passaria por Bonferroni (0,05 dividido por 10).
Grava em `<saida>`: `pares_usados.csv`, `tabela_janela_2_trimestres.md` e `.csv`, `tabela_janela_4_trimestres.md` e `.csv`, `tabela_lado_a_lado.md` e `.csv`, `descritivas.md` e `confirmacoes.md`.

Uso (na raiz do repo): uv run --no-project --with pandas --with numpy --with scipy python scripts/granularidade/wilcoxon_uma_previsao_por_ano.py <erros janela 2> <erros janela 4> <saida>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

ERROS_2, ERROS_4, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
SAIDA.mkdir(parents=True, exist_ok=True)
LINGUAS = ["clojure", "elixir", "ocaml", "python"]
NOMES = {"clojure": "Clojure", "elixir": "Elixir", "ocaml": "OCaml", "python": "Python"}
METODOS = ["Ingênua", "Coorte", "Coorte^R", "Conservador", "Conservador^R", "Ingênua-Coorte^R"]
RENOMEIA = {"Conservador (sem repositórios)": "Conservador"}
ESPERADOS = {"clojure": 8, "elixir": 4, "ocaml": 8, "python": 8}
COMPARACOES = (
    [
        (m, "Ingênua", "contra a Ingênua")
        for m in ["Coorte", "Coorte^R", "Conservador", "Conservador^R", "Ingênua-Coorte^R"]
    ]
    + [
        (m, "Coorte", "contra a Coorte")
        for m in ["Coorte^R", "Conservador", "Conservador^R", "Ingênua-Coorte^R"]
    ]
    + [("Conservador^R", "Conservador", "efeito do R no Conservador")]
)
N_COMPARACOES = len(COMPARACOES)
BONFERRONI = 0.05 / N_COMPARACOES
JANELAS = {"2 trimestres": ERROS_2, "4 trimestres": ERROS_4}


def dec(x: float, casas: int = 2) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


def p_texto(p: float) -> str:
    if pd.isna(p):
        return "n/d"
    return f"{p:.1e}".replace(".", ",") if p < 0.001 else f"{p:.4f}".replace(".", ",")


def carrega(caminho: Path) -> pd.DataFrame:
    d = pd.read_csv(caminho).assign(metodo=lambda x: x["metodo"].replace(RENOMEIA))
    d["origem"] = pd.to_datetime(d["origem"])
    d = d[d["origem"].dt.month == 12].copy()  # só as origens de 31 de dezembro
    d["mape"] = d["sinal"].abs()  # |previsto − real| / real, em %
    return d


def wilcoxon_exato(a: np.ndarray, b: np.ndarray) -> tuple[float, int, str]:
    """p exato bilateral, número de pares com diferença e o método usado."""
    dif = a - b
    n = int((dif != 0).sum())
    if n == 0:
        return float("nan"), 0, "sem diferença"
    r = wilcoxon(a, b, method="exact", alternative="two-sided")
    return float(r.pvalue), n, "exato"


# 1. Pares usados e confirmações
confirmacoes = ["# Confirmações", ""]
pares = {}
for janela, caminho in JANELAS.items():
    d = carrega(caminho)
    assert set(METODOS) <= set(d["metodo"]), (
        f"{janela}: faltam métodos {set(METODOS) - set(d['metodo'])}"
    )
    for lingua in LINGUAS:
        o = d[(d["linguagem"] == lingua) & (d["metodo"] == "Ingênua")]["origem"].sort_values()
        if len(o) != ESPERADOS[lingua]:
            sys.exit(
                f"{janela} {lingua}: {len(o)} origens de dezembro, esperado {ESPERADOS[lingua]}: {[x.date().isoformat() for x in o]}"
            )
        anos = o.dt.year.to_numpy()
        assert (np.diff(anos) == 1).all(), f"{janela} {lingua}: dezembros não consecutivos: {anos}"
        # os métodos têm exatamente essas origens
        for m in METODOS:
            om = d[(d["linguagem"] == lingua) & (d["metodo"] == m)]["origem"].sort_values()
            assert list(om) == list(o), f"{janela} {lingua} {m}: origens diferentes das da Ingênua"
        confirmacoes.append(
            f"- {janela}, {NOMES[lingua]}: {len(o)} previsões de {o.min().date()} a {o.max().date()}; alvos de {(o.min() + pd.DateOffset(years=1)).date()} a {(o.max() + pd.DateOffset(years=1)).date()}, 12 meses um do outro."
        )
    pares[janela] = d
total = sum(ESPERADOS.values())
confirmacoes += [
    "",
    f"Total: {total} pares (linguagem e ano) por janela. Origens de 31 de dezembro dentro da sequência contínua; dez/2016 a dez/2023 em Clojure, OCaml e Python e dez/2020 a dez/2023 em Elixir.",
    "",
    "Sobreposição dos alvos: cada alvo é a população ativa de um ano de calendário (12 meses terminados em 31 de dezembro do ano seguinte à origem). Os alvos de duas previsões consecutivas distam exatamente 12 meses, então os 12 meses de cada alvo não se sobrepõem aos do alvo anterior. O alvo de uma previsão é a janela de observação da origem seguinte, ou seja, os intervalos são adjacentes e não se sobrepõem, mas as mesmas pessoas podem aparecer em anos seguidos.",
    "",
]
(SAIDA / "confirmacoes.md").write_text("\n".join(confirmacoes) + "\n", encoding="utf-8")
usados = pd.concat([d.assign(janela=j) for j, d in pares.items()], ignore_index=True)
usados["alvo"] = usados["origem"] + pd.DateOffset(years=1)
usados[
    [
        "janela",
        "linguagem",
        "origem",
        "alvo",
        "metodo",
        "previsto",
        "real",
        "mape",
        "abre",
        "erro_pessoas",
    ]
].to_csv(SAIDA / "pares_usados.csv", index=False, float_format="%.10g")


# 2. Testes
def testa(d: pd.DataFrame, recorte: str, janela: str) -> list[dict]:
    """Uma linha por comparação, no recorte `recorte` (uma linguagem ou `juntas`)."""
    linhas = []
    base = d if recorte == "juntas" else d[d["linguagem"] == recorte]
    for a, b, grupo in COMPARACOES:
        x = base[base["metodo"] == a].set_index(["linguagem", "origem"]).sort_index()
        y = base[base["metodo"] == b].set_index(["linguagem", "origem"]).sort_index()
        assert list(x.index) == list(y.index)
        registro = {
            "janela": janela,
            "recorte": recorte,
            "grupo": grupo,
            "metodo_a": a,
            "metodo_b": b,
            "pares": len(x),
        }
        for medida in ("mape", "abre"):
            va, vb = x[medida].to_numpy(), y[medida].to_numpy()
            p, n_dif, como = wilcoxon_exato(va, vb)
            registro.update(
                {
                    f"{medida}_vitorias_a": int((va < vb).sum()),
                    f"{medida}_vitorias_b": int((vb < va).sum()),
                    f"{medida}_empates": int((va == vb).sum()),
                    f"{medida}_mediana_da_diferenca": float(np.median(va - vb)),
                    f"{medida}_p": p,
                    f"{medida}_menor_p_possivel": 2.0 / 2.0**n_dif if n_dif else float("nan"),
                    f"{medida}_significativo": bool(p < 0.05) if not np.isnan(p) else False,
                    f"{medida}_passa_bonferroni": bool(p < BONFERRONI)
                    if not np.isnan(p)
                    else False,
                    f"{medida}_metodo_do_p": como,
                }
            )
        linhas.append(registro)
    return linhas


resultado = []
for janela, d in pares.items():
    for recorte in [*LINGUAS, "juntas"]:
        resultado += testa(d, recorte, janela)
res = pd.DataFrame(resultado)
res.to_csv(SAIDA / "resultados.csv", index=False, float_format="%.10g")
assert (res["mape_metodo_do_p"] == "exato").all() and (res["abre_metodo_do_p"] == "exato").all(), (
    "algum p não é exato (diferença nula)"
)

NOME_DO_RECORTE = {**{x: NOMES[x] for x in LINGUAS}, "juntas": "Quatro linguagens juntas"}
AVISO_ELIXIR = "Com 4 pares (Elixir) o menor p possível é 0,125 (2 / 2⁴), então nenhuma diferença pode ser significativa."
AVISO_OITO = "Com 8 pares o menor p possível é 0,0078 (2 / 2⁸): só vitória em todos os 8 anos dá p abaixo de 0,05, e nenhum p passa por Bonferroni (0,05 / 10 = 0,005)."
AVISO_JUNTAS = "Juntando as linguagens, cada par é uma linguagem num ano (28 pares). Linguagens no mesmo ano podem sofrer o mesmo choque, então os pares do mesmo ano não são independentes."


def tabela_da_janela(janela: str) -> list[str]:
    r = res[res["janela"] == janela]
    T = [
        f"# Wilcoxon com uma previsão por ano, janela de {janela}",
        "",
        "Wilcoxon pareado, exato, bilateral, nível de 95%. Previsões de 31 de dezembro dentro da sequência contínua, alvo 12 meses depois. Medida principal: erro percentual absoluto |previsto − real| / real. Ao lado, o ABRE. Diferença = primeiro método menos segundo (negativa favorece o primeiro); a mediana da diferença do erro percentual é em pontos percentuais e a do ABRE é absoluta. Vitórias: quantas vezes o primeiro e o segundo método tiveram menor erro. Bonferroni é só mostrado: p abaixo de 0,05 / 10 = 0,005 (10 comparações por recorte).",
        "",
        f"Avisos: {AVISO_ELIXIR} {AVISO_OITO} {AVISO_JUNTAS}",
        "",
    ]
    for recorte in [*LINGUAS, "juntas"]:
        x = r[r["recorte"] == recorte]
        T += [f"## {NOME_DO_RECORTE[recorte]} ({x['pares'].iloc[0]} pares)", ""]
        if recorte == "elixir":
            T += [f"{AVISO_ELIXIR}", ""]
        T += [
            "| Comparação | Grupo | Vitórias (1º / 2º) | Mediana da diferença (p.p.) | Menor p possível | p | p < 0,05 | Passaria por Bonferroni | ABRE: vitórias (1º / 2º) | ABRE: mediana da diferença | ABRE: p | ABRE: p < 0,05 |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for _, y in x.iterrows():
            T.append(
                f"| {y['metodo_a']} contra {y['metodo_b']} | {y['grupo']} | {y['mape_vitorias_a']} / {y['mape_vitorias_b']} | {dec(y['mape_mediana_da_diferenca'])} | {p_texto(y['mape_menor_p_possivel'])} | {p_texto(y['mape_p'])} | {'sim' if y['mape_significativo'] else 'não'} | {'sim' if y['mape_passa_bonferroni'] else 'não'} | {y['abre_vitorias_a']} / {y['abre_vitorias_b']} | {dec(y['abre_mediana_da_diferenca'], 4)} | {p_texto(y['abre_p'])} | {'sim' if y['abre_significativo'] else 'não'} |"
            )
        T.append("")
    return T


for janela, arquivo in (
    ("2 trimestres", "tabela_janela_2_trimestres"),
    ("4 trimestres", "tabela_janela_4_trimestres"),
):
    (SAIDA / f"{arquivo}.md").write_text(
        "\n".join(tabela_da_janela(janela)) + "\n", encoding="utf-8"
    )
    res[res["janela"] == janela].to_csv(SAIDA / f"{arquivo}.csv", index=False, float_format="%.10g")

# 3. As duas janelas lado a lado (medida principal; p do ABRE ao lado)
L = [
    "# Wilcoxon com uma previsão por ano: janela de 2 trimestres e de 4 trimestres lado a lado",
    "",
    'Medida principal: erro percentual absoluto. Cada janela mostra as vitórias (1º / 2º), a mediana da diferença em pontos percentuais, o p e se p < 0,05; o p do ABRE vem ao lado. Bonferroni (0,05 / 10 = 0,005) só mostrado: coluna "B" (sim ou não). Veja os avisos nas tabelas de cada janela.',
    "",
    f"{AVISO_ELIXIR} {AVISO_OITO} {AVISO_JUNTAS}",
    "",
]
lado = []
for recorte in [*LINGUAS, "juntas"]:
    L += [
        f"## {NOME_DO_RECORTE[recorte]}",
        "",
        "| Comparação | 2 tri.: vitórias | 2 tri.: mediana (p.p.) | 2 tri.: p | 2 tri.: <0,05 | 2 tri.: B | 2 tri.: p do ABRE | 4 tri.: vitórias | 4 tri.: mediana (p.p.) | 4 tri.: p | 4 tri.: <0,05 | 4 tri.: B | 4 tri.: p do ABRE |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for a, b, _ in COMPARACOES:
        x = res[(res["recorte"] == recorte) & (res["metodo_a"] == a) & (res["metodo_b"] == b)]
        d2, d4 = x[x["janela"] == "2 trimestres"].iloc[0], x[x["janela"] == "4 trimestres"].iloc[0]
        L.append(
            f"| {a} contra {b} | {d2['mape_vitorias_a']} / {d2['mape_vitorias_b']} | {dec(d2['mape_mediana_da_diferenca'])} | {p_texto(d2['mape_p'])} | {'sim' if d2['mape_significativo'] else 'não'} | {'sim' if d2['mape_passa_bonferroni'] else 'não'} | {p_texto(d2['abre_p'])} | {d4['mape_vitorias_a']} / {d4['mape_vitorias_b']} | {dec(d4['mape_mediana_da_diferenca'])} | {p_texto(d4['mape_p'])} | {'sim' if d4['mape_significativo'] else 'não'} | {'sim' if d4['mape_passa_bonferroni'] else 'não'} | {p_texto(d4['abre_p'])} |"
        )
        lado.append(
            {
                "recorte": recorte,
                "comparacao": f"{a} contra {b}",
                "p_2": d2["mape_p"],
                "p_4": d4["mape_p"],
                "sig_2": d2["mape_significativo"],
                "sig_4": d4["mape_significativo"],
            }
        )
    L.append("")
(SAIDA / "tabela_lado_a_lado.md").write_text("\n".join(L) + "\n", encoding="utf-8")
pd.DataFrame(lado).to_csv(SAIDA / "tabela_lado_a_lado.csv", index=False, float_format="%.10g")

# 4. Descritivas: erro percentual absoluto e ABRE por método e linguagem (média e mediana de 8 ou 4 previsões)
Q = [
    "# Descritivas das previsões usadas",
    "",
    "Média / mediana do erro percentual absoluto (%) e do ABRE, nas previsões de 31 de dezembro (8 por linguagem, 4 em Elixir). Para comparar com a mediana de ABRE de 0,40 de Onoue et al. (projetos isolados, previsão de 3 meses), lembre que aqui o objeto é a linguagem inteira e o horizonte é de 12 meses.",
    "",
]
for janela, d in pares.items():
    Q += [
        f"## Janela de {janela}",
        "",
        "| Linguagem | " + " | ".join(METODOS) + " |",
        "|---|" + "---|" * len(METODOS),
    ]
    for lingua in LINGUAS:
        celulas = []
        for m in METODOS:
            s = d[(d["linguagem"] == lingua) & (d["metodo"] == m)]
            celulas.append(
                f"{dec(s['mape'].mean(), 1)} / {dec(s['mape'].median(), 1)}; ABRE {dec(s['abre'].mean(), 3)} / {dec(s['abre'].median(), 3)}"
            )
        Q.append(f"| {NOMES[lingua]} | " + " | ".join(celulas) + " |")
    celulas = []
    for m in METODOS:
        s = d[d["metodo"] == m]
        celulas.append(
            f"{dec(s['mape'].mean(), 1)} / {dec(s['mape'].median(), 1)}; ABRE {dec(s['abre'].mean(), 3)} / {dec(s['abre'].median(), 3)}"
        )
    Q.append("| Juntas (28 pares) | " + " | ".join(celulas) + " |")
    Q.append("")
(SAIDA / "descritivas.md").write_text("\n".join(Q) + "\n", encoding="utf-8")
print("\n".join(confirmacoes))
print("\n".join(L[:20]))
