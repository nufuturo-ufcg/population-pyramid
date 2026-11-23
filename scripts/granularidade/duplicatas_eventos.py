"""Linhas repetidas de um CSV bruto da coleta, por repositório e tipo de evento. Só lê.

Uso (na VM, em baixa prioridade, na raiz do repo):
  nice -n 19 .venv/bin/python scripts/granularidade/duplicatas_eventos.py <eventos.csv> <saida.csv> [memoria_gb threads]
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.coleta_csv.contagem_por_repo import duplicatas_por_repo

inicio = time.time()
if len(sys.argv) > 4:
    duplicatas_por_repo(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
else:
    duplicatas_por_repo(Path(sys.argv[1]), Path(sys.argv[2]))
print(f"pronto em {(time.time() - inicio) / 60:.1f} minutos")
