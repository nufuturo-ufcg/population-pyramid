"""Tabelas do Markdown de duas rodadas lado a lado: o valor antigo e o novo na mesma célula (`antigo → novo`).

Casa as tabelas de cada arquivo pela ordem em que aparecem. Células iguais aparecem uma vez só. Se duas tabelas
casadas têm forma diferente, as duas saem separadas, uma abaixo da outra. Não interpreta nenhum número.

Uso: python3 compara_tabelas.py <saida.md> <titulo> <antigo.md> <novo.md> [<titulo> <antigo.md> <novo.md> ...]
"""

import sys
from pathlib import Path

SAIDA = Path(sys.argv[1])
TRIOS = sys.argv[2:]


def le_blocos(caminho: Path) -> list[tuple[str, list[list[str]]]]:
    """Cada tabela do arquivo com o último título que a precede."""
    blocos = []
    titulo = ""
    atual: list[list[str]] = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        if linha.startswith("#"):
            titulo = linha.lstrip("# ").strip()
        if linha.startswith("|"):
            atual.append([c.strip() for c in linha.strip().strip("|").split("|")])
            continue
        if atual:
            blocos.append((titulo, atual))
            atual = []
    if atual:
        blocos.append((titulo, atual))
    return blocos


def separador(linha: list[str]) -> bool:
    return all(set(c) <= set("-: ") for c in linha)


def junta(antiga: list[list[str]], nova: list[list[str]]) -> list[str]:
    linhas = []
    for a, n in zip(antiga, nova, strict=True):
        if separador(a):
            linhas.append("|" + "|".join("---" for _ in a) + "|")
            continue
        celulas = []
        for x, y in zip(a, n, strict=True):
            celulas.append(x if x == y else f"{x} → {y}")
        linhas.append("| " + " | ".join(celulas) + " |")
    return linhas


def como_texto(tabela: list[list[str]]) -> list[str]:
    linhas = []
    for linha in tabela:
        if separador(linha):
            linhas.append("|" + "|".join("---" for _ in linha) + "|")
        else:
            linhas.append("| " + " | ".join(linha) + " |")
    return linhas


saida = [
    "# Valores antigos e novos lado a lado",
    "",
    "Cada célula mostra `antigo → novo`. Célula igual aparece uma vez. Os caminhos de cada par estão na seção.",
    "",
]
for i in range(0, len(TRIOS), 3):
    titulo, antigo, novo = TRIOS[i], Path(TRIOS[i + 1]), Path(TRIOS[i + 2])
    saida += [f"## {titulo}", "", f"Antigo: `{antigo}`. Novo: `{novo}`.", ""]
    blocos_a, blocos_n = le_blocos(antigo), le_blocos(novo)
    total = max(len(blocos_a), len(blocos_n))
    for j in range(total):
        if j >= len(blocos_a) or j >= len(blocos_n):
            saida += ["Tabela sem par no outro arquivo.", ""]
            continue
        titulo_a, tab_a = blocos_a[j]
        titulo_n, tab_n = blocos_n[j]
        saida += [f"### {titulo_n or titulo_a}", ""]
        if len(tab_a) == len(tab_n) and len(tab_a[0]) == len(tab_n[0]):
            saida += junta(tab_a, tab_n)
        else:
            saida += ["Forma diferente (as duas tabelas, separadas).", "", "Antigo:", ""]
            saida += [*como_texto(tab_a), "", "Novo:", "", *como_texto(tab_n)]
        saida.append("")
SAIDA.write_text("\n".join(saida), encoding="utf-8")
print(f"{SAIDA}: {len(saida)} linhas")
