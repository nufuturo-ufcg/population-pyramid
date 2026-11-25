"""Compara o Longo, não casuais com janelas curtas (`S4j`) com o de antes (`S4`) e explica a origem de 2011 de Clojure. Sem projeção nova.

Lê `<antes>/<l>_S4_*` (rodada anterior), `<depois>/<l>_S4j_*` e `<depois>/<l>_S4_*` (o S4 refeito com o código novo, que tem de dar as mesmas previsões do anterior).
Origens: todo fim de trimestre até 31/12/2023 em que os cinco métodos têm ABRE definido (a regra da rodada anterior, sem piso de ano).
Grava em `<saida>`: `erros_por_origem.csv` (mesmo formato do anterior), `comparacao_erro_com_sinal.md` e `.csv`, `comparacao_abre.md`, `cobertura_antes_depois.md`,
`origens.md` e `origem_2011_clojure.md`.

Uso (na raiz do repo): uv run --no-project --with pandas --with numpy python scripts/granularidade/janelas_curtas_analise.py <antes> <depois> <saida>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ANTES, DEPOIS, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
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
SEM = ("pessimista_R0", "otimista_R0")
COM = ("pessimista_nova_R3", "otimista_nova_R3")
CENARIO = "Longo, não casuais, janelas curtas"
ULTIMA = pd.Timestamp("2023-12-31")


def dec(x: float, casas: int = 3) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


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


def definidas(t: pd.DataFrame) -> pd.Series:
    """Por origem (k), True quando os cinco métodos têm ABRE definido."""
    abre = t[t["metodo"].isin(METODOS)].pivot(index="k", columns="metodo", values="abre")[
        list(METODOS)
    ]
    return abre.notna().all(axis=1)


def erros_do_cenario(t: pd.DataFrame, ks: list[int], lingua: str) -> pd.DataFrame:
    linhas = []
    for _, x in t[t["k"].isin(ks) & t["metodo"].isin(METODOS)].iterrows():
        p, r = float(x["previsto"]), float(x["real"])
        linhas.append(
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
    return pd.DataFrame(linhas)


# 1. O S4 refeito com o código novo dá as mesmas previsões do anterior
for lingua in ["clojure", "elixir", "ocaml"]:
    a = le(ANTES, "S4", lingua).set_index(["k", "metodo"])["previsto"]
    b = le(DEPOIS, "S4", lingua).set_index(["k", "metodo"])["previsto"]
    comuns = a.index.intersection(b.index)
    x, y = a.loc[comuns].to_numpy(), b.loc[comuns].to_numpy()
    iguais = (np.isnan(x) & np.isnan(y)) | (np.abs(x - y) <= 1e-8 * np.maximum(1.0, np.abs(y)))
    if not iguais.all():
        sys.exit(
            f"{lingua}: o S4 refeito difere do anterior em {int((~iguais).sum())} de {len(comuns)} previsões, por exemplo {comuns[~iguais][:3].tolist()}"
        )

# 2. Origens e erros antes e depois
antes, depois, ks_antes, ks_depois = {}, {}, {}, {}
for lingua in LINGUAS:
    antes[lingua], depois[lingua] = le(ANTES, "S4", lingua), le(DEPOIS, "S4j", lingua)
    for t, ks in ((antes[lingua], ks_antes), (depois[lingua], ks_depois)):
        assert t["origem"].max() == ULTIMA, f"{lingua}: a última origem é {t['origem'].max()}"
        ok = definidas(t)
        origem = t.drop_duplicates("k").set_index("k")["origem"]
        ks[lingua] = [k for k in ok.index[ok] if origem.loc[k] <= ULTIMA]
erros_antes = pd.concat(
    [erros_do_cenario(antes[x], ks_antes[x], x) for x in LINGUAS], ignore_index=True
)
erros_depois = pd.concat(
    [erros_do_cenario(depois[x], ks_depois[x], x) for x in LINGUAS], ignore_index=True
)
erros_depois.to_csv(SAIDA / "erros_por_origem.csv", index=False, float_format="%.10g")
erros_antes.assign(cenario="Longo, não casuais (todo trimestre)").to_csv(
    SAIDA / "erros_por_origem_antes.csv", index=False, float_format="%.10g"
)

ORIGENS = [
    "# Origens antes e depois",
    "",
    "Todo fim de trimestre até 31/12/2023 em que os cinco métodos têm ABRE definido. Início da sequência: primeira origem a partir da qual todas as seguintes também projetam.",
    "",
    "| Linguagem | Antes: origens | Antes: primeira | Antes: início da sequência | Depois: origens | Depois: primeira | Depois: início da sequência |",
    "|---|---|---|---|---|---|---|",
]
for lingua in LINGUAS:
    linha = [NOMES[lingua]]
    for t, ks in ((antes[lingua], ks_antes[lingua]), (depois[lingua], ks_depois[lingua])):
        origem = t.drop_duplicates("k").set_index("k")["origem"]
        ok = definidas(t)
        ultimo_indefinido = max([k for k in ok.index[~ok]] or [-1])
        sequencia = [k for k in ok.index if k > ultimo_indefinido]
        linha += [
            str(len(ks)),
            str(origem.loc[ks].min().date()),
            str(origem.loc[sequencia].min().date()) + f" ({len(sequencia)} origens)",
        ]
    ORIGENS.append("| " + " | ".join(linha) + " |")
ORIGENS.append("")
(SAIDA / "origens.md").write_text("\n".join(ORIGENS) + "\n", encoding="utf-8")


# 3. Erro com sinal antes e depois, por método e linguagem
def resume(e: pd.DataFrame, lingua: str, metodo: str, origens: set | None) -> dict:
    s = e[(e["linguagem"] == lingua) & (e["metodo"] == metodo)]
    if origens is not None:
        s = s[s["origem"].isin(origens)]
    return {
        "n": len(s),
        "media": s["sinal"].mean(),
        "mediana": s["sinal"].median(),
        "abre_medio": s["abre"].mean(),
        "abre_mediano": s["abre"].median(),
    }


linhas = []
for lingua in LINGUAS:
    comuns = set(erros_antes[erros_antes["linguagem"] == lingua]["origem"]) & set(
        erros_depois[erros_depois["linguagem"] == lingua]["origem"]
    )
    for metodo in METODOS.values():
        a, d = (
            resume(erros_antes, lingua, metodo, comuns),
            resume(erros_depois, lingua, metodo, comuns),
        )
        a_proprio, d_proprio = (
            resume(erros_antes, lingua, metodo, None),
            resume(erros_depois, lingua, metodo, None),
        )
        linhas.append(
            {
                "linguagem": lingua,
                "metodo": metodo,
                "origens_comuns": a["n"],
                "sinal_media_antes": a["media"],
                "sinal_media_depois": d["media"],
                "sinal_mediana_antes": a["mediana"],
                "sinal_mediana_depois": d["mediana"],
                "abre_medio_antes": a["abre_medio"],
                "abre_medio_depois": d["abre_medio"],
                "abre_mediano_antes": a["abre_mediano"],
                "abre_mediano_depois": d["abre_mediano"],
                "origens_antes": a_proprio["n"],
                "origens_depois": d_proprio["n"],
                "sinal_media_antes_origens_proprias": a_proprio["media"],
                "sinal_media_depois_origens_proprias": d_proprio["media"],
                "sinal_mediana_antes_origens_proprias": a_proprio["mediana"],
                "sinal_mediana_depois_origens_proprias": d_proprio["mediana"],
            }
        )
comp = pd.DataFrame(linhas)
comp.to_csv(SAIDA / "comparacao_erro_com_sinal.csv", index=False, float_format="%.10g")
C = [
    "# Erro com sinal antes e depois das janelas curtas",
    "",
    "Erro com sinal = (previsto − real) / real, em %. Positivo é superestimar. Antes: novatos, surgimento e parada com as janelas de 2 anos e a última transição. Depois: as 2 últimas contagens e as 2 últimas transições. Origens comuns: as que têm os cinco métodos definidos nas duas rodadas.",
    "",
    "## Origens comuns às duas rodadas",
    "",
    "| Linguagem | Método | Origens | Média antes | Média depois | Mediana antes | Mediana depois |",
    "|---|---|---|---|---|---|---|",
]
for _, x in comp.iterrows():
    C.append(
        f"| {NOMES[x['linguagem']]} | {x['metodo']} | {x['origens_comuns']} | {dec(x['sinal_media_antes'], 1)} | {dec(x['sinal_media_depois'], 1)} | {dec(x['sinal_mediana_antes'], 1)} | {dec(x['sinal_mediana_depois'], 1)} |"
    )
C += [
    "",
    "## Origens próprias de cada rodada",
    "",
    "| Linguagem | Método | Origens antes | Origens depois | Média antes | Média depois | Mediana antes | Mediana depois |",
    "|---|---|---|---|---|---|---|---|",
]
for _, x in comp.iterrows():
    C.append(
        f"| {NOMES[x['linguagem']]} | {x['metodo']} | {x['origens_antes']} | {x['origens_depois']} | {dec(x['sinal_media_antes_origens_proprias'], 1)} | {dec(x['sinal_media_depois_origens_proprias'], 1)} | {dec(x['sinal_mediana_antes_origens_proprias'], 1)} | {dec(x['sinal_mediana_depois_origens_proprias'], 1)} |"
    )
C.append("")
(SAIDA / "comparacao_erro_com_sinal.md").write_text("\n".join(C) + "\n", encoding="utf-8")
A = [
    "# ABRE médio e mediano antes e depois (origens comuns)",
    "",
    "| Linguagem | Método | ABRE médio antes | ABRE médio depois | ABRE mediano antes | ABRE mediano depois |",
    "|---|---|---|---|---|---|",
]
for _, x in comp.iterrows():
    A.append(
        f"| {NOMES[x['linguagem']]} | {x['metodo']} | {dec(x['abre_medio_antes'])} | {dec(x['abre_medio_depois'])} | {dec(x['abre_mediano_antes'])} | {dec(x['abre_mediano_depois'])} |"
    )
A.append("")
(SAIDA / "comparacao_abre.md").write_text("\n".join(A) + "\n", encoding="utf-8")


# 4. Cobertura do intervalo antes e depois (os intervalos com repositórios usam o surgimento e a parada)
def cobertura(t: pd.DataFrame, ks: list[int], limites: tuple[str, str]) -> tuple[int, int, float]:
    p = t[t["k"].isin(ks)].pivot(index="k", columns="metodo", values="previsto")
    real = t[t["k"].isin(ks)].drop_duplicates("k").set_index("k")["real"]
    dentro = (p[limites[0]] <= real) & (real <= p[limites[1]])
    largura = (p[limites[1]] - p[limites[0]]) / p["ingenua"]
    return int(dentro.sum()), len(ks), float(largura.median())


V = [
    "# Cobertura do intervalo pessimista a otimista antes e depois",
    "",
    "| Linguagem | Sem repositórios, antes | Sem, depois | Com repositórios, antes | Com, depois | Largura sem, antes | Largura sem, depois | Largura com, antes | Largura com, depois |",
    "|---|---|---|---|---|---|---|---|---|",
]
for lingua in LINGUAS:
    sa, ca = (
        cobertura(antes[lingua], ks_antes[lingua], SEM),
        cobertura(antes[lingua], ks_antes[lingua], COM),
    )
    sd, cd = (
        cobertura(depois[lingua], ks_depois[lingua], SEM),
        cobertura(depois[lingua], ks_depois[lingua], COM),
    )
    V.append(
        f"| {NOMES[lingua]} | {sa[0]} de {sa[1]} | {sd[0]} de {sd[1]} | {ca[0]} de {ca[1]} | {cd[0]} de {cd[1]} | {dec(sa[2])} | {dec(sd[2])} | {dec(ca[2])} | {dec(cd[2])} |"
    )
V.append("")
(SAIDA / "cobertura_antes_depois.md").write_text("\n".join(V) + "\n", encoding="utf-8")

# 5. A origem de 31/03/2011 de Clojure
d = pd.read_csv(ANTES / "clojure_S4_detalhe.csv.gz")
ing = d[d["metodo"] == "Ingênua"].groupby(["origem", "faixa"])["pessoas_na_faixa_origem"].sum()
coorte = d[d["metodo"] == "Coorte"].set_index(["origem", "faixa"])["taxa_permanencia"]
origens_k = sorted(d["origem"].unique())
t_antes = antes["clojure"]
ok = definidas(t_antes)
mapa_origem = t_antes.drop_duplicates("k").set_index("k")["origem"].dt.strftime("%Y-%m-%d")
projeta = {mapa_origem.loc[k]: bool(v) for k, v in ok.items()}
E = [
    "# A origem de 31/03/2011 de Clojure",
    "",
    "Em cada origem, a Coorte leva cada faixa para a seguinte com a taxa de permanência da faixa: quem está na faixa f+1 agora dividido por quem estava na faixa f um trimestre antes. A faixa mais velha da pirâmide só tem gente agora porque alguém envelheceu até ela, então um trimestre antes ela estava vazia e a taxa fica indefinida. Faixa com gente e sem taxa deixa a projeção indefinida (`avanca` multiplica por NaN). A faixa aberta (96 meses ou mais) é a exceção: o denominador é quem estava nela (e na anterior) um trimestre antes, e o mais velho deixa de entrar numa faixa nova a cada trimestre. Quando ela tem gente em dois trimestres seguidos, a faixa mais velha passa a ter taxa em todas as origens seguintes.",
    "",
    "| Origem | Cinco métodos projetam? | Faixa mais velha (meses) | Pessoas nela | Pessoas nela um trimestre antes | Taxa da faixa mais velha |",
    "|---|---|---|---|---|---|",
]
for i, o in enumerate(origens_k):
    if not ("2010-09-30" <= o <= "2011-12-31" or "2016-03-31" <= o <= "2016-12-31"):
        continue
    por_faixa = ing.loc[o]
    velha = int(por_faixa[por_faixa > 0].index.max())
    antes_n = ing.loc[origens_k[i - 1]].get(velha, 0) if i > 0 else 0
    taxa = coorte.get((o, velha), np.nan)
    rotulo = f"{3 * velha}+" if velha == 32 else f"{3 * velha} a {3 * velha + 3}"
    E.append(
        f"| {o} | {'sim' if projeta[o] else 'não'} | {rotulo} | {int(por_faixa[velha])} | {int(antes_n)} | {dec(taxa, 2)} |"
    )
E += [
    "",
    "Conclusão numérica: em 31/03/2011 a faixa mais velha (33 a 36 meses) já tinha uma pessoa em 31/12/2010, porque a idade com desconto não avança em trimestre de pausa. Isso deu taxa à faixa e deixou os cinco métodos projetarem. Em 30/06/2011 a faixa mais velha passa a ser a de 36 a 39 meses, vazia um trimestre antes, e a projeção fica indefinida. O mesmo se repete a cada trimestre até a faixa aberta ter gente (30/09/2016).",
    "",
]
(SAIDA / "origem_2011_clojure.md").write_text("\n".join(E) + "\n", encoding="utf-8")
print("\n".join(ORIGENS))
print("\n".join(E[:30]))
print("\n".join(V))
