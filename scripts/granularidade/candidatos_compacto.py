"""Candidatos das cinco linguagens com a classificação da coluna `languages` da SEART, num CSV compacto. Roda na VM.

Colunas: linguagem, repo_id, repo_name, createdAt, pushedAt, categoria, fracao_seart (participação da linguagem-alvo nos bytes, 0 se não houver).
Usado por `impacto_elegibilidade.py`. Mesmas listas de `lista_vazios.py`.

Uso (na batuta, na raiz do repo): .venv/bin/python scripts/granularidade/candidatos_compacto.py <runs> <python> <saida.csv>
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
        categorias, fracoes = [], []
        for texto in lista["languages"]:
            categoria, fracao, _ = classifica(texto, NOME[lingua])
            categorias.append(categoria)
            fracoes.append(fracao)
        lista["categoria"] = categorias
        lista["fracao_seart"] = fracoes
        lista["linguagem"] = lingua
        partes.append(
            lista[
                [
                    "linguagem",
                    "repo_id",
                    "repo_name",
                    "createdAt",
                    "pushedAt",
                    "categoria",
                    "fracao_seart",
                ]
            ]
        )
saida = pd.concat(partes, ignore_index=True).drop_duplicates(["linguagem", "repo_id"])
saida.to_csv(SAIDA, index=False)
print(len(saida), "candidatos")
