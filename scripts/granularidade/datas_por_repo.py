"""Item 3 de `projecao-rq3/correcao-elegibilidade/hipoteses.md`: primeiro e último evento de cada repositório no arquivo bruto. Só lê.

Grava `<saida>` (repo_id, primeiro, ultimo, eventos). A leitura fica em `adapters/coleta_csv/contagem_por_repo.py`.

Uso (na VM, em baixa prioridade, na raiz do repo):
  nice -n 19 .venv/bin/python scripts/granularidade/datas_por_repo.py <eventos.csv> <saida.csv> [copiados]
Com `copiados`, grava por repositório os commits e os que têm o SHA em outro repositório.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.coleta_csv.contagem_por_repo import commits_copiados_por_repo, datas_por_repo

ARQUIVO, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
COPIADOS = len(sys.argv) > 3 and sys.argv[3] == "copiados"
inicio = time.time()
if COPIADOS:
    commits_copiados_por_repo(ARQUIVO, SAIDA)
else:
    datas_por_repo(ARQUIVO, SAIDA)
print(f"pronto em {(time.time() - inicio) / 60:.1f} minutos")
