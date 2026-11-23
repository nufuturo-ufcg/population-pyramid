"""Testes adicionais do S2 para a RQ3, a partir das previsões já salvas em `projecao-rq3/unidades/`.

Wilcoxon pareado bicaudal exato sobre o ABRE, sem correção para comparações múltiplas.
Origens comuns: as de dezembro em que todos os 13 métodos (ingênua e coorte, conservador e C3 em R0 a R3) têm ABRE definido.
Confere o ABRE salvo em `projecao-cenarios-ieice/unidades/` quando o método existe lá.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/testes_s2.py <projecao-rq3> <projecao-cenarios-ieice>
"""

import sys
from pathlib import Path

import pandas as pd
from scipy.stats import wilcoxon

RQ3 = Path(sys.argv[1])
IEICE = Path(sys.argv[2])
LINGUAS = ["clojure", "elixir", "ocaml", "python"]
NOMES = {"clojure": "Clojure", "elixir": "Elixir", "ocaml": "OCaml", "python": "Python"}
FAMILIAS = [("coorte", "Coorte"), ("conservador", "Conservador"), ("C3", "C3")]
ROTULO = {"ingenua": "Ingênua"}
for base, nome in FAMILIAS:
    for r in range(4):
        ROTULO[f"{base}_R{r}"] = f"{nome} em R{r}"
METODOS = list(ROTULO)


def carrega(pasta: Path, lingua: str) -> pd.DataFrame:
    partes = [pd.read_csv(pasta / "unidades" / f"{lingua}_S2_pares.csv.gz")]
    for r in (1, 2, 3):
        partes.append(pd.read_csv(pasta / "unidades" / f"{lingua}_S2_R{r}_pares.csv.gz"))
    return pd.concat(partes, ignore_index=True)


def num4(x: float) -> str:
    return f"{x:.4f}".replace(".", ",")


def teste(a: pd.Series, b: pd.Series) -> dict:
    """Estatística, p exato, pares, menor p possível e anos em que `a` errou menos que `b`."""
    diferenca = a.to_numpy() - b.to_numpy()
    n_dif = int((diferenca != 0).sum())
    r = wilcoxon(a.to_numpy(), b.to_numpy(), method="exact")
    return {
        "pares": len(a),
        "dif": n_dif,
        "estatistica": float(r.statistic),
        "p": float(r.pvalue),
        "menor_p": 2.0 / 2.0**n_dif,
        "vitorias": int((diferenca < 0).sum()),
    }


def linha_teste(nome: str, t: dict) -> str:
    pares = (
        str(t["pares"]) if t["dif"] == t["pares"] else f"{t['pares']} ({t['dif']} com diferença)"
    )
    return (
        f"| {nome} | {pares} | {t['estatistica']:g} | {num4(t['p'])} | {num4(t['menor_p'])} "
        f"| {t['vitorias']} de {t['pares']} |"
    )


COMPARACOES_2 = [
    ("C3 R0 contra ingênua", "C3_R0", "ingenua"),
    ("C3 R0 contra coorte R0", "C3_R0", "coorte_R0"),
    ("C3 R3 contra coorte R3", "C3_R3", "coorte_R3"),
]

saida = []
csv = []
medidas = []
conferencia = []
origens_usadas = {}

for lingua in LINGUAS:
    t = carrega(RQ3, lingua)
    abre = t.pivot(index="k", columns="metodo", values="abre")[METODOS]
    origem = t[t["metodo"] == "ingenua"].set_index("k")["origem"]
    base = abre.notna().all(axis=1)
    d = abre[base]
    datas = origem[d.index].tolist()
    origens_usadas[lingua] = f"{datas[0]} a {datas[-1]} ({len(d)})"

    # Confere com o ABRE salvo em projecao-cenarios-ieice (mesmas origens, mesmos métodos).
    outro = carrega(IEICE, lingua).pivot(index="k", columns="metodo", values="abre")
    diferenca_max = 0.0
    comparados = []
    for m in METODOS:
        if m in outro.columns:
            comparados.append(m)
            dif = (outro.loc[d.index, m] - d[m]).abs().max()
            diferenca_max = max(diferenca_max, float(dif))
    conferencia.append(
        f"- {NOMES[lingua]}: {len(comparados)} métodos presentes nas duas pastas, diferença máxima do ABRE {diferenca_max:.2g}."
    )

    saida.append(f"## {NOMES[lingua]}")
    saida.append("")
    saida.append(f"Origens: {origens_usadas[lingua]}.")
    saida.append("")

    saida.append("### 1. Previsão de repositórios contra R0")
    saida.append("")
    saida.append(
        "| Comparação | Pares | Estatística | p exato | Menor p possível | Anos em que o primeiro errou menos |"
    )
    saida.append("|---|---|---|---|---|---|")
    for base_nome, nome in FAMILIAS:
        for r in (1, 2, 3):
            res = teste(d[f"{base_nome}_R{r}"], d[f"{base_nome}_R0"])
            saida.append(linha_teste(f"{nome} R{r} contra R0", res))
            csv.append(
                {
                    "linguagem": lingua,
                    "grupo": "R contra R0",
                    "comparacao": f"{nome} R{r} contra R0",
                    **res,
                }
            )
    saida.append("")

    saida.append("### 2. Combinação")
    saida.append("")
    saida.append(
        "| Comparação | Pares | Estatística | p exato | Menor p possível | Anos em que o primeiro errou menos |"
    )
    saida.append("|---|---|---|---|---|---|")
    for nome, a, b in COMPARACOES_2:
        res = teste(d[a], d[b])
        saida.append(linha_teste(nome, res))
        csv.append({"linguagem": lingua, "grupo": "combinação", "comparacao": nome, **res})
    saida.append("")

    for base_nome, nome in FAMILIAS:
        linha = [NOMES[lingua], nome]
        for r in range(4):
            col = d[f"{base_nome}_R{r}"]
            linha.append(f"{num4(col.mean())} / {num4(col.median())}")
        medidas.append(linha)

cabeca = [
    "# Testes adicionais do S2 (RQ3)",
    "",
    f"Código das previsões: commit `{(RQ3 / 'commit.txt').read_text(encoding='utf-8').strip()}`.",
    "Previsões lidas de `projecao-rq3/unidades/`. Nada foi rodado de novo, porque os 13 métodos já existiam nas origens comuns.",
    'Teste: Wilcoxon pareado bicaudal exato (`scipy.stats.wilcoxon`, `method="exact"`) sobre o ABRE, sem correção para comparações múltiplas.',
    "Estatística: o menor entre a soma dos postos positivos e a dos negativos. Menor p possível: 2 dividido por 2 elevado ao número de pares com diferença.",
    "Pares: origens de dezembro em que ingênua, coorte, conservador e C3 em R0 a R3 têm ABRE definido.",
    "Coorte R0 é a coorte V0, conservador R0 é o conservador V0 e C3 R0 é a média da ingênua com a coorte V0.",
    "",
    "Origens usadas:",
    "",
]
for lingua in LINGUAS:
    cabeca.append(f"- {NOMES[lingua]}: {origens_usadas[lingua]}.")
cabeca.append("")
cabeca.append("Conferência contra `projecao-cenarios-ieice/unidades/`:")
cabeca.append("")
cabeca.extend(conferencia)
cabeca.append("")

tabela_medidas = [
    "## ABRE médio / mediano por linguagem",
    "",
    "| Linguagem | Método | R0 | R1 | R2 | R3 |",
    "|---|---|---|---|---|---|",
]
for linha in medidas:
    tabela_medidas.append("| " + " | ".join(linha) + " |")
tabela_medidas.append("")
tabela_medidas.append("Ingênua, no mesmo conjunto de origens:")
tabela_medidas.append("")
tabela_medidas.append("| Linguagem | Média / mediana |")
tabela_medidas.append("|---|---|")
for lingua in LINGUAS:
    t = carrega(RQ3, lingua)
    abre = t.pivot(index="k", columns="metodo", values="abre")[METODOS]
    col = abre[abre.notna().all(axis=1)]["ingenua"]
    tabela_medidas.append(f"| {NOMES[lingua]} | {num4(col.mean())} / {num4(col.median())} |")
tabela_medidas.append("")

texto = "\n".join(cabeca + tabela_medidas + saida) + "\n"
(RQ3 / "testes_s2.md").write_text(texto, encoding="utf-8")
pd.DataFrame(csv).to_csv(RQ3 / "testes_s2.csv", index=False)
print(texto)
