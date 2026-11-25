"""Janela de 4 trimestres (`S4m`) contra a de 2 trimestres (`S4k`), no Longo, não casuais em todo trimestre. Sem projeção nova.

Origens: cada linguagem começa na primeira origem a partir da qual os cinco métodos (Ingênua, Coorte, Coorte^R, Conservador^R e Ingênua-Coorte^R) projetam em todos os trimestres
seguintes, até 31/12/2023. Confere que o `S4k` refeito com o código novo dá as previsões do `S4k` anterior (a generalização da média de transições não muda nada) e que a Ingênua não muda.
Grava em `<saida>`: `erros_por_origem.csv` (mesmo formato, seis métodos), `comparacao.md` e `.csv` (média e mediana do erro com sinal, do erro absoluto em pessoas e do MAPE, com a rodada de
2 trimestres ao lado), `origens.md` e `conferencia.md`.

Uso (na raiz do repo): uv run --no-project --with pandas --with numpy python scripts/granularidade/janela4_analise.py <S4k anterior> <S4k refeito e S4m> <saida>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ANTERIOR, NOVAS, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
SAIDA.mkdir(parents=True, exist_ok=True)
LINGUAS = ["clojure", "elixir", "ocaml", "python"]
NOMES = {"clojure": "Clojure", "elixir": "Elixir", "ocaml": "OCaml", "python": "Python"}
CINCO = {
    "ingenua": "Ingênua",
    "coorte_R0": "Coorte",
    "coorte_R3": "Coorte^R",
    "conservador_R3": "Conservador^R",
    "C3_R3": "Ingênua-Coorte^R",
}
SEIS = {
    "ingenua": "Ingênua",
    "coorte_R0": "Coorte",
    "coorte_R3": "Coorte^R",
    "conservador_R0": "Conservador",
    "conservador_R3": "Conservador^R",
    "C3_R3": "Ingênua-Coorte^R",
}
ORDEM = ["Ingênua", "Coorte", "Coorte^R", "Conservador", "Conservador^R", "Ingênua-Coorte^R"]
CENARIO = "Longo, não casuais, janela de 4 trimestres"
ULTIMA = pd.Timestamp("2023-12-31")


def dec(x: float, casas: int = 1) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


def milhar(x: float) -> str:
    return "n/d" if pd.isna(x) else f"{x:,.0f}".replace(",", ".")


def le(pasta: Path, codigo: str, lingua: str) -> pd.DataFrame:
    partes = []
    for sufixo in ("", "_R1", "_R2", "_R3"):
        caminho = pasta / f"{lingua}_{codigo}{sufixo}_pares.csv.gz"
        if not caminho.exists():
            sys.exit(f"falta o arquivo {caminho}")
        partes.append(pd.read_csv(caminho))
    t = pd.concat(partes, ignore_index=True).drop_duplicates(["k", "metodo"])
    t["origem"] = pd.to_datetime(t["origem"])
    return t


def iguais(a: pd.Series, b: pd.Series, metodos: list[str]) -> tuple[int, int]:
    idx = [i for i in a.index.intersection(b.index) if i[1] in metodos]
    x, y = a.loc[idx].to_numpy(), b.loc[idx].to_numpy()
    ok = (np.isnan(x) & np.isnan(y)) | (np.abs(x - y) <= 1e-8 * np.maximum(1.0, np.abs(y)))
    return len(idx), int((~ok).sum())


def sequencia(t: pd.DataFrame) -> list[int]:
    abre = t[t["metodo"].isin(CINCO)].pivot(index="k", columns="metodo", values="abre")[list(CINCO)]
    origem = t.drop_duplicates("k").set_index("k")["origem"]
    ks = [k for k in abre.index if origem.loc[k] <= ULTIMA]
    ok = abre.notna().all(axis=1)
    ultimo_indefinido = max([k for k in ks if not ok.loc[k]] or [-1])
    return [k for k in ks if k > ultimo_indefinido]


velho = {x: le(ANTERIOR, "S4k", x) for x in LINGUAS}
dois = {x: le(NOVAS, "S4k", x) for x in LINGUAS if (NOVAS / f"{x}_S4k_pares.csv.gz").exists()}
quatro = {x: le(NOVAS, "S4m", x) for x in LINGUAS}

C = [
    "# Conferências",
    "",
    "| Conferência | Linguagem | Previsões comparadas | Diferentes |",
    "|---|---|---|---|",
]
for lingua in LINGUAS:
    if lingua in dois:  # o S4k refeito é o S4k anterior
        a, b = (
            velho[lingua].set_index(["k", "metodo"])["previsto"],
            dois[lingua].set_index(["k", "metodo"])["previsto"],
        )
        n, d = iguais(a, b, list(SEIS))
        C.append(f"| S4k refeito contra o anterior (seis métodos) | {NOMES[lingua]} | {n} | {d} |")
        if d:
            (SAIDA / "conferencia.md").write_text("\n".join(C) + "\n", encoding="utf-8")
            sys.exit(f"{lingua}: o S4k refeito difere do anterior em {d} previsões; parei")
    a, b = (
        velho[lingua].set_index(["k", "metodo"])["previsto"],
        quatro[lingua].set_index(["k", "metodo"])["previsto"],
    )
    n, d = iguais(a, b, ["ingenua"])
    C.append(f"| Ingênua, S4m contra S4k | {NOMES[lingua]} | {n} | {d} |")
    if d:
        sys.exit(f"{lingua}: a Ingênua mudou ({d} previsões)")
C.append("")
(SAIDA / "conferencia.md").write_text("\n".join(C) + "\n", encoding="utf-8")

ks = {x: sequencia(quatro[x]) for x in LINGUAS}
ks_velho = {x: sequencia(velho[x]) for x in LINGUAS}
ORIGENS = [
    "# Origens",
    "",
    "Primeira origem a partir da qual os cinco métodos projetam em todos os trimestres seguintes, até 31/12/2023.",
    "",
    "| Linguagem | Origens | Primeira | Última | Mesmas da rodada de 2 trimestres? | Conservador projeta em todas? |",
    "|---|---|---|---|---|---|",
]
for lingua in LINGUAS:
    origem = quatro[lingua].drop_duplicates("k").set_index("k")["origem"]
    sem_r = quatro[lingua][
        (quatro[lingua]["metodo"] == "conservador_R0") & quatro[lingua]["k"].isin(ks[lingua])
    ]
    todas = bool(sem_r["previsto"].notna().all()) and len(sem_r) == len(ks[lingua])
    ORIGENS.append(
        f"| {NOMES[lingua]} | {len(ks[lingua])} | {origem.loc[ks[lingua]].min().date()} | {origem.loc[ks[lingua]].max().date()} | {'sim' if ks[lingua] == ks_velho[lingua] else 'não'} | {'sim' if todas else 'não'} |"
    )
ORIGENS.append("")
(SAIDA / "origens.md").write_text("\n".join(ORIGENS) + "\n", encoding="utf-8")


def erros(t: pd.DataFrame, lingua: str, escolhidas: list[int], cenario: str) -> pd.DataFrame:
    linhas = []
    for _, x in t[t["k"].isin(escolhidas) & t["metodo"].isin(SEIS)].iterrows():
        p, r = float(x["previsto"]), float(x["real"])
        if not (p > 0 and r > 0):
            sys.exit(
                f"par faltando: {lingua} {x['origem'].date()} {x['metodo']}: previsto {p}, real {r}"
            )
        linhas.append(
            {
                "cenario": cenario,
                "linguagem": lingua,
                "origem": x["origem"].date().isoformat(),
                "metodo": SEIS[x["metodo"]],
                "previsto": p,
                "real": r,
                "sinal": 100 * (p - r) / r,
                "abre": abs(p - r) / min(p, r),
                "erro_pessoas": abs(p - r),
            }
        )
    return pd.DataFrame(linhas)


novo = pd.concat([erros(quatro[x], x, ks[x], CENARIO) for x in LINGUAS], ignore_index=True)
novo.to_csv(SAIDA / "erros_por_origem.csv", index=False, float_format="%.10g")
anterior = pd.concat(
    [erros(velho[x], x, ks[x], "Longo, não casuais, janela de 2 trimestres") for x in LINGUAS],
    ignore_index=True,
)
anterior.to_csv(SAIDA / "erros_por_origem_2_trimestres.csv", index=False, float_format="%.10g")

linhas = []
for lingua in LINGUAS:
    for metodo in ORDEM:
        registro = {"linguagem": lingua, "metodo": metodo}
        for rotulo, e in (("4", novo), ("2", anterior)):
            s = e[(e["linguagem"] == lingua) & (e["metodo"] == metodo)]
            mape = s["sinal"].abs()
            registro.update(
                {
                    f"origens_{rotulo}": len(s),
                    f"sinal_media_{rotulo}": s["sinal"].mean(),
                    f"sinal_mediana_{rotulo}": s["sinal"].median(),
                    f"erro_pessoas_media_{rotulo}": s["erro_pessoas"].mean(),
                    f"erro_pessoas_mediana_{rotulo}": s["erro_pessoas"].median(),
                    f"mape_{rotulo}": mape.mean(),
                    f"mdape_{rotulo}": mape.median(),
                }
            )
        linhas.append(registro)
comp = pd.DataFrame(linhas)
comp.to_csv(SAIDA / "comparacao.csv", index=False, float_format="%.10g")
T = [
    "# Janela de 4 trimestres contra a de 2 trimestres",
    "",
    "Erro com sinal = (previsto − real) / real, em %; positivo é superestimar. Erro absoluto = |previsto − real| em pessoas. MAPE = média de |previsto − real| / real, em %, e a segunda cifra é a mediana. Cada célula traz média / mediana. As duas rodadas usam as mesmas origens (o início da sequência contínua da rodada de 4 trimestres, ver `origens.md`). Os dois grupos de colunas são a rodada de 4 trimestres (novo) e a de 2 trimestres (antes).",
    "",
    "| Linguagem | Método | Origens | Erro com sinal (%), 4 | Erro com sinal (%), 2 | Erro absoluto (pessoas), 4 | Erro absoluto (pessoas), 2 | MAPE (%), 4 | MAPE (%), 2 |",
    "|---|---|---|---|---|---|---|---|---|",
]
for _, x in comp.iterrows():
    T.append(
        f"| {NOMES[x['linguagem']]} | {x['metodo']} | {x['origens_4']} | {dec(x['sinal_media_4'])} / {dec(x['sinal_mediana_4'])} | {dec(x['sinal_media_2'])} / {dec(x['sinal_mediana_2'])} | {milhar(x['erro_pessoas_media_4'])} / {milhar(x['erro_pessoas_mediana_4'])} | {milhar(x['erro_pessoas_media_2'])} / {milhar(x['erro_pessoas_mediana_2'])} | {dec(x['mape_4'])} / {dec(x['mdape_4'])} | {dec(x['mape_2'])} / {dec(x['mdape_2'])} |"
    )
T.append("")
(SAIDA / "comparacao.md").write_text("\n".join(T) + "\n", encoding="utf-8")
# H4: o erro absoluto médio da Coorte e da Coorte^R não piora mais de 10%
piora = comp[comp["metodo"].isin(["Coorte", "Coorte^R"])].assign(
    razao=lambda d: d["erro_pessoas_media_4"] / d["erro_pessoas_media_2"]
)
print("\n".join(ORIGENS))
print("\n".join(C))
print(piora[["linguagem", "metodo", "razao"]].round(3).to_string(index=False))
