"""Item 4 de `projecao-rq3/filtro-python/hipoteses.md`: eventos por `repo_id` no arquivo bruto de Python (346 GB). Só lê.

Grava `<saida>/eventos_por_repo_python.csv` (repo_id, eventos). A leitura fica em `adapters/coleta_csv/contagem_por_repo.py`.

Uso (na VM, em baixa prioridade, na raiz do repo): nice -n 19 .venv/bin/python scripts/granularidade/eventos_por_repo.py <eventos_python.csv> <saida>
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.coleta_csv.contagem_por_repo import conta_eventos_por_repo

ARQUIVO, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
inicio = time.time()
conta_eventos_por_repo(ARQUIVO, SAIDA / "eventos_por_repo_python.csv")
print(f"pronto em {(time.time() - inicio) / 60:.1f} minutos")
