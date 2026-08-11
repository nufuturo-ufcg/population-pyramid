"""Hook: SQL só existe dentro de `adapters/` e de `src/pyramid/sources/`.

A regra vem da separação entre origem e motor de cálculo, em `CONTRIBUTING.md`.
Todo `SELECT` mora num adaptador; o resto do pipeline recebe DataFrame já no
formato canônico de eventos. Quebrar isso amarra o cálculo ao MySQL do MSR'14 e
inviabiliza a segunda fonte de dados.

O hook também barra `information_schema.table_rows`, que devolve estimativa do
otimizador e já entregou contagem errada em sanity check. A contagem é
`COUNT(*)`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
# `adapters/` guarda um adaptador por dataset; `src/pyramid/sources/` guarda o
# contrato e o loader. Os dois podem conter SQL.
PERMITIDO = (Path("adapters"), Path("src/pyramid/sources"))
# O próprio hook carrega os padrões que procura. Auditar a si mesmo daria
# violação em toda rodada.
ISENTO = Path("scripts/hooks")
# O teste do hook carrega SQL de exemplo para provar que o hook pega. Ele é o
# único arquivo isento fora da pasta acima, e está nomeado aqui de propósito:
# a lista é curta e revisável em code review.
ISENTOS = (Path("tests/test_hooks.py"),)
# Só o começo de um comando SQL dentro de string. `select` como palavra solta
# aparece em prosa e em nome de método de DataFrame.
SQL = re.compile(
    r"""["'\s(]\s*(SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\s""",
    re.IGNORECASE | re.DOTALL,
)
ESTIMATIVA = re.compile(r"information_schema\.table_rows", re.IGNORECASE)


def _sob(caminho: Path, pasta: Path) -> bool:
    """Diz se `caminho` está dentro de `pasta`, do jeito que o git entrega.

    O prek passa caminho relativo à raiz do repo, mas `git commit` com hook
    chamado à mão passa absoluto. Comparar `Path("scripts/hooks")` contra os
    parents de um caminho absoluto dá sempre falso, e o hook passaria a acusar
    a si mesmo e a própria fonte MSR14.
    """
    return (RAIZ / pasta) in (RAIZ / caminho).resolve().parents


def _e_isento(caminho: Path) -> bool:
    """Diz se o arquivo está na lista curta de isentos nomeados."""
    alvo = (RAIZ / caminho).resolve()
    return any((RAIZ / f).resolve() == alvo for f in ISENTOS)


def _violacoes(caminho: Path) -> list[str]:
    """Lista os problemas de um arquivo, em texto pronto para o terminal."""
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    achados: list[str] = []
    for m in ESTIMATIVA.finditer(texto):
        linha = texto.count("\n", 0, m.start()) + 1
        achados.append(
            f"{caminho}:{linha}: information_schema.table_rows é estimativa do otimizador. "
            f"Use COUNT(*)."
        )
    if any(_sob(caminho, pasta) for pasta in PERMITIDO):
        return achados
    onde = " nem ".join(f"{p}/" for p in PERMITIDO)
    for m in SQL.finditer(texto):
        linha = texto.count("\n", 0, m.start()) + 1
        comando = m.group(1).split()[0].upper()
        achados.append(
            f"{caminho}:{linha}: {comando} fora de {onde}. "
            f"SQL vive num adaptador; o motor de cálculo recebe DataFrame."
        )
    return achados


def main(argv: list[str]) -> int:
    """Recebe os arquivos do commit e devolve 1 se algum quebrar a regra."""
    achados: list[str] = []
    for arg in argv:
        caminho = Path(arg)
        if caminho.suffix != ".py" or not caminho.exists():
            continue
        if _sob(caminho, ISENTO) or _e_isento(caminho):
            continue
        achados += _violacoes(caminho)
    for a in achados:
        print(a, file=sys.stderr)
    return 1 if achados else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
