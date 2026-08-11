"""Hook de commit-msg: barra assinatura de assistente e mensagem vazia.

Nenhum commit deste repositório leva `Co-authored-by` de assistente nem linha de
propaganda de ferramenta. A autoria do commit é de quem o assina.

O hook também exige assunto curto e linha em branco antes do corpo, que é o que
mantém `git log --oneline` legível.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

LIMITE_ASSUNTO = 72

PROIBIDO = [
    (
        re.compile(r"^\s*co-authored-by:.*(claude|anthropic|copilot|cursor)", re.I | re.M),
        "trailer de coautoria de assistente",
    ),
    (
        re.compile(r"generated with .*(claude|copilot|cursor)", re.I),
        "linha de propaganda de ferramenta",
    ),
    (re.compile(r"🤖"), "emoji de robô na mensagem"),
]


def problemas(msg: str) -> list[str]:
    """Lista o que impede a mensagem de virar commit."""
    linhas = [ln for ln in msg.splitlines() if not ln.lstrip().startswith("#")]
    achados = [f"mensagem tem {motivo}." for padrao, motivo in PROIBIDO if padrao.search(msg)]
    if not linhas or not linhas[0].strip():
        achados.append("mensagem sem assunto.")
        return achados
    if len(linhas[0]) > LIMITE_ASSUNTO:
        achados.append(f"assunto com {len(linhas[0])} caracteres (limite {LIMITE_ASSUNTO}).")
    if len(linhas) > 1 and linhas[1].strip():
        achados.append("falta linha em branco entre assunto e corpo.")
    return achados


def main(argv: list[str]) -> int:
    """Recebe o arquivo da mensagem que o git passa ao hook."""
    if not argv:
        print("uso: mensagem_de_commit.py <arquivo>", file=sys.stderr)
        return 2
    achados = problemas(Path(argv[0]).read_text(encoding="utf-8"))
    for a in achados:
        print(f"commit recusado: {a}", file=sys.stderr)
    return 1 if achados else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
