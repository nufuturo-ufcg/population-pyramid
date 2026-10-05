"""Teste sem framework: run_git aceita saída do git que não é UTF-8.

O próprio `git commit` converte mensagem em latin-1 para UTF-8, então o commit
é montado com o comando de baixo nível (hash-object --literally), como acontece
em histórico importado de outros sistemas.

Rodar: cd scripts && ../venv/bin/python test_run_git_utf8.py
"""

import subprocess
import tempfile
from pathlib import Path

import common


def git(repo: Path, *args: str, entrada: bytes | None = None) -> str:
    """Roda git no repositório de teste e devolve o stdout (texto)."""
    resultado = subprocess.run(
        ["git", *args], cwd=repo, input=entrada, check=True, capture_output=True
    )
    return resultado.stdout.decode("utf-8", errors="replace").strip()


def main() -> None:
    """Commit com mensagem em latin-1 não pode derrubar a leitura do histórico."""
    repo = Path(tempfile.mkdtemp())
    git(repo, "init", "-q")
    arvore = git(repo, "mktree", entrada=b"")
    commit = (
        f"tree {arvore}\nauthor t <t@t> 0 +0000\ncommitter t <t@t> 0 +0000\n\n".encode()
        + "correção em latin-1\n".encode("latin-1")
    )
    sha = git(repo, "hash-object", "-t", "commit", "-w", "--stdin", "--literally", entrada=commit)
    git(repo, "update-ref", "refs/heads/main", sha)

    saida = common.run_git(["log", "-1", "--format=%B", "main"], cwd=repo)

    assert "�" in saida  # o byte inválido virou caractere de substituição
    assert "em latin-1" in saida  # o resto da mensagem chegou inteiro
    print("ok")


if __name__ == "__main__":
    main()
