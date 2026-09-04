"""
Verifica se eventos_api.csv e eventos_git.csv têm linhas duplicadas.

Duplicatas acontecem quando um repositório já concluído é reprocessado --
por exemplo, pelo bug (já corrigido) de chave int/str em repo_status, que
fazia todo repositório parecer "nunca processado" a cada reinício do
pipeline antes do fix. As linhas resultantes não são idênticas byte a
byte: collection_started_at é gerado uma vez por execução do processo, não
por repositório, então a mesma issue/commit coletada antes e depois de um
reinício tem esse campo diferente. Por isso a verificação ignora essa
coluna ao decidir o que é duplicata, e não compara a linha inteira.

Só leitura -- não altera nenhum arquivo. Pra remover as duplicatas
encontradas, usa scripts/dedupe_eventos.py.

Uso:
    python verificar_duplicatas_eventos.py <run_dir>

Roda contra eventos_api.csv e eventos_git.csv dentro do run_dir informado.
"""

import csv
import sys
from collections import Counter
from pathlib import Path

# O limite padrão do módulo csv (128KB por campo) é menor que o corpo de
# algumas issues/comentários do GitHub -- sem isso, csv.DictReader levanta
# _csv.Error: field larger than field limit em arquivos reais.
csv.field_size_limit(sys.maxsize)

FIELDS_IGNORADOS_NA_CHAVE = {"collection_started_at"}


def find_duplicates(path: Path):
    """
    Retorna (total_linhas, duplicatas_por_repo), onde duplicatas_por_repo é
    {(repo_id, repo_name): quantidade de linhas duplicadas (extras, além da
    primeira ocorrência de cada evento)}.
    """
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="|")
        fieldnames = reader.fieldnames
        rows = list(reader)

    seen = set()
    duplicates_por_repo = Counter()

    for row in rows:
        key = tuple(
            row[field] for field in fieldnames if field not in FIELDS_IGNORADOS_NA_CHAVE
        )
        if key in seen:
            duplicates_por_repo[(row["repo_id"], row["repo_name"])] += 1
        else:
            seen.add(key)

    return len(rows), duplicates_por_repo


def check_file(path: Path):
    print(f"=== {path} ===")
    if not path.exists():
        print("  (arquivo não existe, pulando)")
        return

    total, duplicates_por_repo = find_duplicates(path)
    total_duplicatas = sum(duplicates_por_repo.values())

    print(f"  Total de linhas: {total}")

    if not duplicates_por_repo:
        print("  Nenhuma duplicata encontrada.")
        return

    print(f"  Linhas duplicadas: {total_duplicatas} ({len(duplicates_por_repo)} repositórios afetados)")
    for (repo_id, repo_name), count in sorted(
        duplicates_por_repo.items(), key=lambda x: -x[1]
    ):
        print(f"    {repo_name} (repo_id {repo_id}): {count} linhas duplicadas")


def main():
    if len(sys.argv) < 2:
        print("Uso: python verificar_duplicatas_eventos.py <run_dir>")
        sys.exit(1)

    run_dir = Path(sys.argv[1])

    check_file(run_dir / "eventos_api.csv")
    print()
    check_file(run_dir / "eventos_git.csv")


if __name__ == "__main__":
    main()