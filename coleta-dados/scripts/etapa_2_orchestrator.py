"""
Orquestrador da Etapa 2: executa etapa_2A e etapa_2B em paralelo e
faz o merge dos CSVs de saída.

Uso:
    python etapa_2_orchestrator.py <run_dir> --language <linguagem> [--limit N]

O run_dir deve conter:
    repositorios_{language}_alvo.csv  (saída da Etapa 1 ou fonte externa)

Obrigatório:
    --language <nome>  Linguagem-alvo (clojure, elixir, ...)

Opcional:
    --limit N  Processa no máximo N repositórios novos (pulando já coletados)

Após a execução, o run_dir conterá:
    eventos_api.csv     (saída da etapa_2A)
    eventos_git.csv     (saída da etapa_2B)
    eventos_repositorios.csv  (merge dos dois)
    reports/
        etapa_2A_progresso.json
        etapa_2B_progresso.json
"""

import json
import subprocess
import sys
from pathlib import Path

import common


SCRIPT_DIR = Path(__file__).resolve().parent


def merge_csvs(api_csv, git_csv, output_csv):
    """
    Faz o merge de dois CSVs em um único arquivo.

    Ambos os CSVs têm o mesmo schema (OUTPUT_FIELDS de common.py).
    O resultado contém o header de um deles seguido de todas as linhas
    de dados dos dois arquivos, sem duplicação de header.
    """
    if not api_csv.exists() and not git_csv.exists():
        print("Nenhum CSV para merge.")
        return

    # Determina qual CSV tem header para usar como referência
    source_csv = api_csv if api_csv.exists() else git_csv

    with output_csv.open("w", newline="", encoding="utf-8") as out:
        # Copia header do CSV fonte
        with source_csv.open("r", encoding="utf-8") as f:
            header_line = f.readline()
            out.write(header_line)

        # Copia linhas de dados de ambos os CSVs
        for csv_file in (api_csv, git_csv):
            if not csv_file.exists():
                continue
            with csv_file.open("r", encoding="utf-8") as f:
                # Pula o header
                f.readline()
                for line in f:
                    out.write(line)


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

    api_csv = run_dir / "eventos_api.csv"
    git_csv = run_dir / "eventos_git.csv"
    output_csv = run_dir / "eventos_repositorios.csv"

    print("=== Etapa 2: coleta de eventos (paralela) ===")
    print(f"  Linguagem:   {language}")
    print(f"  Entrada:     {input_csv}")
    print(f"  Script API:  etapa_2A_eventos.py")
    print(f"  Script Git:  etapa_2B_eventos.py")
    print(f"  Diretório:   {run_dir}")
    if limit is not None:
        print(f"  Limite:      {limit} repositórios novos")
    print()

    # Monta argumentos extras para os subprocessos
    extra_args = ["--language", language]
    if limit is not None:
        extra_args += ["--limit", str(limit)]

    # Roda os dois scripts em paralelo
    api_proc = subprocess.Popen(
        [sys.executable, str(SCRIPT_DIR / "etapa_2A_eventos.py"), str(run_dir)] + extra_args,
    )
    git_proc = subprocess.Popen(
        [sys.executable, str(SCRIPT_DIR / "etapa_2B_eventos.py"), str(run_dir)] + extra_args,
    )

    # Aguarda ambos terminarem
    api_proc.wait()
    git_proc.wait()

    # Verifica erros
    failed = []
    if api_proc.returncode != 0:
        failed.append(f"etapa_2A terminou com código {api_proc.returncode}")
    if git_proc.returncode != 0:
        failed.append(f"etapa_2B terminou com código {git_proc.returncode}")

    if failed:
        for msg in failed:
            print(f"ERRO: {msg}")
        sys.exit(1)

    # Merge dos CSVs
    print()
    print("=== Merge dos CSVs ===")
    merge_csvs(api_csv, git_csv, output_csv)
    print(f"Merge concluído: {output_csv}")

    # Estatísticas consolidadas
    stats_file = run_dir / "reports" / "estatisticas.json"
    if stats_file.exists():
        try:
            with stats_file.open("r", encoding="utf-8") as f:
                stats = json.load(f)
            total_api = (
                stats.get("etapa_1", {}).get("api_calls", 0)
                + stats.get("etapa_2A", {}).get("api_calls", 0)
                + stats.get("etapa_2B", {}).get("api_calls", 0)
            )
            print()
            print("=== Estatísticas da run ===")
            for etapa_name in ("etapa_1", "etapa_2A", "etapa_2B"):
                etapa = stats.get(etapa_name, {})
                if etapa:
                    calls = etapa.get("api_calls", 0)
                    repos = etapa.get("repos_processed") or etapa.get("repos_valid") or etapa.get("repos_scanned", 0)
                    print(f"  {etapa_name}: {calls} requisições API, {repos} repositórios")
            print(f"  Total: {total_api} requisições API")
            print(f"  Arquivo: {stats_file}")
        except (OSError, json.JSONDecodeError):
            pass

    print()
    print("=== Etapa 2 concluída ===")


if __name__ == "__main__":
    main()
