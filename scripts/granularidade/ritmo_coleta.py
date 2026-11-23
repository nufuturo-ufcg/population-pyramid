"""Item 4 de `projecao-rq3/filtro-python/hipoteses.md`: ritmo da coleta de Python e razão dos erros dos candidatos não elegíveis. Roda na VM.

Lê os `etapa_2A_progresso.json` e `etapa_2B_progresso.json` dos quatro runs e `<saida>/status_coleta_python.csv`.
Grava `<saida>/ritmo_coleta_python.csv` (por run e etapa) e `<saida>/erros_nao_elegiveis.csv` (texto do erro, etapa, n).

Uso (na VM): .venv/bin/python scripts/granularidade/ritmo_coleta.py <python> <saida>
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

PYTHON, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
status = pd.read_csv(SAIDA / "status_coleta_python.csv", dtype={"repo_id": str})
nao_elegiveis = set(status[~status["elegivel"]]["repo_id"])

ritmo, erros = [], Counter()
for run in ["run-aws-1", "run-batuta-1", "run-batuta-2", "run-vm2-1"]:
    for etapa in ["2A", "2B"]:
        progresso = json.loads(
            (PYTHON / run / "reports" / f"etapa_{etapa}_progresso.json").read_text(encoding="utf-8")
        )
        repos = progresso["repositories"]
        datas = []
        for repo_id, info in repos.items():
            if info["status"] == "complete":
                datas.append(pd.Timestamp(info["updated_at"]))
            elif repo_id in nao_elegiveis:
                texto = re.sub(r"Token \.\.\.\w+", "Token", info["error"])  # sem o fim do token
                texto = re.sub(r"https://api.github.com/repos/\S+:", "<repo>:", texto)
                erros[(texto[:120], etapa)] += 1
        serie = pd.Series(datas)
        horas = (serie.max() - serie.min()).total_seconds() / 3600
        por_hora = serie.dt.floor("h").value_counts()
        ritmo.append(
            {
                "run": run,
                "etapa": etapa,
                "repos_completos": len(serie),
                "primeira_atualizacao": str(serie.min())[:19],
                "ultima_atualizacao": str(serie.max())[:19],
                "horas_entre_a_primeira_e_a_ultima": round(horas, 1),
                "repos_por_hora_media": round(len(serie) / horas, 1) if horas else 0,
                "repos_por_hora_pico": int(por_hora.max()),
                "iniciada_a_ultima_sessao": progresso.get("collection_started_at", ""),
                "terminada_a_ultima_sessao": progresso.get("collection_ended_at", ""),
            }
        )
pd.DataFrame(ritmo).to_csv(SAIDA / "ritmo_coleta_python.csv", index=False)
linhas = [{"erro": e, "etapa": etapa, "n": n} for (e, etapa), n in erros.most_common()]
pd.DataFrame(linhas).to_csv(SAIDA / "erros_nao_elegiveis.csv", index=False)
print("pronto")
