"""ABRE médio e mediano por linguagem, método e cenário (S1, S3h, S4, S5, S2), mais o Wilcoxon pareado contra Ingênua e contra Coorte.

Lê `<pasta>/unidades/<l>_<cenario>_pares.csv.gz` e `_R3_pares.csv.gz` de cada cenário. Não interpreta nada.

Origens de cada cenário (cada método precisa ter ABRE definido):
  S1, S3h, S5 (todas): todo recorte trimestral de 2017 em diante.
  S4, S2, S5 (dezembro): só dezembro de 2017 em diante.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/resumo_s1_a_s5.py <saida> S1=<pasta> S3h=<pasta> S4=<pasta> S5=<pasta> S2=<pasta>
"""

import sys
from pathlib import Path

import pandas as pd
from scipy.stats import wilcoxon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tabelas_cenarios import COLUNAS, LINGUAS, METODOS, NOMES, carrega, num3, origens, rotulo

SAIDA = Path(sys.argv[1])
SAIDA.mkdir(parents=True, exist_ok=True)
PASTAS: dict[str, Path] = {}
for argumento in sys.argv[2:]:
    nome, pasta = argumento.split("=")
    PASTAS[nome] = Path(pasta)


def teste(a: pd.Series, b: pd.Series) -> dict:
    diferenca = a.to_numpy() - b.to_numpy()
    n_dif = int((diferenca != 0).sum())
    if n_dif == 0:
        return {"pares": len(a), "dif": 0, "p": float("nan"), "vitorias": 0}
    try:
        p = float(wilcoxon(a.to_numpy(), b.to_numpy(), method="exact").pvalue)
    except ValueError:
        p = float(wilcoxon(a.to_numpy(), b.to_numpy()).pvalue)
    return {"pares": len(a), "dif": n_dif, "p": p, "vitorias": int((diferenca < 0).sum())}


linhas = []
testes = []
for lingua in LINGUAS:
    for cenario, so_dezembro in COLUNAS:
        if cenario not in PASTAS:
            continue
        abre = carrega(PASTAS, cenario, lingua)
        if abre is None:
            continue
        d = origens(abre, so_dezembro)
        if d.empty:
            continue
        nome = rotulo(cenario, so_dezembro)
        for metodo, rotulo_metodo in METODOS.items():
            linhas.append(
                {
                    "linguagem": lingua,
                    "metodo": rotulo_metodo,
                    "cenario": nome,
                    "origens": len(d),
                    "primeira": d["origem"].min().date().isoformat(),
                    "ultima": d["origem"].max().date().isoformat(),
                    "abre_medio": d[metodo].mean(),
                    "abre_mediano": d[metodo].median(),
                }
            )
            for base, rotulo_base in (("ingenua", "Ingênua"), ("coorte_R0", "Coorte")):
                if metodo == base:
                    continue
                testes.append(
                    {
                        "linguagem": lingua,
                        "cenario": nome,
                        "metodo": rotulo_metodo,
                        "contra": rotulo_base,
                        **teste(d[metodo], d[base]),
                    }
                )

abre_csv = pd.DataFrame(linhas)
abre_csv.to_csv(SAIDA / "abre_por_cenario.csv", index=False)
pd.DataFrame(testes).to_csv(SAIDA / "wilcoxon_por_cenario.csv", index=False)

colunas_nome = [rotulo(c, d) for c, d in COLUNAS if c in PASTAS]
texto = [
    "# ABRE médio / mediano por linguagem, método e cenário",
    "",
    "Cada célula mostra média / mediana do ABRE sobre as origens do cenário. Origens: S1, S3h e S5 em todo trimestre a partir de 2017; S4, S2 e S5 (dezembro) só em dezembro a partir de 2017. Só entram origens em que os cinco métodos têm ABRE definido.",
    "",
]
for lingua in LINGUAS:
    sub = abre_csv[abre_csv["linguagem"] == lingua]
    if sub.empty:
        continue
    texto += [
        f"## {NOMES[lingua]}",
        "",
        "| Método | " + " | ".join(colunas_nome) + " |",
        "|---|" + "---|" * len(colunas_nome),
    ]
    origens_linha = []
    for c in colunas_nome:
        s = sub[sub["cenario"] == c]
        origens_linha.append(f"{int(s['origens'].iloc[0])}" if len(s) else "n/d")
    texto.append("| Origens | " + " | ".join(origens_linha) + " |")
    for rotulo_metodo in METODOS.values():
        celulas = []
        for c in colunas_nome:
            s = sub[(sub["cenario"] == c) & (sub["metodo"] == rotulo_metodo)]
            celulas.append(
                f"{num3(s['abre_medio'].iloc[0])} / {num3(s['abre_mediano'].iloc[0])}"
                if len(s)
                else "n/d"
            )
        texto.append(f"| {rotulo_metodo} | " + " | ".join(celulas) + " |")
    texto.append("")
(SAIDA / "abre_por_cenario.md").write_text("\n".join(texto) + "\n", encoding="utf-8")

t = pd.DataFrame(testes)
saida = [
    "# Wilcoxon pareado (exato, bicaudal) sobre o ABRE, sem correção para comparações múltiplas",
    "",
    "Pares: as origens do cenário. No S5 com todos os trimestres, pares de origens vizinhas são dependentes (a janela do alvo compartilha 9 dos 12 meses), então o p descreve e não vale como teste. Vitórias: origens em que o método errou menos que a base.",
    "",
    "| Linguagem | Cenário | Método | Contra | Pares (com diferença) | p | Vitórias |",
    "|---|---|---|---|---|---|---|",
]
for _, x in t.iterrows():
    p = (
        "n/d"
        if pd.isna(x["p"])
        else (f"{x['p']:.1e}".replace(".", ",") if x["p"] < 0.001 else num3(x["p"]))
    )
    saida.append(
        f"| {NOMES[x['linguagem']]} | {x['cenario']} | {x['metodo']} | {x['contra']} | {x['pares']} ({x['dif']}) | {p} | {x['vitorias']} de {x['pares']} |"
    )
(SAIDA / "wilcoxon_por_cenario.md").write_text("\n".join(saida) + "\n", encoding="utf-8")
print("\n".join(texto))
