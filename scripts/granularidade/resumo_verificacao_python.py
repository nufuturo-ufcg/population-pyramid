"""Resumo da verificação da lista de repositórios (`projecao-rq3/verificacao-python/`). Ver `hipoteses.md`.

Lê `lista_seart.csv`, `nascimento.csv`, `candidatos.csv`, `push_contra_evento.csv` e `estatisticas_<lang>.json` (gerados na VM por `verificacao_lista.py`),
o `AMOSTRA.md` e a auditoria da rodada oficial. Grava `tabelas.md` e `resumo.md`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/resumo_verificacao_python.py <verificacao-python> <pyramid-vitalidade>
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd

SAIDA = Path(sys.argv[1])
VITALIDADE = Path(sys.argv[2])
LINGUAS = ["clojure", "elixir", "ocaml", "python", "zig"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "ocaml": "OCaml",
    "python": "Python",
    "zig": "Zig",
}
COMMITS = (SAIDA / "commit.txt").read_text(encoding="utf-8").strip().splitlines()


def pct(x: float, casas: int = 1) -> str:
    return f"{100 * x:.{casas}f}%".replace(".", ",")


def milhar(n: float) -> str:
    return f"{int(n):,}".replace(",", ".")


lista = pd.read_csv(SAIDA / "lista_seart.csv").set_index("linguagem")
nasc = pd.read_csv(SAIDA / "nascimento.csv")
cand = pd.read_csv(SAIDA / "candidatos.csv", dtype={"repo_id": str})
push = pd.read_csv(SAIDA / "push_contra_evento.csv").set_index("linguagem")

# AMOSTRA.md: a linha de cada linguagem na primeira tabela
amostra = {}
for linha in (VITALIDADE / "AMOSTRA.md").read_text(encoding="utf-8").splitlines():
    partes = [c.strip() for c in linha.strip().strip("|").split("|")]
    if len(partes) >= 5 and partes[0] in NOMES.values() and re.fullmatch(r"[\d.]+", partes[1]):
        amostra[partes[0]] = [int(c.replace(".", "")) for c in partes[1:5]]

T = ["# Tabelas da verificação da lista de repositórios", ""]
T += [f"Código: commit `{c}`." for c in COMMITS] + [""]

# ---- 1a: o que a lista da SEART contém
T += ["## 1a. O que as listas da SEART contêm", ""]
T += ["| Linguagem | Linhas | repo_id únicos | Arquivos (linhas) | Estrelas mín. | Estrelas mediana | Estrelas máx. | repo_id em ordem crescente | repo_id mín. | repo_id máx. |", "|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
for lingua in LINGUAS:
    x = lista.loc[lingua]
    T.append(
        f"| {NOMES[lingua]} | {milhar(x['linhas'])} | {milhar(x['repo_ids_unicos'])} | {int(x['arquivos'])} ({x['linhas_por_arquivo']}) | {int(x['estrelas_min'])} | {x['estrelas_mediana']:.0f} | {milhar(x['estrelas_max'])} | {'sim' if x['repo_id_crescente'] else 'não'} | {milhar(x['repo_id_min'])} | {milhar(x['repo_id_max'])} |"
    )
T += ["", "| Linguagem | Criado: mais antigo | Criado: mais novo | Criado até 2020 | Criado em 2021 ou depois | Último push: mais antigo | Último push: mais novo | Push até 2020 | Push até 2023 | Push em 2025 ou depois | Forks | Arquivados | Linguagem principal igual |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
for lingua in LINGUAS:
    x = lista.loc[lingua]
    T.append(
        f"| {NOMES[lingua]} | {x['criado_min']} | {x['criado_max']} | {pct(x['criado_ate_2020'])} | {pct(x['criado_2021_ou_depois'])} | {x['push_min']} | {x['push_max']} | {pct(x['push_ate_2020'])} | {pct(x['push_ate_2023'])} | {pct(x['push_2025_ou_depois'])} | {pct(x['fork'])} | {pct(x['arquivado'])} | {pct(x['linguagem_principal_igual'])} |"
    )
T += [
    "",
    "Percentuais sobre todas as linhas da lista (candidatos), sem o filtro de proporção de código.",
    "",
]

T += [
    "### Último push da SEART contra último evento da carga",
    "",
    "Só os repositórios da carga (com algum evento). Anos civis.",
    "",
]
T += ["| Linguagem | Repositórios | Push até 2020 | Último evento até 2020 | Os dois até 2020 | Push até 2020 e último evento depois | Push depois e último evento até 2020 | Último evento mais de 1 ano depois do push |", "|---|---|---|---|---|---|---|---|"]  # fmt: skip
for lingua in LINGUAS:
    x = push.loc[lingua]
    n = x["repos"]
    T.append(
        f"| {NOMES[lingua]} | {milhar(n)} | {milhar(x['push_ate_2020'])} ({pct(x['push_ate_2020'] / n)}) | {milhar(x['ultimo_evento_ate_2020'])} ({pct(x['ultimo_evento_ate_2020'] / n)}) | {milhar(x['push_ate_2020_e_ultimo_evento_ate_2020'])} | {milhar(x['push_ate_2020_e_ultimo_evento_depois'])} | {milhar(x['push_depois_e_ultimo_evento_ate_2020'])} | {milhar(x['ultimo_evento_mais_de_1_ano_depois_do_push'])} ({pct(x['ultimo_evento_mais_de_1_ano_depois_do_push'] / n)}) |"
    )
T.append("")

# ---- 1b: nascimento e parada
T += [
    "## 1b. Repositórios por ano de nascimento e fração com o último evento até 3 anos depois",
    "",
    "Nascimento: ano do primeiro evento do repositório. Fração: último evento em ano civil menor ou igual ao do nascimento mais 3.",
    "",
]
cab = ["Ano de nascimento"]
for lingua in LINGUAS:
    cab += [f"{NOMES[lingua]}: nasceram", f"{NOMES[lingua]}: fração"]
T += ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
for ano in range(2008, 2021):
    celulas = [str(ano)]
    for lingua in LINGUAS:
        x = nasc[(nasc["linguagem"] == lingua) & (nasc["ano_nascimento"] == ano)].iloc[0]
        celulas.append(milhar(x["repos"]))
        celulas.append(pct(x["ultimo_evento_ate_3_anos"] / x["repos"]) if x["repos"] else "n/d")
    T.append("| " + " | ".join(celulas) + " |")
celulas = ["2008 a 2020"]
for lingua in LINGUAS:
    d = nasc[(nasc["linguagem"] == lingua) & (nasc["ano_nascimento"] <= 2020)]
    celulas.append(milhar(d["repos"].sum()))
    celulas.append(pct(d["ultimo_evento_ate_3_anos"].sum() / d["repos"].sum()))
T.append("| " + " | ".join(celulas) + " |")
T += [
    "",
    "Contagens absolutas de repositórios com o último evento até 3 anos depois em `nascimento.csv`.",
    "",
]

# ---- 1c: reconciliação com AMOSTRA.md
T += ['## 1c. Total de repositórios da carga contra a coluna "com algum evento" de AMOSTRA.md', ""]
T += ["| Linguagem | Candidatos | Excluídos por proporção de código | Elegíveis | AMOSTRA.md: com algum evento | Carga: com algum evento | Diferença | Duplicados fundidos (carga) | Duplicados em repos_excluidos.csv | Desses, com evento na carga | Candidatos sem evento na carga | Desses: proporção | Desses: duplicados | Desses: outros | AMOSTRA.md: elegíveis sem evento |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
saida_1c = []
for lingua in LINGUAS:
    est = json.loads((SAIDA / f"estatisticas_{lingua}.json").read_text(encoding="utf-8"))
    c = cand[cand["linguagem"] == lingua]
    excluidos = pd.read_csv(
        VITALIDADE / "rodada-2026-11-14-0921" / "auditoria" / lingua / "repos_excluidos.csv",
        dtype={"repo_id": str},
    )
    x_ids = set(excluidos["repo_id"])
    com_evento = set(c[c["com_evento_na_carga"]]["repo_id"])
    todos = set(c["repo_id"])
    sem_evento = len(todos) - len(com_evento)
    duplicados_sem_evento = len(x_ids & (todos - com_evento))
    outros = sem_evento - est["repos_excluidos_share"] - duplicados_sem_evento
    a = amostra[NOMES[lingua]]
    T.append(
        f"| {NOMES[lingua]} | {milhar(est['repos_total'])} | {milhar(est['repos_excluidos_share'])} | {milhar(est['repos_elegiveis'])} | {milhar(a[2])} | {milhar(len(com_evento))} | {milhar(a[2] - len(com_evento))} | {milhar(est['repos_fundidos'])} | {milhar(len(x_ids))} | {milhar(len(x_ids & com_evento))} | {milhar(sem_evento)} | {milhar(est['repos_excluidos_share'])} | {milhar(duplicados_sem_evento)} | {milhar(outros)} | {milhar(a[3])} |"
    )
    saida_1c.append((lingua, est, a, len(com_evento), len(x_ids), outros))
T += [
    "",
    'Candidatos sem evento na carga = candidatos menos os com algum evento. "Proporção" é a contagem `repos_excluidos_share` de `estatisticas_da_carga.json`. "Outros" é o que sobra depois de tirar proporção e duplicados.',
    "",
]

(SAIDA / "tabelas.md").write_text("\n".join(T) + "\n", encoding="utf-8")

# ---- resumo
L = ["# Como a lista de repositórios foi montada, em Python e nas outras linguagens", ""]
L += [
    f"Código: commit `{COMMITS[0]}` (script de medida) e `{COMMITS[1]}` (resumo). Protocolo em `hipoteses.md`. Todas as tabelas em `tabelas.md`.",
    "",
]
L += ["## 1a. Como a lista de cada linguagem foi montada", ""]
L += [
    "O que está registrado:",
    "",
    "- **Critério de estrelas.** 10 estrelas ou mais, medidas na data da listagem, pela SEART (`AMOSTRA.md`, `docs/linguagem/tcc.md`). Estrelas mínimas nas listas: 10 em quatro linguagens e 9 em Python.",
    "- **Elegibilidade.** Mais de 50% do código na linguagem, pela coluna `languages` da SEART (`AMOSTRA.md`). Depois dessa regra ficam 7.363 (Clojure), 6.284 (Elixir), 3.426 (OCaml), 2.092 (Zig) e 309.920 (Python).",
    "- **Limite de resultados.** A SEART lista todos os repositórios que casam, sem o limite de 1.000 resultados da busca padrão do GitHub (descrição em `Plano de Experimento.md`). As listas têm de 2.177 (Zig) a 422.720 linhas (Python), sem repetição de `repo_id`.",
    "- **Origem das listas.** As cinco são exportações da SEART com o mesmo cabeçalho (`repo_id`, `repo_name`, `isFork`, `commits`, `stargazers`, `createdAt`, `pushedAt` e outras). A primeira coleta de Clojure (runs de 23/08 e 01/09/2026) usou outra origem: a busca do GitHub em `etapa_1_coleta.py`, que pagina 34 páginas de 30 resultados ordenadas por estrelas. Ela foi trocada pela lista da SEART em 02/09/2026, e a lista de Clojure desta análise é a de `2026-09-03-clojure`.",
    "- **Divisão da busca em faixas.** Não está registrada. As listas de todas as linguagens vêm com o `repo_id` em ordem crescente.",
    "- **Ordenação.** Não está registrada. A ordem do `repo_id` é a das listas; só Clojure teve ordenação por estrelas, na busca antiga descartada.",
    "- **Filtro de atividade.** Não está registrado (`AMOSTRA.md`, `docs/linguagem/tcc.md`). O último push mais antigo das listas é de 2008 em Clojure, OCaml e Python, de 2012 em Elixir e de 2019 em Zig (tabela 1a). Um filtro de commit recente na busca não deixaria esses repositórios na lista, e a data da listagem também não está registrada. O limite inferior dela é o push mais novo da lista (agosto a outubro de 2026).",
    "- **Forks, data de criação e atividade.** Registrado que os filtros da busca nesses três campos não estão no repositório.",
    "",
    "Python foi coletado de um jeito diferente?",
    "",
    "- **Origem e critério.** Mesma origem (SEART) e mesmos critérios de estrelas e de proporção de código que as outras quatro linguagens.",
    "- **Divisão operacional.** A lista de Python tem 422.720 linhas em dois arquivos (211.359 e 211.361 linhas, com `repo_id` crescente de 125.860 a 95.947.574). Os eventos foram coletados em três máquinas (AWS, batuta e uma terceira VM) em runs separados, redivididos em 05/10 e 07/10/2026 e juntados em 12/10 e 15/10/2026 (`MANIFESTO.txt`). A coleta dos eventos roda o mesmo código (`etapa_2A_eventos.py` e `etapa_2B_eventos.py`).",
    "- **Leitura dos eventos.** O arquivo de eventos de Python tem 346 GB e é lido sem contar as linhas brutas (`AMOSTRA.md`).",
    "",
]
L += [
    "## 1b. Nascimento e parada",
    "",
    "Tabela por linguagem e ano de nascimento em `tabelas.md` (nasceram e fração com o último evento até 3 anos depois). Último push da SEART contra último evento da carga na mesma seção de tabelas.",
    "",
]
L += ["## 1c. Carga contra AMOSTRA.md", ""]
L += [
    '- `AMOSTRA.md` (modificado em 19/10/2026) tem a coluna "com algum evento" de `meta.json` da rodada 2026-11-09-0945, anterior ao tratamento de repositórios duplicados.',
    "- A carga atual é a da rodada oficial 2026-11-14-0921, que funde cada grupo de repositórios duplicados num só (`repos_fundidos` repositórios em `grupos_de_duplicados` grupos, lista em `auditoria/<lang>/repos_excluidos.csv`). Os duplicados saem da contagem e o grupo conta como um repositório.",
    "- Em Elixir, `meta.json` das rodadas dá 6.265 repositórios com evento em 2026-11-09-0945, 6.008 em 2026-11-13-1756, 2026-11-13-2054 e 2026-11-13-2255 (esta com 253 fundidos) e 6.010 na oficial 2026-11-14-0921.",
    "",
    "Elixir, da tabela 1c:",
    "",
]
for lingua, est, a, n_com, n_x, outros in saida_1c:
    if lingua != "elixir":
        continue
    L += [
        f"- {milhar(a[2])} em AMOSTRA.md menos {milhar(n_com)} na carga: {a[2] - n_com} repositórios.",
        f"- {n_x} deles são duplicados listados em `repos_excluidos.csv` (todos candidatos da lista, nenhum com evento na carga). A diferença restante é {a[2] - n_com - n_x}.",
        f"- Os candidatos sem evento na carga são {milhar(est['repos_total'] - n_com)}: {est['repos_excluidos_share']} por proporção de código, {n_x} duplicados e {outros} outros. `AMOSTRA.md` conta {a[3]} elegíveis sem evento.",
    ]
L += [
    "",
    "As outras linguagens estão na mesma tabela.",
    "",
    "Sem leitura de resultado além das tabelas.",
]
(SAIDA / "resumo.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
