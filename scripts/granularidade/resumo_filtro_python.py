"""Resumo do diagnóstico do filtro de proporção de código em Python (`projecao-rq3/filtro-python/`). Ver `hipoteses.md`.

Lê os CSV gerados na VM por `filtro_languages.py`, `api_linguagens.py`, `eventos_por_repo.py` e `ritmo_coleta.py`. Grava `tabelas.md` e `resumo.md`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/resumo_filtro_python.py <filtro-python>
"""

import sys
from pathlib import Path

import pandas as pd

PASTA = Path(sys.argv[1])
LINGUAS = ["python", "clojure", "elixir", "ocaml", "zig"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "ocaml": "OCaml",
    "python": "Python",
    "zig": "Zig",
}
CATEGORIAS = [
    "vazia",
    "outro formato",
    "sem a linguagem",
    "com a linguagem abaixo de 50%",
    "com a linguagem acima de 50%",
]
GRUPOS = {
    "nao_elegivel_push_ate_2020": "Não elegíveis, último push até 2020",
    "nao_elegivel_todos": "Não elegíveis, todos",
    "elegivel_amostra": "Elegíveis, amostra de 1.000",
}
COMMITS = (PASTA / "commit.txt").read_text(encoding="utf-8").strip().splitlines()
LIMITE_BRUTO = 300


def milhar(n: float) -> str:
    return f"{int(n):,}".replace(",", ".")


def pct(x: float, casas: int = 1) -> str:
    return f"{100 * x:.{casas}f}%".replace(".", ",")


def bruto(texto: object) -> str:
    """Conteúdo bruto da coluna, com barra vertical escapada e corte em LIMITE_BRUTO caracteres."""
    if not isinstance(texto, str) or texto == "":
        return "(vazio)"
    cortado = texto if len(texto) <= LIMITE_BRUTO else texto[:LIMITE_BRUTO] + "…"
    return "`" + cortado.replace("|", "\\|").replace("`", "'") + "`"


cat = pd.read_csv(PASTA / "categorias.csv")
faixas = pd.read_csv(PASTA / "faixas_participacao.csv")
maior = pd.read_csv(PASTA / "maior_linguagem.csv")
ano = pd.read_csv(PASTA / "por_ano_push.csv")
exemplos = pd.read_csv(PASTA / "exemplos_python.csv", keep_default_na=False)
api = pd.read_csv(PASTA / "api_linguagens.csv", keep_default_na=False)
amostra_api = pd.read_csv(PASTA / "amostra_api.csv", dtype={"repo_id": str})
status = pd.read_csv(PASTA / "status_coleta_python.csv", dtype={"repo_id": str})
ritmo = pd.read_csv(PASTA / "ritmo_coleta_python.csv")
erros = pd.read_csv(PASTA / "erros_nao_elegiveis.csv")
arquivo_eventos = PASTA / "eventos_por_repo_python.csv"
eventos = None
if arquivo_eventos.exists() and arquivo_eventos.stat().st_size > 0:
    eventos = pd.read_csv(arquivo_eventos, dtype={"repo_id": str})

T = ["# Tabelas do diagnóstico do filtro de proporção de código", ""]
T += [f"Código: commit `{c}`." for c in COMMITS] + [""]

# ---- item 1
T += [
    "## 1. Coluna `languages` em Python",
    "",
    "Categorias definidas em `hipoteses.md`. Elegível: mais de 50% do código em Python.",
    "",
]
T += ["| Grupo | Total | " + " | ".join(CATEGORIAS) + " |", "|---|---|" + "---|" * len(CATEGORIAS)]
for grupo, rotulo in GRUPOS.items():
    g = cat[(cat["linguagem"] == "python") & (cat["grupo"] == grupo)]
    total = int(g["total_do_grupo"].iloc[0])
    celulas = [rotulo, milhar(total)]
    for categoria in CATEGORIAS:
        n = int(g[g["categoria"] == categoria]["n"].iloc[0])
        celulas.append(f"{milhar(n)} ({pct(n / total)})")
    T.append("| " + " | ".join(celulas) + " |")
T += ["", "Participação de Python nos bytes, nos grupos com objeto JSON:", ""]
ordem_faixas = [
    "vazia",
    "outro formato",
    "sem a linguagem",
    "até 10%",
    "10% a 25%",
    "25% a 50%",
    "50% a 75%",
    "75% a 90%",
    "90% a 100%",
]
T += ["| Grupo | " + " | ".join(ordem_faixas) + " |", "|---|" + "---|" * len(ordem_faixas)]
for grupo, rotulo in GRUPOS.items():
    g = faixas[(faixas["linguagem"] == "python") & (faixas["grupo"] == grupo)].set_index("faixa")[
        "n"
    ]
    T.append("| " + rotulo + " | " + " | ".join(milhar(g.get(f, 0)) for f in ordem_faixas) + " |")
T += [
    "",
    "Linguagem com mais bytes (doze maiores) nos não elegíveis de Python que têm objeto JSON:",
    "",
]
for grupo in ["nao_elegivel_push_ate_2020", "nao_elegivel_todos"]:
    g = maior[(maior["linguagem"] == "python") & (maior["grupo"] == grupo)]
    partes = [f"{x['maior_linguagem']} {milhar(x['n'])}" for _, x in g.iterrows()]
    T.append(f"- {GRUPOS[grupo]}: " + ", ".join(partes) + ".")
T.append("")
T += [
    f"Exemplos: 20 por grupo e categoria, sorteados com semente fixa. O conteúdo bruto de `languages` passa de {LIMITE_BRUTO} caracteres só quando aparece o sinal de corte; o arquivo `exemplos_python.csv` tem o texto inteiro.",
    "",
]
for grupo in ["nao_elegivel_push_ate_2020", "elegivel_amostra"]:
    for categoria in CATEGORIAS:
        g = exemplos[(exemplos["grupo"] == grupo) & (exemplos["categoria"] == categoria)]
        T += [f"### Exemplos: {GRUPOS[grupo].lower()}, {categoria}", ""]
        if len(g) == 0:
            T += ["Nenhum repositório nesta categoria.", ""]
            continue
        T += ["| repo_name | createdAt | pushedAt | languages |", "|---|---|---|---|"]
        for _, x in g.iterrows():
            T.append(
                f"| {x['repo_name']} | {x['createdAt']} | {x['pushedAt']} | {bruto(x['languages'])} |"
            )
        T.append("")

# ---- item 2
T += ["## 2. Categorias por ano do último push (todos os candidatos de Python)", ""]
T += [
    "| Ano do último push | Elegíveis | Vazia | Outro formato | Sem Python | Python abaixo de 50% | Total | Vazia sobre o total |",
    "|---|---|---|---|---|---|---|---|",
]
anos_python = ano[ano["linguagem"] == "python"]
for a in [str(x) for x in range(2008, 2027)] + ["sem data"]:
    g = anos_python[anos_python["ano_push"].astype(str) == a].set_index("categoria")["n"]
    total = int(g.sum())
    if total == 0 and a == "sem data":
        continue
    T.append(
        f"| {a} | {milhar(g['com a linguagem acima de 50%'])} | {milhar(g['vazia'])} | {milhar(g['outro formato'])} | {milhar(g['sem a linguagem'])} | {milhar(g['com a linguagem abaixo de 50%'])} | {milhar(total)} | {pct(g['vazia'] / total) if total else 'n/d'} |"
    )
T.append("")

# ---- item 3
T += [
    "## 3. API de linguagens do GitHub para 50 não elegíveis com último push até 2020",
    "",
    "Consulta `GET /repos/{owner}/{repo}/languages` em 2026-11-23. Participação de Python = bytes de Python sobre o total de bytes.",
    "",
]
ok = api[api["http_status"] == 200].copy()
ok["participacao_python_hoje"] = ok["participacao_python_hoje"].astype(float)
com_mais_de_50 = int((ok["participacao_python_hoje"] > 0.5).sum())
T += [
    f"- Consultas: {len(api)}. Respostas 200: {len(ok)}. Outros status: {len(api) - len(ok)}.",
    f"- Com mais de 50% em Python hoje: {com_mais_de_50} de {len(ok)}.",
    "- Linguagem com mais bytes hoje: "
    + ", ".join(f"{k} {v}" for k, v in ok["maior_linguagem_hoje"].value_counts().items())
    + ".",
    "",
]
T += [
    "| repo_name | Status | Bytes de Python | Bytes totais | Python hoje | Linguagem com mais bytes hoje | Redirecionado |",
    "|---|---|---|---|---|---|---|",
]
for _, x in api.iterrows():
    esperado = f"https://api.github.com/repos/{x['repo_name']}/languages"
    redirecionado = "não" if x["url_final"] == esperado else "sim"
    participacao = (
        pct(float(x["participacao_python_hoje"])) if x["participacao_python_hoje"] != "" else "n/d"
    )
    T.append(
        f"| {x['repo_name']} | {x['http_status']} | {milhar(x['bytes_python'])} | {milhar(x['bytes_total'])} | {participacao} | {x['maior_linguagem_hoje'] or 'n/d'} | {redirecionado} |"
    )
categorias_amostra = amostra_api["categoria"].value_counts()
T += [
    "",
    "Coluna `languages` da SEART nesses "
    + str(len(amostra_api))
    + " repositórios: "
    + ", ".join(f"{k} {v}" for k, v in categorias_amostra.items())
    + ".",
    "",
]

# ---- item 4
T += ["## 4. Eventos coletados", ""]
T += [
    "### Status da coleta nos progressos dos quatro runs",
    "",
    "| Candidatos | Etapa 2A completa e 2B completa | 2A completa e 2B com erro | 2A com erro e 2B completa | Os dois com erro |",
    "|---|---|---|---|---|",
]
for elegivel, rotulo in [(True, "Elegíveis"), (False, "Não elegíveis")]:
    g = status[status["elegivel"] == elegivel]
    c = g.groupby(["status_2A", "status_2B"]).size()
    T.append(
        f"| {rotulo} ({milhar(len(g))}) | {milhar(c.get(('complete', 'complete'), 0))} | {milhar(c.get(('complete', 'error'), 0))} | {milhar(c.get(('error', 'complete'), 0))} | {milhar(c.get(('error', 'error'), 0))} |"
    )
T.append("")
if eventos is not None:
    com_evento = set(eventos[eventos["eventos"] > 0]["repo_id"])
    T += [
        "### Eventos no arquivo bruto de 346 GB (`eventos_python.csv`)",
        "",
        "| Candidatos | Com evento no arquivo | Sem evento no arquivo | Eventos (soma) |",
        "|---|---|---|---|",
    ]
    por_repo = eventos.set_index("repo_id")["eventos"]
    for elegivel, rotulo in [
        (True, "Elegíveis"),
        (False, "Não elegíveis"),
        (None, "Não elegíveis, último push até 2020"),
    ]:
        if elegivel is None:
            g = status[(~status["elegivel"]) & (status["ano_push"] <= 2020)]
        else:
            g = status[status["elegivel"] == elegivel]
        ids = set(g["repo_id"])
        n_com = len(ids & com_evento)
        soma = int(por_repo.reindex(list(ids)).fillna(0).sum())
        T.append(
            f"| {rotulo} ({milhar(len(ids))}) | {milhar(n_com)} | {milhar(len(ids) - n_com)} | {milhar(soma)} |"
        )
    T.append("")
    sem_evento_nao_elegivel = status[(~status["elegivel"]) & (~status["repo_id"].isin(com_evento))]
    T += [
        "Não elegíveis sem evento no arquivo, por status da coleta:",
        "",
        "| Status 2A | Status 2B | n |",
        "|---|---|---|",
    ]
    for (a, b), n in sem_evento_nao_elegivel.groupby(["status_2A", "status_2B"]).size().items():
        T.append(f"| {a} | {b} | {milhar(n)} |")
    T.append("")
else:
    T += ["A contagem direta de eventos no arquivo de 346 GB não terminou.", ""]
T += [
    "### Ritmo da coleta (a partir de `updated_at` dos progressos)",
    "",
    "| Run | Etapa | Repositórios completos | Primeira atualização | Última atualização | Horas entre as duas | Repositórios por hora (média) | Repositórios por hora (pico) |",
    "|---|---|---|---|---|---|---|---|",
]
for _, x in ritmo.iterrows():
    T.append(
        f"| {x['run']} | {x['etapa']} | {milhar(x['repos_completos'])} | {x['primeira_atualizacao']} | {x['ultima_atualizacao']} | {x['horas_entre_a_primeira_e_a_ultima']:.1f} | {x['repos_por_hora_media']:.1f} | {milhar(x['repos_por_hora_pico'])} |"
    )
T += [
    "",
    "### Erros dos não elegíveis que não completaram",
    "",
    "| Erro (cortado em 120 caracteres) | Etapa | n |",
    "|---|---|---|",
]
for _, x in erros.iterrows():
    T.append(f"| {str(x['erro']).replace('|', '/')} | {x['etapa']} | {x['n']} |")
T.append("")

# ---- item 5
T += ["## 5. As outras quatro linguagens", ""]
T += [
    "| Linguagem | Grupo | Total | " + " | ".join(CATEGORIAS) + " |",
    "|---|---|---|" + "---|" * len(CATEGORIAS),
]
for lingua in LINGUAS:
    for grupo, rotulo in GRUPOS.items():
        g = cat[(cat["linguagem"] == lingua) & (cat["grupo"] == grupo)]
        total = int(g["total_do_grupo"].iloc[0])
        celulas = [NOMES[lingua], rotulo, milhar(total)]
        for categoria in CATEGORIAS:
            n = int(g[g["categoria"] == categoria]["n"].iloc[0])
            celulas.append(f"{milhar(n)} ({pct(n / total) if total else 'n/d'})")
        T.append("| " + " | ".join(celulas) + " |")
(PASTA / "tabelas.md").write_text("\n".join(T) + "\n", encoding="utf-8")

# ---- resumo
py = cat[cat["linguagem"] == "python"]
n_vazia = int(
    py[(py["grupo"] == "nao_elegivel_push_ate_2020") & (py["categoria"] == "vazia")]["n"].iloc[0]
)
n_total = int(py[py["grupo"] == "nao_elegivel_push_ate_2020"]["total_do_grupo"].iloc[0])
frases_outras = []
for lingua in ["clojure", "elixir", "ocaml", "zig"]:
    g = cat[(cat["linguagem"] == lingua) & (cat["grupo"] == "nao_elegivel_push_ate_2020")]
    vazias = int(g[g["categoria"] == "vazia"]["n"].iloc[0])
    frases_outras.append(f"{NOMES[lingua]} {int(g['total_do_grupo'].iloc[0])} ({vazias})")
L = ["# Diagnóstico do filtro de proporção de código em Python", ""]
L += [
    f"Código: commit `{COMMITS[0]}`. Protocolo em `hipoteses.md`. Todas as tabelas em `tabelas.md`.",
    "",
]
L += ["## Respostas de fato", ""]
L += [
    f"1. Dos {milhar(n_total)} não elegíveis de Python com último push até 2020, {milhar(n_vazia)} ({pct(n_vazia / n_total)}) têm a coluna `languages` vazia. A amostra de 1.000 elegíveis tem todos com Python acima de 50%.",
    "2. A distribuição por ano do último push, para elegíveis e não elegíveis, está na seção 2 de `tabelas.md`.",
    f"3. API do GitHub: {com_mais_de_50} dos {len(ok)} repositórios consultados têm mais de 50% em Python hoje. Em todos a coluna `languages` da SEART estava vazia.",
]
if eventos is not None:
    nao = status[~status["elegivel"]]
    com = nao["repo_id"].isin(com_evento).sum()
    L.append(
        f"4. Eventos: dos {milhar(len(nao))} não elegíveis, {milhar(com)} têm evento no arquivo de 346 GB. A coleta de eventos não filtra pela proporção de código."
    )
else:
    L.append("4. Eventos: a contagem direta no arquivo de 346 GB não terminou (ver `tabelas.md`).")
L += [
    "5. Outras quatro linguagens, não elegíveis com último push até 2020 (vazias entre parênteses): "
    + "; ".join(frases_outras)
    + ".",
    "",
    "Sem leitura de resultado além das tabelas.",
]
(PASTA / "resumo.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
