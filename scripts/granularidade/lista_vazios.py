"""Item 0 de `projecao-rq3/correcao-elegibilidade/hipoteses.md`: candidatos das cinco linguagens com a coluna `languages` da SEART vazia.

Vazia: célula ausente, texto vazio, `{}` ou bytes somando 0 (a definição de `filtro_languages.py`). Grava `<saida>` (repo_id, repo_name, linguagem, pushedAt, createdAt)
e imprime a contagem por linguagem.

Uso (na batuta, na raiz do repo): .venv/bin/python scripts/granularidade/lista_vazios.py <runs> <python> <saida.csv>
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from filtro_languages_apoio import classifica

RUNS, PYTHON, SAIDA = (Path(a) for a in sys.argv[1:4])
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
partes = []
for lingua, caminhos in LISTAS.items():
    for caminho in caminhos:
        lista = pd.read_csv(
            caminho,
            usecols=["repo_id", "repo_name", "createdAt", "pushedAt", "languages"],
            dtype=str,
        )
        categorias = []
        for texto in lista["languages"]:
            categorias.append(classifica(texto, NOME[lingua])[0])
        lista["categoria"] = categorias
        vazios = lista[lista["categoria"] == "vazia"].copy()
        vazios["linguagem"] = lingua
        partes.append(vazios[["repo_id", "repo_name", "linguagem", "pushedAt", "createdAt"]])
saida = pd.concat(partes, ignore_index=True).drop_duplicates(["linguagem", "repo_id"])
saida.to_csv(SAIDA, index=False)
print(saida["linguagem"].value_counts().to_string())
print("total", len(saida))
