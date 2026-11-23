"""Seções 8 e 9 da tabela de impacto (`correcao-elegibilidade/tabelas.md`), com a carga nova (`-v3`).

8. Linhas repetidas: quantas das 3.707 saíram da carga e de quais repositórios (`linhas_repetidas.csv` da carga).
9. Valores exatos da carga nova contra a antiga, por linguagem, e contra a estimativa da seção 3.

Lê em `<pasta>/dados/`: `carga-v3/{antiga,nova}/<linguagem>.json`, `carga-v3/linhas_repetidas_python.csv`,
`candidatos_compacto.csv` e `verificacao-v3/nascimento.csv` (cópia do que `verificacao_lista.py` gerou com a carga nova).
Lê também `<projecao-rq3>/verificacao-python/nascimento.csv` e `investigacao/repos_por_ano.csv` (carga antiga) e
`<projecao-rq3-v3>/investigacao-v3/repos_por_ano.csv` (carga nova).
Grava `<pasta>/linhas_repetidas_por_repo.csv` e acrescenta as seções à `tabelas.md`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/impacto_v3.py <correcao-elegibilidade> <projecao-rq3> <projecao-rq3-v3>
"""

import csv
import json
import sys
from pathlib import Path

import pandas as pd

PASTA, RQ3, RQ3_V3 = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
DADOS = PASTA / "dados"
CARGA = DADOS / "carga-v3"
LINGUAS = ["clojure", "elixir", "ocaml", "python", "zig"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "ocaml": "OCaml",
    "python": "Python",
    "zig": "Zig",
}


def milhar(n: float) -> str:
    return f"{int(n):,}".replace(",", ".")


def pct(x: float) -> str:
    return "n/d" if pd.isna(x) else f"{100 * x:.1f}%".replace(".", ",")


def antigo_novo(a: float | None, b: float | None) -> str:
    if a is None and b is None:
        return "n/d"
    if a == b:
        return milhar(a)
    texto_a = "n/d" if a is None else milhar(a)
    texto_b = "n/d" if b is None else milhar(b)
    return f"{texto_a} → {texto_b}"


nomes = {}
with (DADOS / "candidatos_compacto.csv").open(encoding="utf-8", newline="") as arquivo:
    for linha in csv.DictReader(arquivo):
        if linha["linguagem"] == "python":
            nomes[linha["repo_id"]] = linha["repo_name"]

# ---- seção 8: linhas repetidas
repetidas = pd.read_csv(CARGA / "linhas_repetidas_python.csv", dtype={"repo_id": str})
repetidas.insert(1, "repo_name", repetidas["repo_id"].map(nomes))
repetidas.to_csv(PASTA / "linhas_repetidas_por_repo.csv", index=False)
nova = json.loads((CARGA / "nova" / "python.json").read_text(encoding="utf-8"))
antiga = json.loads((CARGA / "antiga" / "python.json").read_text(encoding="utf-8"))
api_removidas = int(nova["linhas_repetidas_descartadas_api"])
git_removidas = int(nova["linhas_repetidas_descartadas_git"])
COMMITS_REPETIDOS, API_REPETIDAS, TIPO_INVALIDO = 3090, 616, 3
descartava_git = git_removidas
T = [
    "## 8. Linhas repetidas na carga nova (Python)",
    "",
    "Chave do evento: todas as colunas menos `collection_started_at`. A regra nova (`sem_linhas_repetidas`) vale só em Python e só na carga. Os arquivos brutos não foram tocados.",
    "",
    "| Grupo | Linhas |",
    "|---|---|",
    f"| Repetidas no arquivo final (soma das partes, 3.709; no final 3.707 porque as linhas de tipo inválido se leem diferente) | {milhar(COMMITS_REPETIDOS + API_REPETIDAS + TIPO_INVALIDO)} |",
    f"| Commits repetidos | {milhar(COMMITS_REPETIDOS)} |",
    f"| Commits repetidos que a carga antiga já descartava pelo SHA (os que passam os filtros de linguagem e autor) | {milhar(descartava_git)} |",
    f"| Commits repetidos que já saíam antes, pelos filtros de linguagem e autor | {milhar(COMMITS_REPETIDOS - descartava_git)} |",
    f"| Linhas de API repetidas | {milhar(API_REPETIDAS)} |",
    f"| Linhas de API repetidas que saem só pela regra nova | {milhar(api_removidas)} |",
    f"| Linhas de API repetidas que já saíam antes, pelos filtros de linguagem e autor | {milhar(API_REPETIDAS - api_removidas)} |",
    f"| Linhas de tipo de evento inválido (só na `parte1c`) | {TIPO_INVALIDO} |",
    f"| Linhas de tipo inválido que chegaram ao fim da carga | {milhar(nova.get('eventos_tipo_invalido_descartados', 0))} |",
    "",
    f"Saíram {milhar(api_removidas)} linhas de API pela regra nova, em {milhar(int((repetidas['papel'] == 'api').sum()))} repositórios. A lista completa, com `repo_id`, nome e papel (`api` ou `git`), está em `linhas_repetidas_por_repo.csv`. Os 10 repositórios com mais linhas:",
    "",
    "| Repositório | Papel | Linhas que saíram |",
    "|---|---|---|",
]
maiores = repetidas.sort_values("descartadas", ascending=False).head(10)
for _, linha in maiores.iterrows():
    T.append(
        f"| {linha['repo_name']} ({linha['repo_id']}) | {linha['papel']} | {milhar(linha['descartadas'])} |"
    )
T.append("")

# ---- seção 9: valores exatos
T += [
    "## 9. Valores exatos da carga nova contra a antiga",
    "",
    "Cada célula mostra `antigo → novo` (igual aparece uma vez). Zig e as três linguagens de nicho não mudam, pois nenhum vazio delas entra pela API.",
    "",
    "| Linguagem | Repositórios elegíveis | Repositórios com evento | Contribuidores | Eventos finais |",
    "|---|---|---|---|---|",
]
for lingua in LINGUAS:
    a = json.loads((CARGA / "antiga" / f"{lingua}.json").read_text(encoding="utf-8"))
    n = json.loads((CARGA / "nova" / f"{lingua}.json").read_text(encoding="utf-8"))
    T.append(
        f"| {NOMES[lingua]} | {antigo_novo(a.get('repos_elegiveis'), n.get('repos_elegiveis'))}"
        f" | {antigo_novo(a.get('repos_finais'), n.get('repos_finais'))}"
        f" | {antigo_novo(a.get('contribuidores_finais'), n.get('contribuidores_finais'))}"
        f" | {antigo_novo(a.get('eventos_finais'), n.get('eventos_finais'))} |"
    )
T.append("")

nasc_antigo = pd.read_csv(RQ3 / "verificacao-python" / "nascimento.csv")
nasc_novo = pd.read_csv(DADOS / "verificacao-v3" / "nascimento.csv")
exatos_antigo = pd.read_csv(RQ3 / "investigacao" / "repos_por_ano.csv")
exatos_novo = pd.read_csv(RQ3_V3 / "investigacao-v3" / "repos_por_ano.csv")


def ultimo_ate_2020(tabela: pd.DataFrame, lingua: str) -> float:
    e = tabela[(tabela["linguagem"] == lingua) & (tabela["ano"] <= 2026)]
    if not len(e):
        return float("nan")
    return float(
        e[e["ano"] <= 2020]["repos_ultimo_evento"].sum() / int(e["repos_total_na_carga"].iloc[0])
    )


def parada_3_anos(tabela: pd.DataFrame, lingua: str) -> tuple[int, float]:
    n = tabela[(tabela["linguagem"] == lingua) & (tabela["ano_nascimento"] <= 2020)]
    return int(n["repos"].sum()), float(n["ultimo_evento_ate_3_anos"].sum() / n["repos"].sum())


T += [
    "### Último evento até 2020 e parada até 3 anos depois de nascer (exato)",
    "",
    "A estimativa da seção 3 para Python depois da correção era 16,1% (último evento até 2020) e 35,0% (parada até 3 anos).",
    "",
    "| Linguagem | Último evento até 2020 | Nascidos de 2008 a 2020 | Parados até 3 anos depois |",
    "|---|---|---|---|",
]
for lingua in LINGUAS:
    a_ate, n_ate = ultimo_ate_2020(exatos_antigo, lingua), ultimo_ate_2020(exatos_novo, lingua)
    a_nasc, a_par = parada_3_anos(nasc_antigo, lingua)
    n_nasc, n_par = parada_3_anos(nasc_novo, lingua)
    ate = pct(a_ate) if pd.isna(n_ate) or a_ate == n_ate else f"{pct(a_ate)} → {pct(n_ate)}"
    nasc = milhar(a_nasc) if a_nasc == n_nasc else f"{milhar(a_nasc)} → {milhar(n_nasc)}"
    par = pct(a_par) if a_par == n_par else f"{pct(a_par)} → {pct(n_par)}"
    T.append(f"| {NOMES[lingua]} | {ate} | {nasc} | {par} |")
T.append("")

texto = (PASTA / "tabelas.md").read_text(encoding="utf-8")
corte = texto.find("\n## 8.")
if corte >= 0:
    texto = texto[: corte + 1]
(PASTA / "tabelas.md").write_text(texto.rstrip("\n") + "\n\n" + "\n".join(T), encoding="utf-8")
print("seções 8 e 9 gravadas")
