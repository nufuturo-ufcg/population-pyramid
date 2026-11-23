"""Tabela de impacto da regra nova de elegibilidade, antes de reprocessar (item 3 de `projecao-rq3/correcao-elegibilidade/hipoteses.md`).

Lê em `<pasta>/dados/`: `candidatos_compacto.csv`, `consulta_languages.csv` (a consulta da API, as duas máquinas juntas), `datas_<lang>.csv` (primeiro e último evento
por repositório no arquivo bruto) e `copiados_python.csv` (commits com SHA em outro repositório). Lê também `verificacao-python/nascimento.csv`
e `projecao-rq3/investigacao/repos_por_ano.csv` (valores exatos da carga atual).
Grava `<pasta>/impacto.csv` e `<pasta>/tabelas.md`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/impacto_elegibilidade.py <correcao-elegibilidade> <projecao-rq3>
"""

import sys
from pathlib import Path

import pandas as pd

PASTA = Path(sys.argv[1])
RQ3 = Path(sys.argv[2])
DADOS = PASTA / "dados"
LINGUAS = ["clojure", "elixir", "ocaml", "python", "zig"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "ocaml": "OCaml",
    "python": "Python",
    "zig": "Zig",
}
ELEGIVEL = "com a linguagem acima de 50%"
COMMITS = (PASTA / "commit.txt").read_text(encoding="utf-8").strip().splitlines()


def milhar(n: float) -> str:
    return f"{int(n):,}".replace(",", ".")


def pct(x: float) -> str:
    return "n/d" if pd.isna(x) else f"{100 * x:.1f}%".replace(".", ",")


cand = pd.read_csv(DADOS / "candidatos_compacto.csv", dtype={"repo_id": str})
cand["ano_push"] = pd.to_datetime(cand["pushedAt"], errors="coerce").dt.year
api = pd.read_csv(DADOS / "consulta_languages.csv", dtype={"repo_id": str}, keep_default_na=False)
# a última linha de cada (linguagem, repo_id) vale (reexecução de erro transitório)
api = api.drop_duplicates(["linguagem", "repo_id"], keep="last")
api["http_status"] = api["http_status"].astype(int)
api["fracao"] = pd.to_numeric(api["fracao_linguagem_alvo"], errors="coerce")

cand = cand.merge(
    api[["linguagem", "repo_id", "http_status", "fracao"]], on=["linguagem", "repo_id"], how="left"
)
cand["elegivel_antes"] = cand["categoria"] == ELEGIVEL
cand["vazio"] = cand["categoria"] == "vazia"


def resultado_da_api(x: pd.Series) -> str:
    if not x["vazio"]:
        return ""
    if pd.isna(x["http_status"]):
        return "sem resposta"
    status = int(x["http_status"])
    if status == 200:
        if pd.isna(x["fracao"]):
            return "API sem bytes"
        return "entra (mais de 50%)" if x["fracao"] > 0.5 else "fora (50% ou menos)"
    if status in (404, 403, 451):
        return f"erro {status}"
    return "outro erro"


cand["resultado_api"] = cand.apply(resultado_da_api, axis=1)
cand["elegivel_depois"] = cand["elegivel_antes"] | (cand["resultado_api"] == "entra (mais de 50%)")

T = ["# Tabelas da correção da elegibilidade, antes de reprocessar", ""]
T += [f"Código: commit `{c}`." for c in COMMITS] + [""]

# ---- tabela 1: elegíveis antes e depois
RESULTADOS = [
    "entra (mais de 50%)",
    "fora (50% ou menos)",
    "API sem bytes",
    "erro 404",
    "erro 403",
    "erro 451",
    "outro erro",
    "sem resposta",
]
T += [
    "## 1. Elegíveis antes e depois",
    "",
    "Vazio: coluna `languages` da SEART vazia. Regra nova: mais de 50% do código na linguagem, pela SEART quando ela tem o dado e pela API quando a SEART está vazia.",
    "",
]
T += ["| Linguagem | Candidatos | Elegíveis antes | Vazios | Entram pela API | Fora: 50% ou menos | Fora: API sem bytes | Fora: 404 | Fora: 403 | Fora: 451 | Fora: outro erro | Sem resposta | Elegíveis depois | Variação |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
linhas_csv = []
for lingua in LINGUAS:
    g = cand[cand["linguagem"] == lingua]
    contagem = g[g["vazio"]]["resultado_api"].value_counts()
    antes, depois = int(g["elegivel_antes"].sum()), int(g["elegivel_depois"].sum())
    celulas = [NOMES[lingua], milhar(len(g)), milhar(antes), milhar(g["vazio"].sum())]
    for r in RESULTADOS:
        celulas.append(milhar(contagem.get(r, 0)))
    celulas += [milhar(depois), pct(depois / antes - 1)]
    T.append("| " + " | ".join(celulas) + " |")
    linhas_csv.append({"linguagem": lingua, "candidatos": len(g), "elegiveis_antes": antes, "elegiveis_depois": depois, **{r: int(contagem.get(r, 0)) for r in RESULTADOS}})  # fmt: skip
pd.DataFrame(linhas_csv).to_csv(PASTA / "impacto.csv", index=False)
T.append("")

# ---- tabela 2: os que entram pela API, por ano do último push
entram = cand[cand["resultado_api"] == "entra (mais de 50%)"]
T += ["## 2. Os que entram pela API, por ano do último push da SEART", ""]
T += [
    "| Ano do último push | " + " | ".join(NOMES[x] for x in LINGUAS) + " |",
    "|---|" + "---|" * len(LINGUAS),
]
for ano in [*range(2008, 2027), "sem data"]:
    celulas = [str(ano)]
    for lingua in LINGUAS:
        g = entram[entram["linguagem"] == lingua]
        n = (
            int(g["ano_push"].isna().sum())
            if ano == "sem data"
            else int((g["ano_push"] == ano).sum())
        )
        celulas.append(milhar(n))
    if ano == "sem data" and all(c == "0" for c in celulas[1:]):
        continue
    T.append("| " + " | ".join(celulas) + " |")
T.append("")

# ---- tabela 3: último evento até 2020 e parada até 3 anos depois de nascer
datas = {}
for lingua in LINGUAS:
    d = pd.read_csv(DADOS / f"datas_{lingua}.csv", dtype={"repo_id": str})
    d["ano_primeiro"] = d["primeiro"].str[:4].astype(int)
    d["ano_ultimo"] = d["ultimo"].str[:4].astype(int)
    datas[lingua] = d.set_index("repo_id")


def medidas(lingua: str, ids: set[str]) -> tuple[int, float, int, float]:
    """Repositórios com evento, fração com último evento até 2020, nascidos de 2008 a 2020 e fração que parou até 3 anos depois."""
    d = datas[lingua]
    d = d[d.index.isin(ids)]
    nascidos = d[(d["ano_primeiro"] >= 2008) & (d["ano_primeiro"] <= 2020)]
    pararam = (nascidos["ano_ultimo"] <= nascidos["ano_primeiro"] + 3).sum()
    ate_2020 = (d["ano_ultimo"] <= 2020).mean() if len(d) else float("nan")
    return (
        len(d),
        float(ate_2020),
        len(nascidos),
        float(pararam / len(nascidos)) if len(nascidos) else float("nan"),
    )


nascimento = pd.read_csv(RQ3 / "verificacao-python" / "nascimento.csv")
exatos = pd.read_csv(RQ3 / "investigacao" / "repos_por_ano.csv")
T += ["## 3. Último evento até 2020 e parada até 3 anos depois de nascer", ""]
T += [
    "- **Carga atual (exato):** `verificacao-python/` e `investigacao/` (último evento até 2020 sobre todos os repositórios com evento; nascidos de 2008 a 2020 e fração com o último evento até 3 anos depois).",
    "- **Antes (estimativa):** os elegíveis de hoje, com o primeiro e o último evento do arquivo bruto, sem os filtros da carga de commit copiado e identidade (tira conta apagada, bot e datas fora de 2008 até hoje).",
    "- **Depois (estimativa):** os elegíveis pela regra nova, com a mesma estimativa. A carga nova do item 4 dá o valor exato.",
    "",
]
T += ["| Linguagem | Carga atual: último evento até 2020 | Antes (estimativa): repos | Antes: até 2020 | Depois (estimativa): repos | Depois: até 2020 | Carga atual: nascidos 2008 a 2020 parados até 3 anos | Antes: nascidos | Antes: parados até 3 anos | Depois: nascidos | Depois: parados até 3 anos |", "|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
for lingua in LINGUAS:
    g = cand[cand["linguagem"] == lingua]
    ids_antes = set(g[g["elegivel_antes"]]["repo_id"])
    ids_depois = set(g[g["elegivel_depois"]]["repo_id"])
    n_a, ate_a, nasc_a, par_a = medidas(lingua, ids_antes)
    n_d, ate_d, nasc_d, par_d = medidas(lingua, ids_depois)
    e = exatos[(exatos["linguagem"] == lingua) & (exatos["ano"] <= 2026)]
    ate_exato = float("nan")  # `repos_por_ano.csv` não tem Zig
    if len(e):
        ate_exato = e[e["ano"] <= 2020]["repos_ultimo_evento"].sum() / int(
            e["repos_total_na_carga"].iloc[0]
        )
    n = nascimento[(nascimento["linguagem"] == lingua) & (nascimento["ano_nascimento"] <= 2020)]
    par_exato = n["ultimo_evento_ate_3_anos"].sum() / n["repos"].sum()
    T.append(
        f"| {NOMES[lingua]} | {pct(ate_exato)} | {milhar(n_a)} | {pct(ate_a)} | {milhar(n_d)} | {pct(ate_d)} | {pct(par_exato)} | {milhar(nasc_a)} | {pct(par_a)} | {milhar(nasc_d)} | {pct(par_d)} |"
    )
T.append("")

# Python por ano de nascimento, antes e depois (estimativa)
T += ["### Python por ano de nascimento (estimativa)", "", "| Ano de nascimento | Antes: nasceram | Antes: fração com último evento até 3 anos depois | Depois: nasceram | Depois: fração |", "|---|---|---|---|---|"]  # fmt: skip
g = cand[cand["linguagem"] == "python"]
d_py = datas["python"]
for nome_conjunto, ids in [
    ("antes", set(g[g["elegivel_antes"]]["repo_id"])),
    ("depois", set(g[g["elegivel_depois"]]["repo_id"])),
]:
    d = d_py[d_py.index.isin(ids)]
    datas[f"python_{nome_conjunto}"] = d
for ano in range(2008, 2021):
    celulas = [str(ano)]
    for nome_conjunto in ("antes", "depois"):
        d = datas[f"python_{nome_conjunto}"]
        nasc = d[d["ano_primeiro"] == ano]
        celulas.append(milhar(len(nasc)))
        celulas.append(pct((nasc["ano_ultimo"] <= ano + 3).mean()) if len(nasc) else "n/d")
    T.append("| " + " | ".join(celulas) + " |")
T.append("")

# ---- tabela 4: candidatos a duplicado entre os que entram pela API (Python)
copiados = pd.read_csv(DADOS / "copiados_python.csv", dtype={"repo_id": str}).set_index("repo_id")
copiados["fracao_copiada"] = copiados["commits_copiados"] / copiados["commits"]
T += ["## 4. Candidatos a duplicado em Python", "", "Repositório com 5 commits ou mais e 90% ou mais dos commits com o mesmo SHA em outro repositório do arquivo bruto. É um indicador de cópia de histórico (fork ou clone empurrado), e não a auditoria de duplicados da rodada oficial, que compara issues e PRs.", ""]  # fmt: skip
T += [
    "| Grupo | Repositórios | Com commits no arquivo | Candidatos a duplicado | Fração |",
    "|---|---|---|---|---|",
]
for nome, ids in [
    ("Elegíveis antes", set(g[g["elegivel_antes"]]["repo_id"])),
    ("Entram pela API", set(g[g["resultado_api"] == "entra (mais de 50%)"]["repo_id"])),
]:
    c = copiados[copiados.index.isin(ids)]
    candidatos = c[(c["commits"] >= 5) & (c["fracao_copiada"] >= 0.9)]
    T.append(
        f"| {nome} | {milhar(len(ids))} | {milhar(len(c))} | {milhar(len(candidatos))} | {pct(len(candidatos) / len(c)) if len(c) else 'n/d'} |"
    )
T.append("")

(PASTA / "tabelas.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T[:30]))
