"""Estima o tempo total do Python, versões A e B juntas, a partir da medição de `rodar.py --amostra 3` (Python, P2, passo de 15 dias).

Modelo: o tempo de uma unidade é o do estado (proporcional ao número de datas) mais, para cada versão, o tempo por origem vezes o número de origens. A versão B só roda em P1 e P2. O tempo por origem medido é o de datas
tardias, as mais caras, e o do Holt cresce com a série, então a estimativa é um teto aproximado para os passos mais longos.

Uso: .venv/bin/python scripts/granularidade/estimar.py <segundos do estado, passo de 15 dias> <segundos por origem da A> <segundos por origem da B> [1 com teste de vazamento (padrão) ou 0 sem]
"""

import sys

estado_15d, por_origem_a, por_origem_b = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
fator_vazamento = (
    float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
)  # 1 inclui o teste de vazamento, 0 não
DATAS = {12: 17, 6: 34, 3: 68, 2: 102, 1: 204, 0.5: 408}
ORIGENS = {12: 15, 6: 31, 3: 63, 2: 95, 1: 191, 0.5: 383}
total = 0.0
print("passo  estado(s)  origens A(s)  origens B(s)  total(h)")
for passo in [12, 6, 3, 2, 1, 0.5]:
    # P1 e P2 rodam A e B; P0 (só em 12 meses) roda só a A
    estado = estado_15d * DATAS[passo] / DATAS[0.5]
    origens_a = por_origem_a * ORIGENS[passo]
    origens_b = por_origem_b * ORIGENS[passo]
    vazamento = (
        25 * 0.5 * estado * fator_vazamento
    )  # 5 origens x 5 estados reconstruídos, em média com metade dos dados
    segundos = 2 * (estado + origens_a + origens_b + vazamento)
    if passo == 12:
        segundos += estado + origens_a
    horas = segundos / 3600
    total += horas
    print(f"{passo:>5}  {estado:>9.0f}  {origens_a:>12.0f}  {origens_b:>12.0f}  {horas:>8.2f}")
print(
    f"Python, todos os passos: cerca de {total:.1f} horas (sem contar a carga dos dados nem a fila da VM)"
)
