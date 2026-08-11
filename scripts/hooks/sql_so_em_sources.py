"""Hook: SQL só existe dentro de `src/pyramid/sources/`.

A regra vem da separação entre origem e motor de cálculo (seção 8 da spec).
Todo `SELECT` mora numa fonte; o resto do pipeline recebe DataFrame já no
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

PERMITIDO = Path("src/pyramid/sources")
# O próprio hook carrega os padrões que procura. Auditar a si mesmo daria
# violação em toda rodada.
ISENTO = Path("scripts/hooks")
# Só o começo de um comando SQL dentro de string. `select` como palavra solta
# aparece em prosa e em nome de método de DataFrame.
SQL = re.compile(
    r"""["'\s(]\s*(SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\s""",
    re.IGNORECASE | re.DOTALL,
)
ESTIMATIVA = re.compile(r"information_schema\.table_rows", re.IGNORECASE)


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
    if PERMITIDO in caminho.parents:
        return achados
    for m in SQL.finditer(texto):
        linha = texto.count("\n", 0, m.start()) + 1
        comando = m.group(1).split()[0].upper()
        achados.append(
            f"{caminho}:{linha}: {comando} fora de {PERMITIDO}/. "
            f"SQL vive numa fonte; o motor de cálculo recebe DataFrame."
        )
    return achados


def main(argv: list[str]) -> int:
    """Recebe os arquivos do commit e devolve 1 se algum quebrar a regra."""
    achados: list[str] = []
    for arg in argv:
        caminho = Path(arg)
        if caminho.suffix != ".py" or not caminho.exists():
            continue
        if ISENTO in caminho.parents:
            continue
        achados += _violacoes(caminho)
    for a in achados:
        print(a, file=sys.stderr)
    return 1 if achados else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
