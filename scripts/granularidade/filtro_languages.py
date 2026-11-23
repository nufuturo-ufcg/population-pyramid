"""Distribuição da coluna `languages` da SEART e o filtro de proporção de código (`projecao-rq3/filtro-python/`). Roda na VM.

Itens 1, 2 e 5 de `hipoteses.md`, mais a amostra de 50 repositórios do item 3 e os status de coleta do item 4.
Grava em `<saida>`:
  - `categorias.csv`: linguagem, grupo, categoria, n.
  - `faixas_participacao.csv`: linguagem, grupo, faixa da participação da linguagem, n.
  - `maior_linguagem.csv`: linguagem, grupo, linguagem com mais bytes, n (só candidatos com objeto JSON).
  - `por_ano_push.csv`: linguagem, ano do último push, elegível, categoria, n (todos os candidatos).
  - `exemplos_python.csv`: 20 exemplos por grupo e categoria de Python com o conteúdo bruto de `languages`.
  - `amostra_api.csv`: os 50 candidatos de Python do item 3.
  - `status_coleta_python.csv`: candidatos de Python, elegível e status da coleta (2A e 2B).

Uso (na raiz do repo, na VM): .venv/bin/python scripts/granularidade/filtro_languages.py <runs> <python> <saida>
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from filtro_languages_apoio import classifica

RUNS, PYTHON, SAIDA = (Path(a) for a in sys.argv[1:4])
SAIDA.mkdir(parents=True, exist_ok=True)
SEMENTE = 20261123
LISTAS = {
    "clojure": [RUNS / "2026-09-03-clojure" / "repositorios_clojure_alvo.csv"],
    "elixir": [RUNS / "2026-09-04-elixir" / "repositorios_elixir_alvo.csv"],
    "zig": [RUNS / "2026-09-06-zig" / "repositorios_zig_alvo.csv"],
    "ocaml": [RUNS / "2026-10-10-ocaml" / "repositorios_ocaml_alvo.csv"],
    "python": [
        PYTHON / "run-aws-1" / "repositorios_python_alvo.csv.orig-antes-divisao-2026-10-05",
        PYTHON / "run-batuta-2" / "repositorios_python_alvo.csv",
    ],
}
NOME = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "ocaml": "OCaml",
    "python": "Python",
}
CATEGORIAS = [
    "vazia",
    "outro formato",
    "sem a linguagem",
    "com a linguagem abaixo de 50%",
    "com a linguagem acima de 50%",
]
FAIXAS = [
    "sem a linguagem",
    "até 10%",
    "10% a 25%",
    "25% a 50%",
    "50% a 75%",
    "75% a 90%",
    "90% a 100%",
]


def faixa(categoria: str, participacao: float) -> str:
    resultado = categoria
    if categoria not in ("vazia", "outro formato", "sem a linguagem"):
        limites = [
            (0.10, "até 10%"),
            (0.25, "10% a 25%"),
            (0.50, "25% a 50%"),
            (0.75, "50% a 75%"),
            (0.90, "75% a 90%"),
        ]
        resultado = "90% a 100%"
        for limite, rotulo in limites:
            if participacao <= limite:
                resultado = rotulo
                break
    return resultado


linhas_categorias, linhas_faixas, linhas_maior, linhas_ano, exemplos = [], [], [], [], []
for lingua in ["python", "clojure", "elixir", "ocaml", "zig"]:
    partes = []
    for caminho in LISTAS[lingua]:
        partes.append(
            pd.read_csv(
                caminho,
                usecols=["repo_id", "repo_name", "createdAt", "pushedAt", "languages"],
                dtype=str,
            )
        )
    lista = pd.concat(partes, ignore_index=True)
    resultados = []
    for texto in lista["languages"]:
        resultados.append(classifica(texto, NOME[lingua]))
    lista["categoria"] = [r[0] for r in resultados]
    lista["participacao"] = [r[1] for r in resultados]
    lista["maior"] = [r[2] for r in resultados]
    lista["faixa"] = [faixa(r[0], r[1]) for r in resultados]
    lista["elegivel"] = lista["categoria"] == "com a linguagem acima de 50%"
    lista["ano_push"] = pd.to_datetime(lista["pushedAt"], errors="coerce").dt.year
    print(
        f"{lingua}: {len(lista)} candidatos, {int((~lista['elegivel']).sum())} não elegíveis",
        flush=True,
    )

    ate_2020 = lista["ano_push"] <= 2020
    nao_elegivel_ate_2020 = lista[ate_2020 & ~lista["elegivel"]]
    nao_elegivel_todos = lista[~lista["elegivel"]]
    elegiveis = lista[lista["elegivel"]]
    tamanho_amostra = min(1000, len(elegiveis))
    amostra_elegivel = elegiveis.sample(n=tamanho_amostra, random_state=SEMENTE)
    grupos = [
        ("nao_elegivel_push_ate_2020", nao_elegivel_ate_2020),
        ("nao_elegivel_todos", nao_elegivel_todos),
        ("elegivel_amostra", amostra_elegivel),
    ]
    for nome_grupo, g in grupos:
        for categoria in CATEGORIAS:
            linhas_categorias.append(
                {
                    "linguagem": lingua,
                    "grupo": nome_grupo,
                    "categoria": categoria,
                    "n": int((g["categoria"] == categoria).sum()),
                    "total_do_grupo": len(g),
                }
            )
        for f in [*FAIXAS, "vazia", "outro formato"]:
            linhas_faixas.append(
                {
                    "linguagem": lingua,
                    "grupo": nome_grupo,
                    "faixa": f,
                    "n": int((g["faixa"] == f).sum()),
                }
            )
        contagem = g[g["maior"] != ""]["maior"].value_counts()
        for nome_maior, n in contagem.head(12).items():
            linhas_maior.append(
                {
                    "linguagem": lingua,
                    "grupo": nome_grupo,
                    "maior_linguagem": nome_maior,
                    "n": int(n),
                }
            )
    # por ano do último push
    for ano in [*range(2008, 2027), -1]:
        g_ano = lista[lista["ano_push"].isna()] if ano == -1 else lista[lista["ano_push"] == ano]
        for categoria in CATEGORIAS:
            linhas_ano.append(
                {
                    "linguagem": lingua,
                    "ano_push": "sem data" if ano == -1 else ano,
                    "categoria": categoria,
                    "n": int((g_ano["categoria"] == categoria).sum()),
                }
            )
    # exemplos e amostra da API (só Python)
    if lingua == "python":
        for nome_grupo, g in grupos:
            if nome_grupo == "nao_elegivel_todos":
                continue
            for categoria in CATEGORIAS:
                sub = g[g["categoria"] == categoria]
                escolha = sub.sample(n=min(20, len(sub)), random_state=SEMENTE)
                for _, x in escolha.iterrows():
                    exemplos.append(
                        {
                            "grupo": nome_grupo,
                            "categoria": categoria,
                            "repo_id": x["repo_id"],
                            "repo_name": x["repo_name"],
                            "createdAt": x["createdAt"],
                            "pushedAt": x["pushedAt"],
                            "languages": x["languages"],
                        }
                    )
        sorteio = nao_elegivel_ate_2020.sample(n=50, random_state=SEMENTE)
        sorteio[
            ["repo_id", "repo_name", "createdAt", "pushedAt", "participacao", "categoria"]
        ].to_csv(SAIDA / "amostra_api.csv", index=False)
        # status da coleta de cada candidato
        status = {}
        for run in ["run-aws-1", "run-batuta-1", "run-batuta-2", "run-vm2-1"]:
            for etapa in ["2A", "2B"]:
                caminho = PYTHON / run / "reports" / f"etapa_{etapa}_progresso.json"
                progresso = json.loads(caminho.read_text(encoding="utf-8"))["repositories"]
                for repo_id, info in progresso.items():
                    chave = (repo_id, etapa)
                    if status.get(chave) != "complete":
                        status[chave] = info["status"]
                del progresso
        s2a, s2b = [], []
        for repo_id in lista["repo_id"]:
            s2a.append(status.get((repo_id, "2A"), "sem registro"))
            s2b.append(status.get((repo_id, "2B"), "sem registro"))
        saida_status = lista[["repo_id", "elegivel", "ano_push"]].copy()
        saida_status["status_2A"] = s2a
        saida_status["status_2B"] = s2b
        saida_status.to_csv(SAIDA / "status_coleta_python.csv", index=False)
    pd.DataFrame(linhas_categorias).to_csv(SAIDA / "categorias.csv", index=False)
    pd.DataFrame(linhas_faixas).to_csv(SAIDA / "faixas_participacao.csv", index=False)
    pd.DataFrame(linhas_maior).to_csv(SAIDA / "maior_linguagem.csv", index=False)
    pd.DataFrame(linhas_ano).to_csv(SAIDA / "por_ano_push.csv", index=False)
    pd.DataFrame(exemplos).to_csv(SAIDA / "exemplos_python.csv", index=False)
    del lista
print("pronto")
