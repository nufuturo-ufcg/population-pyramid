"""
Etapa 2B: Mineração de Commits via Git Clone.

Coleta commits de repositórios Clojure alvo usando git clone --bare
--filter=blob:none. Roda em paralelo com a etapa_2A (GitHub REST API).

Entrada:
    repositorios_clojure_alvo.csv

Saída:
    eventos_git.csv

A coleta é resumível por repositório:
- complete: não é processado novamente.
- error: é tentado novamente na próxima execução.
"""

import csv
import os
import shutil
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import common

common.STAGE_LABEL = "2B"


DATA_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

INPUT_CSV = DATA_DIR / "repositorios_clojure_alvo.csv"
OUTPUT_CSV = DATA_DIR / "eventos_git.csv"
PROGRESS_FILE = DATA_DIR / "reports" / "etapa_2B_progresso.json"

# Timeout do `git clone` (segundos). --filter=blob:none já evita baixar
# conteúdo de arquivo, só histórico/metadados, então mesmo repositórios
# grandes (ex.: metabase, ~2GB de blobs) devem terminar bem antes disso numa
# conexão saudável; 10 min é folga suficiente sem deixar uma conexão morta
# pendurada por horas (ver run_git em common.py).
CLONE_TIMEOUT_SECONDS = 600

# Quantos `git clone`/repositório rodam em paralelo. Diferente da etapa_2A,
# aqui não existe cota de token limitando isso -- o teto real é rede/disco
# da máquina (múltiplos clones grandes ao mesmo tempo competem por banda e
# espaço temporário) e o risco de acionar o rate limit "secondary" do
# GitHub por operações git concorrentes demais vindas do mesmo IP. 4 é um
# ponto de partida conservador; ajuste com a env var abaixo sem precisar
# editar o código, ex.: ETAPA_2B_WORKERS=8 python3 scripts/etapa_2B_eventos.py ...
CLONE_WORKERS = int(os.environ.get("ETAPA_2B_WORKERS", "4"))


# normalização

def normalize_commit(repo_id, repo_name, commit, collection_started_at):
    return {
        "repo_id": repo_id,
        "repo_name": repo_name,
        "event_type": "commit",
        "number": "",
        "title": "",
        "author": commit["author"],
        "author_login": "",
        "author_email": commit["author_email"],
        "created_at": commit["created_at"],
        "state": "",
        "sha": commit["sha"],
        "message": commit["message"],
        "url": f"https://github.com/{repo_name}/commit/{commit['sha']}",
        "labels": "",
        "files": ";".join(sorted(commit["touched_files"])),
        "language": "",
        "collection_status": "complete",
        "collection_started_at": collection_started_at,
    }


# git

def clone_bare_repository(repo_name, destination):
    """
    Faz clone bare sem blobs.

    O histórico e os nomes de caminhos ficam disponíveis, mas o conteúdo
    completo dos arquivos não é baixado.
    """
    clone_url = f"https://github.com/{repo_name}.git"

    common.run_git(
        [
            "clone",
            "--bare",
            "--filter=blob:none",
            "--no-tags",
            clone_url,
            str(destination),
        ],
        timeout=CLONE_TIMEOUT_SECONDS,
    )


def get_commit_files_from_git(repo_dir):
    """
    Usa `git log --all --name-only` para mapear SHA -> arquivos tocados.

    Retorna todos os arquivos de cada commit, sem filtro por extensão.
    Isso considera todo o histórico disponível em todas as refs do clone,
    inclusive commits relativos a arquivos que já foram removidos da árvore
    atual do repositório.
    """
    marker = "__ETAPA2_COMMIT__"

    output = common.run_git(
        [
            "log",
            "--all",
            f"--format={marker}%H",
            "--name-only",
            "--no-renames",
        ],
        cwd=repo_dir,
    )

    commits = {}
    current_sha = None

    for raw_line in output.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith(marker):
            current_sha = line[len(marker):].strip()
            commits.setdefault(current_sha, set())
            continue

        if current_sha is not None:
            commits[current_sha].add(line)

    return commits


def get_commit_metadata(repo_dir, sha):
    """Obtém metadados de um commit diretamente do clone local."""
    # Separadores de controle reduzem o risco de colisão com texto do commit.
    field_sep = "\x1f"
    format_string = "%H%x1f%an%x1f%ae%x1f%aI%x1f%B"

    output = common.run_git(
        [
            "show",
            "-s",
            f"--format={format_string}",
            sha,
        ],
        cwd=repo_dir,
    )

    parts = output.split(field_sep, 4)
    if len(parts) != 5:
        raise RuntimeError(f"Não foi possível interpretar metadados do commit {sha}")

    parsed_sha, author, author_email, created_at, message = parts

    return {
        "sha": parsed_sha.strip(),
        "author": author.strip(),
        "author_email": author_email.strip(),
        "created_at": created_at.strip(),
        "message": message.rstrip(),
    }


# coletor

def collect_commits(repo_id, repo_name, collection_started_at):
    """
    Coleta commits de um repositório usando Git local.

    Fluxo:
        git clone --bare --filter=blob:none
        -> git log --all --name-only
        -> mapeia SHA -> todos os arquivos tocados
        -> obtém metadados dos SHAs selecionados

    Não faz requisições à API do GitHub. Todos os dados vêm do clone local.
    """

    temp_root = Path(tempfile.mkdtemp(prefix="etapa2_git_"))
    repo_dir = temp_root / "repository.git"

    try:
        common.log("    Clonando histórico Git sem blobs...")
        clone_bare_repository(repo_name, repo_dir)

        common.log("    Analisando arquivos tocados por cada commit...")
        commit_files = get_commit_files_from_git(repo_dir)

        rows = []
        total = len(commit_files)

        for index, (sha, touched_files) in enumerate(commit_files.items(), start=1):
            if index == 1 or index % 500 == 0 or index == total:
                common.log(f"    Metadados de commits: {index}/{total}")

            metadata = get_commit_metadata(repo_dir, sha)
            metadata["touched_files"] = touched_files
            rows.append(normalize_commit(repo_id, repo_name, metadata, collection_started_at))

        return rows

    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


# orquestração

def process_repo(repo_id, repo_name, branch, collection_started_at):
    """Orquestra o coletor de commits via git clone."""
    common.log("  Coletando commits...")
    commit_rows = collect_commits(repo_id, repo_name, collection_started_at)

    return commit_rows


def print_repo_event_counts(rows):
    counts = Counter(row["event_type"] for row in rows)
    common.log(f"  Concluído: {counts['commit']} commits.")


def main():
    limit = common.parse_limit(sys.argv[1:])

    repositories = common.load_repositories(INPUT_CSV)
    repo_status = common.load_progress(PROGRESS_FILE)

    collection_started_at = datetime.now(timezone.utc).isoformat()

    output_exists, _, _ = common.print_collection_summary(
        "B", INPUT_CSV, OUTPUT_CSV, repositories, repo_status,
    )

    common.log(
        f"INFO: coletando com {CLONE_WORKERS} clones em paralelo "
        f"(ajustável via ETAPA_2B_WORKERS)."
    )

    with OUTPUT_CSV.open("a", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=common.OUTPUT_FIELDS, delimiter='|')

        if not output_exists:
            writer.writeheader()
            output_file.flush()
            os.fsync(output_file.fileno())

        common.collect_repositories_threaded(
            repositories,
            repo_status,
            writer,
            output_file,
            collection_started_at,
            process_repo_fn=process_repo,
            print_counts_fn=print_repo_event_counts,
            progress_file=PROGRESS_FILE,
            max_workers=CLONE_WORKERS,
            limit=limit,
            # etapa_2B não usa a API REST nem tokens -- sem initializer, as
            # threads não precisam de nenhum setup antes de processar (ver
            # collect_repositories_threaded em common.py).
            initializer=None,
        )

    collection_ended_at = datetime.now(timezone.utc).isoformat()
    common.save_progress(repo_status, PROGRESS_FILE, collection_started_at, collection_ended_at)
    common.print_collection_finished("B", OUTPUT_CSV, PROGRESS_FILE, collection_started_at, collection_ended_at)

    completed = sum(1 for info in repo_status.values() if info.get("status") == "complete")
    common.save_run_stats(DATA_DIR, {
        "etapa_2B": {
            "api_calls": 0,
            "repos_processed": completed,
        }
    })


if __name__ == "__main__":
    main()