"""Conservador pela média de 5 anos (`S4k`) contra o de 8 trimestres (`S4j`), no Longo, não casuais em todo trimestre. Sem projeção nova.

Origens: cada linguagem começa na primeira origem a partir da qual os cinco métodos (Ingênua, Coorte, Coorte^R, Conservador^R e Ingênua-Coorte^R) projetam em todos os
trimestres seguintes, até 31/12/2023. Confere que as previsões de Ingênua, Coorte, Coorte^R e Ingênua-Coorte^R, e dos intervalos pessimista e otimista, são as da rodada anterior.
Grava em `<saida>`: `erros_por_origem.csv` (mesmo formato, com as duas versões do Conservador), `comparacao_conservador.md` e `.csv`, `origens.md` e `conferencia_previsoes.md`.

Uso (na raiz do repo): uv run --no-project --with pandas --with numpy python scripts/granularidade/conservador5_analise.py <S4j unidades> <S4k unidades> <saida>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ANTES, DEPOIS, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
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
INALTERADOS = [
    "ingenua",
    "coorte_R0",
    "coorte_R3",
    "C3_R3",
    "pessimista_R0",
    "otimista_R0",
    "pessimista_nova_R3",
    "otimista_nova_R3",
]
SEIS = {**CINCO, "conservador_R0": "Conservador (sem repositórios)"}
CENARIO = "Longo, não casuais, Conservador de 5 anos"
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


def inicio_da_sequencia(t: pd.DataFrame) -> list[int]:
    """Origens (k) a partir da primeira em que os cinco métodos projetam em todas as seguintes, até 31/12/2023."""
    abre = t[t["metodo"].isin(CINCO)].pivot(index="k", columns="metodo", values="abre")[list(CINCO)]
    origem = t.drop_duplicates("k").set_index("k")["origem"]
    ok = abre.notna().all(axis=1) & (origem.reindex(abre.index) <= ULTIMA)
    ate_a_ultima = [k for k in ok.index if origem.loc[k] <= ULTIMA]
    ultimo_indefinido = max([k for k in ate_a_ultima if not ok.loc[k]] or [-1])
    return [k for k in ate_a_ultima if k > ultimo_indefinido]


antes = {x: le(ANTES, "S4j", x) for x in LINGUAS}
depois = {x: le(DEPOIS, "S4k", x) for x in LINGUAS}

# 1. Conferência: os métodos que não mudam têm as mesmas previsões
C = [
    "# Conferência das previsões que não mudam (S4k contra S4j)",
    "",
    "Previsões de todas as origens (não só as escolhidas), comparadas uma a uma.",
    "",
    "| Linguagem | Método | Previsões comparadas | Diferentes |",
    "|---|---|---|---|",
]
for lingua in LINGUAS:
    a = antes[lingua].set_index(["k", "metodo"])["previsto"]
    b = depois[lingua].set_index(["k", "metodo"])["previsto"]
    for metodo in INALTERADOS:
        idx = [i for i in a.index.intersection(b.index) if i[1] == metodo]
        x, y = a.loc[idx].to_numpy(), b.loc[idx].to_numpy()
        iguais = (np.isnan(x) & np.isnan(y)) | (np.abs(x - y) <= 1e-8 * np.maximum(1.0, np.abs(y)))
        C.append(f"| {NOMES[lingua]} | {metodo} | {len(idx)} | {int((~iguais).sum())} |")
        if not iguais.all():
            (SAIDA / "conferencia_previsoes.md").write_text("\n".join(C) + "\n", encoding="utf-8")
            sys.exit(
                f"{lingua} {metodo}: {int((~iguais).sum())} previsões diferem da rodada anterior; parei"
            )
    # o Conservador tem de ter mudado
    for metodo in ("conservador_R0", "conservador_R3"):
        idx = [i for i in a.index.intersection(b.index) if i[1] == metodo]
        x, y = a.loc[idx].to_numpy(), b.loc[idx].to_numpy()
        mudou = ~(
            (np.isnan(x) & np.isnan(y)) | (np.abs(x - y) <= 1e-8 * np.maximum(1.0, np.abs(y)))
        )
        C.append(
            f"| {NOMES[lingua]} | {metodo} (muda de propósito) | {len(idx)} | {int(mudou.sum())} |"
        )
C.append("")
(SAIDA / "conferencia_previsoes.md").write_text("\n".join(C) + "\n", encoding="utf-8")

# 2. Origens
ks = {x: inicio_da_sequencia(depois[x]) for x in LINGUAS}
ks_antes = {x: inicio_da_sequencia(antes[x]) for x in LINGUAS}
ORIGENS = [
    "# Origens",
    "",
    "Primeira origem a partir da qual os cinco métodos projetam em todos os trimestres seguintes, até 31/12/2023.",
    "",
    "| Linguagem | Origens | Primeira | Última | Mesmas da rodada anterior? | Conservador sem repositórios projeta em todas? |",
    "|---|---|---|---|---|---|",
]
for lingua in LINGUAS:
    origem = depois[lingua].drop_duplicates("k").set_index("k")["origem"]
    sem_r = depois[lingua][
        (depois[lingua]["metodo"] == "conservador_R0") & depois[lingua]["k"].isin(ks[lingua])
    ]
    todas = bool(sem_r["previsto"].notna().all()) and len(sem_r) == len(ks[lingua])
    ORIGENS.append(
        f"| {NOMES[lingua]} | {len(ks[lingua])} | {origem.loc[ks[lingua]].min().date()} | {origem.loc[ks[lingua]].max().date()} | {'sim' if ks[lingua] == ks_antes[lingua] else 'não'} | {'sim' if todas else 'não'} |"
    )
ORIGENS.append("")
(SAIDA / "origens.md").write_text("\n".join(ORIGENS) + "\n", encoding="utf-8")


# 3. Erros por origem (novo) e do Conservador antigo nas mesmas origens
def erros(
    t: pd.DataFrame, lingua: str, escolhidas: list[int], nomes: dict, cenario: str
) -> pd.DataFrame:
    linhas = []
    for _, x in t[t["k"].isin(escolhidas) & t["metodo"].isin(nomes)].iterrows():
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
                "metodo": nomes[x["metodo"]],
                "previsto": p,
                "real": r,
                "sinal": 100 * (p - r) / r,
                "abre": abs(p - r) / min(p, r),
                "erro_pessoas": abs(p - r),
            }
        )
    return pd.DataFrame(linhas)


novo = pd.concat([erros(depois[x], x, ks[x], SEIS, CENARIO) for x in LINGUAS], ignore_index=True)
novo.to_csv(SAIDA / "erros_por_origem.csv", index=False, float_format="%.10g")
antigo = pd.concat(
    [
        erros(
            antes[x],
            x,
            ks[x],
            {
                "conservador_R0": "Conservador (sem repositórios), antigo",
                "conservador_R3": "Conservador^R, antigo",
            },
            "Conservador de 8 trimestres",
        )
        for x in LINGUAS
    ],
    ignore_index=True,
)
antigo.to_csv(SAIDA / "erros_por_origem_conservador_antigo.csv", index=False, float_format="%.10g")

# 4. Tabela: erro com sinal e erro absoluto, média e mediana, com o Conservador antigo ao lado
ordem = [
    "Ingênua",
    "Coorte",
    "Coorte^R",
    "Ingênua-Coorte^R",
    "Conservador (sem repositórios)",
    "Conservador (sem repositórios), antigo",
    "Conservador^R",
    "Conservador^R, antigo",
]
tudo = pd.concat([novo, antigo], ignore_index=True)
linhas = []
for lingua in LINGUAS:
    for metodo in ordem:
        s = tudo[(tudo["linguagem"] == lingua) & (tudo["metodo"] == metodo)]
        linhas.append(
            {
                "linguagem": lingua,
                "metodo": metodo,
                "origens": len(s),
                "sinal_media": s["sinal"].mean(),
                "sinal_mediana": s["sinal"].median(),
                "sinal_desvio": s["sinal"].std(ddof=1),
                "erro_pessoas_media": s["erro_pessoas"].mean(),
                "erro_pessoas_mediana": s["erro_pessoas"].median(),
                "abre_medio": s["abre"].mean(),
                "abre_mediano": s["abre"].median(),
            }
        )
comp = pd.DataFrame(linhas)
comp.to_csv(SAIDA / "comparacao_conservador.csv", index=False, float_format="%.10g")
T = [
    "# Conservador de 5 anos contra o de 8 trimestres",
    "",
    "Erro com sinal = (previsto − real) / real, em %; positivo é superestimar. Erro absoluto = |previsto − real| em pessoas. Cada célula traz média / mediana. Origens: o início da sequência de cada linguagem (ver `origens.md`). O Conservador antigo é o do `S4j` (média de 8 trimestres), nas mesmas origens.",
    "",
    "| Linguagem | Método | Origens | Erro com sinal (%) | Erro absoluto (pessoas) | Desvio do erro com sinal (%) | ABRE |",
    "|---|---|---|---|---|---|---|",
]
for _, x in comp.iterrows():
    T.append(
        f"| {NOMES[x['linguagem']]} | {x['metodo']} | {x['origens']} | {dec(x['sinal_media'])} / {dec(x['sinal_mediana'])} | {milhar(x['erro_pessoas_media'])} / {milhar(x['erro_pessoas_mediana'])} | {dec(x['sinal_desvio'])} | {dec(x['abre_medio'], 3)} / {dec(x['abre_mediano'], 3)} |"
    )
T.append("")
(SAIDA / "comparacao_conservador.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(ORIGENS))
print("\n".join(C[:6]), "...")
print("\n".join(T[:40]))
