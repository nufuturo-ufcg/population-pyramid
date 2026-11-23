"""Repositórios por ano e população P1 do S2, por linguagem (investigação 2 de `projecao-rq3/investigacao/`).

Para cada ano de 2008 a 2026 grava em `<saida>/repos_por_ano.csv`:
  - repos_com_evento: repositórios com algum evento no ano (qualquer pessoa, todos os eventos da carga);
  - repos_primeiro_evento: repositórios cujo primeiro evento da carga é do ano;
  - repos_ultimo_evento: repositórios cujo último evento da carga (até o fim da coleta) é do ano;
  - repos_com_evento_residente e repos_primeiro_evento_residente: os mesmos dois números contando só eventos de quem já era residente (P1) na data do evento, que é o que o estado do S2 usa;
  - p1_dezembro: população P1 (ativos) em 31 de dezembro, do estado do S2 (só até 2024, a data final da grade).

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/repos_por_ano.py <carga> <saida> clojure elixir ocaml python zig
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estado import BIG, FIM, constroi_estado
from rodar import le_dados

CARGA = Path(sys.argv[1])
SAIDA = Path(sys.argv[2])
LINGUAS = sys.argv[3:]
ANOS = list(range(2008, 2027))
SAIDA.mkdir(parents=True, exist_ok=True)

linhas = []
for lingua in LINGUAS:
    pessoas, eventos = le_dados(CARGA, lingua)
    anos_evento = eventos["dia"].astype("datetime64[Y]").astype(np.int64) + 1970

    # repositórios por ano, com qualquer evento da carga
    tabela = pd.DataFrame({"codigo": eventos["codigo"], "ano": anos_evento.astype(np.int16)})
    tabela = tabela.drop_duplicates()
    com_evento = tabela["ano"].value_counts()
    por_repo = tabela.groupby("codigo")["ano"].agg(["min", "max"])
    primeiro = por_repo["min"].value_counts()
    ultimo = por_repo["max"].value_counts()
    n_repos = len(por_repo)
    del tabela, por_repo

    # estado do S2 (P1, idade descontada, recorte em 31 de dezembro): residentes pelo passado
    est = constroi_estado(pessoas, eventos, 12, "P1", FIM, janela_blocos=None, idade="descontada")
    datas = est["datas"]
    pop_r = est["pop_r"].sum(axis=1)  # repositórios com par ativo de residente no ano
    nascidos_r = np.bincount(est["primeiro_r"][est["primeiro_r"] < BIG], minlength=len(datas))
    for k, data in enumerate(datas):
        ano = int(str(data)[:4])
        linhas.append(
            {
                "linguagem": lingua,
                "ano": ano,
                "repos_com_evento": int(com_evento.get(ano, 0)),
                "repos_primeiro_evento": int(primeiro.get(ano, 0)),
                "repos_ultimo_evento": int(ultimo.get(ano, 0)),
                "repos_com_evento_residente": int(pop_r[k]),
                "repos_primeiro_evento_residente": int(nascidos_r[k]),
                "p1_dezembro": int(est["ativas"][k]),
                "repos_total_na_carga": n_repos,
            }
        )
    for ano in [2025, 2026]:  # depois da grade: só os repositórios por ano
        linhas.append(
            {
                "linguagem": lingua,
                "ano": ano,
                "repos_com_evento": int(com_evento.get(ano, 0)),
                "repos_primeiro_evento": int(primeiro.get(ano, 0)),
                "repos_ultimo_evento": int(ultimo.get(ano, 0)),
                "repos_total_na_carga": n_repos,
            }
        )
    anos_fora = sorted(set(com_evento.index) - set(ANOS))
    print(
        f"{lingua}: {n_repos} repositórios na carga, pessoas {len(pessoas)}, anos com evento fora de 2008 a 2026: {anos_fora}",
        flush=True,
    )
    pd.DataFrame(linhas).to_csv(SAIDA / "repos_por_ano.csv", index=False)
print("pronto")
