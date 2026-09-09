"""
Wrapper do etapa_2_orchestrator.py que redireciona stdout+stderr
para um arquivo de log e para o terminal simultaneamente.

Uso:
    python capturar_logs.py <run_dir> --language <linguagem> [--limit N]

O run_dir deve conter:
    repositorios_{language}_alvo.csv  (saída da Etapa 1 ou fonte externa)

Obrigatório:
    --language <nome>  Linguagem-alvo (clojure, elixir, ...)

Opcional:
    --limit N  Processa no máximo N repositórios novos (pulando já coletados)

Saída:
    reports/etapa_2.log  Log com timestamp de toda a execução
"""

import os
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import common

SCRIPT_DIR = Path(__file__).resolve().parent


def main():
    if len(sys.argv) < 2:
        print(
            f"Uso: {sys.executable} {__file__} <run_dir> "
            f"--language <linguagem> [--limit N]"
        )
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    language = common.parse_language(sys.argv[2:])
    limit = common.parse_limit(sys.argv[2:])

    if language is None:
        print("ERRO: --language é obrigatório.")
        print(f"Disponíveis: {', '.join(sorted(common.LANGUAGE_CONFIGS))}")
        sys.exit(1)

    if not run_dir.exists():
        print(f"Diretório não encontrado: {run_dir}")
        sys.exit(1)

    input_csv = common.input_csv_path(run_dir, language)
    if not input_csv.exists():
        print(f"CSV de entrada não encontrado: {input_csv}")
        sys.exit(1)

    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    log_path = reports_dir / "etapa_2.log"

    log_file = open(log_path, "a", encoding="utf-8", buffering=1)

    def _timestamp():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.") + f"{datetime.now().microsecond // 1000:03d}"

    def _write_log(line):
        log_file.write(f"{_timestamp()} | {line}")
        log_file.flush()

    def _close_log(rc):
        _write_log(f"# exit code: {rc}\n")
        log_file.close()

    # Ctrl-C fecha o log e sai com 130
    def _sigint_handler(sig, frame):
        _close_log(130)
        sys.exit(130)

    signal.signal(signal.SIGINT, _sigint_handler)

    # Monta argumentos para o orchestrator
    cmd = [sys.executable, str(SCRIPT_DIR / "etapa_2_orchestrator.py"), str(run_dir)]
    cmd += ["--language", language]
    if limit is not None:
        cmd += ["--limit", str(limit)]

    env = {**os.environ, "PYTHONUNBUFFERED": "1"}

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    # Lê linha a linha: terminal + log
    for line in proc.stdout:
        print(line, end="")
        if line.endswith("\n"):
            _write_log(line)
        else:
            _write_log(line + "\n")

    rc = proc.wait()
    _close_log(rc)
    sys.exit(rc)


if __name__ == "__main__":
    main()
