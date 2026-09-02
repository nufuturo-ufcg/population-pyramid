"""
Etapa 2A: Mineração de Eventos via GitHub REST API.

Coleta issues, PRs, commit_comments, pr_comments, issue_comments e
issue_events de repositórios Clojure alvo. Roda em paralelo com a
etapa_2B (commits via git clone).

Entrada:
    repositorios_clojure_alvo.csv

Saída:
    eventos_api.csv

A coleta é resumível por repositório:
- complete: não é processado novamente.
- error: é tentado novamente na próxima execução.
"""

import csv
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import common


DATA_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

INPUT_CSV = DATA_DIR / "repositorios_clojure_alvo.csv"
OUTPUT_CSV = DATA_DIR / "eventos_api.csv"
PROGRESS_FILE = DATA_DIR / "reports" / "etapa_2A_progresso.json"


# normalização

def normalize_issue(repo_id, repo_name, issue, collection_started_at):
    labels = [
        label.get("name", "")
        for label in issue.get("labels", [])
        if isinstance(label, dict)
    ]

    return {
        "repo_id": repo_id,
        "repo_name": repo_name,
        "event_type": "issue",
        "number": issue.get("number", ""),
        "title": issue.get("title", ""),
        "author": common._login(issue.get("user")),
        "author_login": common._login(issue.get("user")),
        "author_email": "",
        "created_at": issue.get("created_at", ""),
        "state": issue.get("state", ""),
        "sha": "",
        "message": "",
        "url": issue.get("html_url", ""),
        "labels": ";".join(labels),
        "files": "",
        "collection_status": "complete",
        "collection_started_at": collection_started_at,
    }


def normalize_pr(repo_id, repo_name, pr, pr_files, collection_started_at):
    labels = [
        label.get("name", "")
        for label in pr.get("labels", [])
        if isinstance(label, dict)
    ]

    state = "merged" if pr.get("merged_at") else pr.get("state", "")

    return {
        "repo_id": repo_id,
        "repo_name": repo_name,
        "event_type": "pr",
        "number": pr.get("number", ""),
        "title": pr.get("title", ""),
        "author": common._login(pr.get("user")),
        "author_login": common._login(pr.get("user")),
        "author_email": "",
        "created_at": pr.get("created_at", ""),
        "state": state,
        "sha": (pr.get("head") or {}).get("sha", ""),
        "message": "",
        "url": pr.get("html_url", ""),
        "labels": ";".join(labels),
        "files": ";".join(sorted(pr_files)),
        "collection_status": "complete",
        "collection_started_at": collection_started_at,
    }


def normalize_commit_comment(repo_id, repo_name, comment, lang, collection_started_at):
    return {
        "repo_id": repo_id,
        "repo_name": repo_name,
        "event_type": "commit_comment",
        "number": "",
        "title": "",
        "author": common._login(comment.get("user")),
        "author_login": common._login(comment.get("user")),
        "author_email": "",
        "created_at": comment.get("created_at", ""),
        "state": "",
        "sha": comment.get("commit_id", ""),
        "message": comment.get("body", ""),
        "url": comment.get("html_url", ""),
        "labels": "",
        "files": comment.get("path") or "",
        "language": lang,
        "collection_status": "complete",
        "collection_started_at": collection_started_at,
    }


def normalize_pr_comment(repo_id, repo_name, comment, lang, collection_started_at):
    return {
        "repo_id": repo_id,
        "repo_name": repo_name,
        "event_type": "pr_comment",
        "number": "",
        "title": "",
        "author": common._login(comment.get("user")),
        "author_login": common._login(comment.get("user")),
        "author_email": "",
        "created_at": comment.get("created_at", ""),
        "state": "",
        "sha": comment.get("commit_id", ""),
        "message": comment.get("body", ""),
        "url": comment.get("html_url", ""),
        "labels": "",
        "files": comment.get("path") or "",
        "language": lang,
        "collection_status": "complete",
        "collection_started_at": collection_started_at,
    }


def normalize_issue_comment(repo_id, repo_name, comment, lang, collection_started_at):
    return {
        "repo_id": repo_id,
        "repo_name": repo_name,
        "event_type": "issue_comment",
        "number": "",
        "title": "",
        "author": common._login(comment.get("user")),
        "author_login": common._login(comment.get("user")),
        "author_email": "",
        "created_at": comment.get("created_at", ""),
        "state": "",
        "sha": "",
        "message": comment.get("body", ""),
        "url": comment.get("html_url", ""),
        "labels": "",
        "files": "",
        "language": lang,
        "collection_status": "complete",
        "collection_started_at": collection_started_at,
    }


def normalize_issue_event(repo_id, repo_name, event, lang, collection_started_at):
    label = event.get("label") or {}
    label_name = label.get("name", "") if isinstance(label, dict) else ""
    return {
        "repo_id": repo_id,
        "repo_name": repo_name,
        "event_type": "issue_event",
        "number": (event.get("issue") or {}).get("number", ""),
        "title": (event.get("issue") or {}).get("title", ""),
        "author": common._login(event.get("actor")),
        "author_login": common._login(event.get("actor")),
        "author_email": "",
        "created_at": event.get("created_at", ""),
        "state": (event.get("issue") or {}).get("state", ""),
        "sha": event.get("commit_id") or "",
        "message": event.get("event", ""),
        "url": event.get("url", ""),
        "labels": label_name,
        "files": "",
        "language": lang,
        "collection_status": "complete",
        "collection_started_at": collection_started_at,
    }


# coletores

def collect_issues(repo_id, repo_name, owner, repo, collection_started_at):
    """
    Coleta todas as issues reais.

    O endpoint /issues também retorna PRs. Objetos com a chave `pull_request`
    são descartados aqui porque PR é outro tipo de evento.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    rows = []

    for item in common.get_paginated(
        url,
        params={
            "state": "all",
            "sort": "created",
            "direction": "asc",
        },
    ):
        if "pull_request" not in item:
            rows.append(normalize_issue(repo_id, repo_name, item, collection_started_at))

    return rows


def collect_prs(repo_id, repo_name, owner, repo, collection_started_at):
    """
    Coleta PRs que tocaram pelo menos um arquivo Clojure.

    Para cada PR, consulta /pulls/{number}/files e coleta todos os arquivos.
    Apenas PRs com ao menos um arquivo Clojure são incluídos.
    """
    prs_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    rows = []

    for pr in common.get_paginated(
        prs_url,
        params={
            "state": "all",
            "sort": "created",
            "direction": "asc",
        },
    ):
        number = pr.get("number")
        if number is None:
            continue

        files_url = (
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/files"
        )

        all_files = set()
        has_clojure = False

        for file_data in common.get_paginated(files_url):
            filename = file_data.get("filename", "")
            all_files.add(filename)
            if common.is_clojure_file(filename):
                has_clojure = True

        if has_clojure:
            rows.append(
                normalize_pr(
                    repo_id=repo_id,
                    repo_name=repo_name,
                    pr=pr,
                    pr_files=all_files,
                    collection_started_at=collection_started_at,
                )
            )

    return rows


def collect_commit_comments(repo_id, repo_name, owner, repo, collection_started_at):
    """
    Coleta todos os comentários em commits do repositório.

    Endpoint: GET /repos/{owner}/{repo}/comments
    O campo 'path' indica o arquivo comentado. A extensão desse path
    determina a linguagem do evento.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/comments"
    rows = []
    count = 0

    for item in common.get_paginated(url):
        count += 1
        if count == 1 or count % 500 == 0:
            print(f"    Commit comments: {count}...")
        lang = common.language_from_path(item.get("path") or "")
        rows.append(normalize_commit_comment(repo_id, repo_name, item, lang, collection_started_at))

    return rows


def collect_pr_comments(repo_id, repo_name, owner, repo, collection_started_at):
    """
    Coleta todos os comentários em pull requests do repositório.

    Endpoint: GET /repos/{owner}/{repo}/pulls/comments
    O campo 'path' indica o arquivo comentado. A extensão desse path
    determina a linguagem do evento.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/comments"
    rows = []
    count = 0

    for item in common.get_paginated(url):
        count += 1
        if count == 1 or count % 500 == 0:
            print(f"    PR comments: {count}...")
        lang = common.language_from_path(item.get("path") or "")
        rows.append(normalize_pr_comment(repo_id, repo_name, item, lang, collection_started_at))

    return rows


def collect_issue_comments(repo_id, repo_name, owner, repo, repo_language, collection_started_at):
    """
    Coleta todos os comentários em issues do repositório.

    Endpoint: GET /repos/{owner}/{repo}/issues/comments
    Nenhum arquivo envolvido. O evento recebe a linguagem principal do
    repositório.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/comments"
    rows = []
    count = 0

    for item in common.get_paginated(url):
        count += 1
        if count == 1 or count % 500 == 0:
            print(f"    Issue comments: {count}...")
        rows.append(normalize_issue_comment(repo_id, repo_name, item, repo_language, collection_started_at))

    return rows


def collect_issue_events(repo_id, repo_name, owner, repo, repo_language, collection_started_at):
    """
    Coleta todos os eventos de issues do repositório (fechar, reabrir,
    etiquetar, etc).

    Endpoint: GET /repos/{owner}/{repo}/issues/events
    Nenhum arquivo envolvido. O evento recebe a linguagem principal do
    repositório.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/events"
    rows = []
    count = 0

    for item in common.get_paginated(url):
        count += 1
        if count == 1 or count % 500 == 0:
            print(f"    Issue events: {count}...")
        rows.append(normalize_issue_event(repo_id, repo_name, item, repo_language, collection_started_at))

    return rows


# orquestração

def process_repo(repo_id, repo_name, branch, collection_started_at):
    """
    Orquestra os seis coletores da API REST.

    Cada tipo de evento possui sua própria função:
        collect_issues()
        collect_prs()
        collect_commit_comments()
        collect_pr_comments()
        collect_issue_comments()
        collect_issue_events()
    """
    owner, repo = repo_name.split("/", 1)

    repo_language = common.get_repo_language(owner, repo)

    print("  Coletando issues...")
    issue_rows = collect_issues(repo_id, repo_name, owner, repo, collection_started_at)

    print("  Coletando PRs que tocam Clojure...")
    pr_rows = collect_prs(repo_id, repo_name, owner, repo, collection_started_at)

    print("  Coletando commit comments...")
    commit_comment_rows = collect_commit_comments(repo_id, repo_name, owner, repo, collection_started_at)

    print("  Coletando PR comments...")
    pr_comment_rows = collect_pr_comments(repo_id, repo_name, owner, repo, collection_started_at)

    print("  Coletando issue comments...")
    issue_comment_rows = collect_issue_comments(repo_id, repo_name, owner, repo, repo_language, collection_started_at)

    print("  Coletando issue events...")
    issue_event_rows = collect_issue_events(repo_id, repo_name, owner, repo, repo_language, collection_started_at)

    return (
        issue_rows
        + pr_rows
        + commit_comment_rows
        + pr_comment_rows
        + issue_comment_rows
        + issue_event_rows
    )


def print_repo_event_counts(rows):
    counts = Counter(row["event_type"] for row in rows)
    print(
        f"  Concluído: {counts['issue']} issues, "
        f"{counts['pr']} PRs, "
        f"{counts['commit_comment']} commit_comments, "
        f"{counts['pr_comment']} pr_comments, "
        f"{counts['issue_comment']} issue_comments, "
        f"{counts['issue_event']} issue_events."
    )


def main():
    limit = common.parse_limit(sys.argv[1:])
    common.warn_if_github_token_missing()

    repositories = common.load_repositories(INPUT_CSV)
    repo_status = common.load_progress(PROGRESS_FILE)

    collection_started_at = datetime.now(timezone.utc).isoformat()

    output_exists, _, _ = common.print_collection_summary(
        "A", INPUT_CSV, OUTPUT_CSV, repositories, repo_status,
    )

    with OUTPUT_CSV.open("a", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=common.OUTPUT_FIELDS, delimiter='|')

        if not output_exists:
            writer.writeheader()
            output_file.flush()
            os.fsync(output_file.fileno())

        common.collect_repositories(
            repositories,
            repo_status,
            writer,
            output_file,
            collection_started_at,
            process_repo_fn=process_repo,
            print_counts_fn=print_repo_event_counts,
            progress_file=PROGRESS_FILE,
            limit=limit,
        )

    collection_ended_at = datetime.now(timezone.utc).isoformat()
    common.save_progress(repo_status, PROGRESS_FILE, collection_started_at, collection_ended_at)
    common.print_collection_finished("A", OUTPUT_CSV, PROGRESS_FILE, collection_started_at, collection_ended_at)

    completed = sum(1 for info in repo_status.values() if info.get("status") == "complete")
    common.save_run_stats(DATA_DIR, {
        "etapa_2A": {
            "api_calls": common.api_calls,
            "repos_processed": completed,
        }
    })


if __name__ == "__main__":
    main()
