"""Reconstrói as partes do arquivo final de eventos da Python (`python-completo/eventos_python.csv`) e calcula o SHA-256 de cada uma.

O arquivo final é a junção dos 8 arquivos das 4 partes, na ordem de `MANIFESTO.txt`, sem o cabeçalho
dos 7 últimos, mais 4 trechos anexados depois (sem cabeçalho). Cada parte reconstruída é
cabeçalho + corpo + trecho anexado, igual ao arquivo de origem. Só lê o final e grava em `<saida>`.

Uso: python3 particiona_final.py <eventos_python.csv> <saida> <parte>
  <parte>: aws_api, aws_git, vm2_api, vm2_git, b1_api, b1_git, b2_api ou b2_git
Grava `<saida>/<parte>.csv` e `<saida>/<parte>.sha256` (hash, bytes).
"""

import hashlib
import sys
from pathlib import Path

FINAL, SAIDA, PARTE = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
CABECALHO = 171
TAMANHO_ORIGINAL = 343985220020
BLOCO = 64 * 1024 * 1024
ARQUIVOS = [
    ("aws_api", 53742096262),
    ("aws_git", 78273865488),
    ("vm2_api", 20658836966),
    ("vm2_git", 171),
    ("b1_api", 17613951539),
    ("b1_git", 171),
    ("b2_api", 77129338272),
    ("b2_git", 96567132348),
]
ANEXADOS = [
    ("b1_api", 93468493),
    ("aws_api", 1631486093),
    ("aws_git", 22088),
    ("vm2_api", 333154758),
]

faixas: dict[str, list[tuple[int, int]]] = {}
posicao = 0
for numero, (nome, tamanho) in enumerate(ARQUIVOS):
    corpo = tamanho if numero == 0 else tamanho - CABECALHO
    faixas[nome] = [(posicao, corpo)]
    posicao += corpo
assert posicao == TAMANHO_ORIGINAL, (posicao, TAMANHO_ORIGINAL)
for nome, tamanho in ANEXADOS:
    faixas[nome].append((posicao, tamanho))
    posicao += tamanho
assert posicao == FINAL.stat().st_size, (posicao, FINAL.stat().st_size)

SAIDA.mkdir(parents=True, exist_ok=True)
hash_parte = hashlib.sha256()
bytes_parte = 0
with FINAL.open("rb") as entrada, (SAIDA / f"{PARTE}.csv").open("wb") as saida:
    if PARTE != "aws_api":
        entrada.seek(0)
        cabecalho = entrada.read(CABECALHO)
        saida.write(cabecalho)
        hash_parte.update(cabecalho)
        bytes_parte += len(cabecalho)
    for inicio, comprimento in faixas[PARTE]:
        entrada.seek(inicio)
        restante = comprimento
        while restante > 0:
            dados = entrada.read(min(BLOCO, restante))
            saida.write(dados)
            hash_parte.update(dados)
            bytes_parte += len(dados)
            restante -= len(dados)
(SAIDA / f"{PARTE}.sha256").write_text(
    f"{hash_parte.hexdigest()} {bytes_parte}\n", encoding="utf-8"
)
print(PARTE, hash_parte.hexdigest(), bytes_parte)
