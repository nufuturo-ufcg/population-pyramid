"""Como a lista de repositórios de cada linguagem foi montada (verificação de `projecao-rq3/verificacao-python/`). Roda na VM.

Grava em `<saida>`:
  - `lista_seart.csv`: por linguagem, o que as listas da SEART (`repositorios_<lang>_alvo.csv`) contêm: estrelas, datas de criação e do último push, forks, arquivados, ordem do `repo_id`.
  - `nascimento.csv`: por linguagem e ano do primeiro evento do repositório (todos os eventos da carga), quantos nasceram e quantos tiveram o último evento até 3 anos depois (em anos civis).
  - `repos_pre_pos.csv`: os `repo_id` com algum evento na rodada 2026-11-13-1756 (sem fusão de duplicados, a que `AMOSTRA.md` descreve) e na carga atual (com fusão), para reconciliar as contagens.

Uso (na raiz do repo, na VM): .venv/bin/python scripts/granularidade/verificacao_lista.py <carga> <rodadas> <runs> <python> <saida> clojure elixir ocaml python zig
  <rodadas> = ~/pyramid/rodadas, <runs> = ~/population-pyramid/coleta-dados/runs, <python> = ~/dados-brutos/python
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rodar import le_dados

CARGA, RODADAS, RUNS, PYTHON, SAIDA = (Path(a) for a in sys.argv[1:6])
LINGUAS = sys.argv[6:]
SAIDA.mkdir(parents=True, exist_ok=True)
RODADA_SEM_FUSAO = "2026-11-13-1756"
LISTAS = {
    "clojure": [RUNS / "2026-09-03-clojure" / "repositorios_clojure_alvo.csv"],
    "elixir": [RUNS / "2026-09-04-elixir" / "repositorios_elixir_alvo.csv"],
    "zig": [RUNS / "2026-09-06-zig" / "repositorios_zig_alvo.csv"],
    "ocaml": [RUNS / "2026-10-10-ocaml" / "repositorios_ocaml_alvo.csv"],
    # as duas metades da lista de Python, antes das divisões entre as máquinas
    "python": [
        PYTHON / "run-aws-1" / "repositorios_python_alvo.csv.orig-antes-divisao-2026-10-05",
        PYTHON / "run-batuta-2" / "repositorios_python_alvo.csv",
    ],
}
NOME_NA_SEART = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "ocaml": "OCaml",
    "python": "Python",
}

linhas_lista, linhas_nascimento, linhas_pre_pos = [], [], []
for lingua in LINGUAS:
    # ---- 1. o que a lista da SEART contém
    partes = []
    for caminho in LISTAS[lingua]:
        cabecalho = pd.read_csv(caminho, nrows=0).columns
        coluna_estrelas = "stargazers" if "stargazers" in cabecalho else "stars"
        usar = [
            "repo_id",
            "isFork",
            "mainLanguage",
            coluna_estrelas,
            "createdAt",
            "pushedAt",
            "isArchived",
        ]
        parte = pd.read_csv(caminho, usecols=usar).rename(columns={coluna_estrelas: "estrelas"})
        partes.append(parte)
        print(f"{lingua}: {caminho.name} {len(parte)} linhas", flush=True)
    lista = pd.concat(partes, ignore_index=True)
    ids = lista["repo_id"].to_numpy()
    criado = pd.to_datetime(lista["createdAt"], errors="coerce")
    push = pd.to_datetime(lista["pushedAt"], errors="coerce")
    linhas_lista.append(
        {
            "linguagem": lingua,
            "linhas": len(lista),
            "repo_ids_unicos": int(lista["repo_id"].nunique()),
            "arquivos": len(partes),
            "linhas_por_arquivo": "+".join(str(len(p)) for p in partes),
            "estrelas_min": int(lista["estrelas"].min()),
            "estrelas_mediana": float(lista["estrelas"].median()),
            "estrelas_max": int(lista["estrelas"].max()),
            "criado_min": str(criado.min())[:10],
            "criado_max": str(criado.max())[:10],
            "criado_ate_2020": float((criado.dt.year <= 2020).mean()),
            "criado_2021_ou_depois": float((criado.dt.year >= 2021).mean()),
            "push_min": str(push.min())[:10],
            "push_max": str(push.max())[:10],
            "push_ate_2020": float((push.dt.year <= 2020).mean()),
            "push_ate_2023": float((push.dt.year <= 2023).mean()),
            "push_2025_ou_depois": float((push.dt.year >= 2025).mean()),
            "fork": float((lista["isFork"].astype(str).str.lower() == "true").mean()),
            "arquivado": float((lista["isArchived"].astype(str).str.lower() == "true").mean()),
            "linguagem_principal_igual": float(
                (lista["mainLanguage"] == NOME_NA_SEART[lingua]).mean()
            ),
            "repo_id_min": int(ids.min()),
            "repo_id_max": int(ids.max()),
            "repo_id_crescente": bool(np.all(np.diff(ids) > 0)),
        }
    )
    del lista, partes

    # ---- 2. nascimento do repositório e último evento (todos os eventos da carga)
    pessoas, eventos = le_dados(CARGA, lingua)
    anos = (eventos["dia"].astype("datetime64[Y]").astype(np.int64) + 1970).astype(np.int16)
    tabela = pd.DataFrame({"codigo": eventos["codigo"], "ano": anos}).drop_duplicates()
    por_repo = tabela.groupby("codigo")["ano"].agg(primeiro="min", ultimo="max")
    del tabela, pessoas
    por_repo["parou_ate_3_anos"] = por_repo["ultimo"] <= por_repo["primeiro"] + 3
    for ano in range(2008, 2025):
        nascidos = por_repo[por_repo["primeiro"] == ano]
        linhas_nascimento.append(
            {
                "linguagem": lingua,
                "ano_nascimento": ano,
                "repos": len(nascidos),
                "ultimo_evento_ate_3_anos": int(nascidos["parou_ate_3_anos"].sum()),
            }
        )

    # ---- 3. repositórios com algum evento antes e depois da fusão de duplicados
    codigos_pos = set(por_repo.index)
    repos_pos = pd.read_parquet(CARGA / lingua / "origem" / "repos.parquet")
    ids_pos = set(repos_pos[repos_pos["codigo"].isin(codigos_pos)]["repo_id"].astype(str))
    pasta_pre = RODADAS / RODADA_SEM_FUSAO / lingua / "origem"
    repos_pre = pd.read_parquet(pasta_pre / "repos.parquet")
    codigos_pre = set(pd.read_parquet(pasta_pre / "repos_por_trimestre.parquet")["codigo"])
    ids_pre = set(repos_pre[repos_pre["codigo"].isin(codigos_pre)]["repo_id"].astype(str))
    for repo_id in sorted(ids_pre | ids_pos):
        linhas_pre_pos.append(
            {
                "linguagem": lingua,
                "repo_id": repo_id,
                "com_evento_antes_da_fusao": repo_id in ids_pre,
                "com_evento_depois_da_fusao": repo_id in ids_pos,
            }
        )
    print(
        f"{lingua}: antes da fusão {len(ids_pre)} repositórios, depois {len(ids_pos)}", flush=True
    )
    pd.DataFrame(linhas_lista).to_csv(SAIDA / "lista_seart.csv", index=False)
    pd.DataFrame(linhas_nascimento).to_csv(SAIDA / "nascimento.csv", index=False)
    pd.DataFrame(linhas_pre_pos).to_csv(SAIDA / "repos_pre_pos.csv", index=False)
print("pronto")
