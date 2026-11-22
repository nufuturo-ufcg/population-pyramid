"""Estima o tempo total do Python a partir da medição de `rodar.py --amostra 3` (Python, P2, passo de 15 dias).

Modelo: o tempo de uma unidade é o do estado (proporcional ao número de datas) mais o tempo por origem vezes o número de origens. O tempo por origem medido é o de datas
tardias, as mais caras, e o do Holt cresce com a série, então a estimativa é um teto aproximado para os passos mais longos.

Uso: .venv/bin/python scripts/granularidade/estimar.py <segundos do estado, passo de 15 dias> <segundos por origem, passo de 15 dias> [fator de teste de vazamento]
"""

import sys

estado_15d, por_origem = float(sys.argv[1]), float(sys.argv[2])
fator_vazamento = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
DATAS = {12: 17, 6: 34, 3: 68, 2: 102, 1: 204, 0.5: 408}
ORIGENS = {12: 15, 6: 31, 3: 63, 2: 95, 1: 191, 0.5: 383}
total = 0.0
print("passo  unidades  estado(s)  origens(s)  total(h)")
for passo in [12, 6, 3, 2, 1, 0.5]:
    unidades = 3 if passo == 12 else 2  # P0, P1 e P2 só em 12 meses
    estado = estado_15d * DATAS[passo] / DATAS[0.5]
    origens = por_origem * ORIGENS[passo]
    por_unidade = estado + origens
    horas = unidades * por_unidade * (1 + fator_vazamento) / 3600
    total += horas
    print(f"{passo:>5}  {unidades:>8}  {estado:>9.0f}  {origens:>10.0f}  {horas:>8.2f}")
print(
    f"Python, todos os passos: cerca de {total:.1f} horas (sem contar a carga dos dados nem a fila da VM)"
)
