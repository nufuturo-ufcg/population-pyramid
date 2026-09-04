"""
Verifica se reports/etapa_2A_progresso.json e etapa_2B_progresso.json têm
chaves de repo_id duplicadas dentro do objeto "repositories".

Isso podia acontecer por causa de um bug já corrigido em common.py: antes
do fix, repo_id era guardado ora como int, ora como str no dict em memória
(repo_status), e as duas formas contavam como chaves DIFERENTES em Python
(26500787 != "26500787"). Ao salvar em JSON, as duas viravam a mesma
string "26500787" -- resultando num arquivo com essa chave escrita duas
vezes. json.load() comum não detecta isso: ele silenciosamente fica só com
a última ocorrência de cada chave repetida. Por isso este script usa
object_pairs_hook, que recebe os pares crus antes dessa deduplicação
automática do parser, pra conseguir realmente contar as ocorrências.

Uso:
    python verificar_duplicatas_progresso.py <run_dir>

Roda contra reports/etapa_2A_progresso.json e reports/etapa_2B_progresso.json
dentro do run_dir informado. Só leitura -- não altera nenhum arquivo.
"""

import json
import sys
from collections import Counter
from pathlib import Path


def find_duplicate_keys(path: Path):
    """
    Retorna {chave: quantidade de ocorrências} para toda chave que aparece
    mais de uma vez dentro de um objeto que pareça um mapa de repo_id
    (todas as chaves puramente numéricas) -- na prática, o objeto
    "repositories" do arquivo de progresso.
    """
    duplicates = {}

    def hook(pairs):
        keys = [k for k, _ in pairs]
        if keys and all(k.lstrip("-").isdigit() for k in keys):
            counts = Counter(keys)
            for key, count in counts.items():
                if count > 1:
                    duplicates[key] = duplicates.get(key, 0) + count
        return dict(pairs)

    with path.open("r", encoding="utf-8") as f:
        json.load(f, object_pairs_hook=hook)

    return duplicates


def check_file(path: Path):
    print(f"=== {path} ===")
    if not path.exists():
        print("  (arquivo não existe, pulando)")
        return

    try:
        duplicates = find_duplicate_keys(path)
    except json.JSONDecodeError as exc:
        print(f"  ERRO: JSON inválido -- {exc}")
        return

    if not duplicates:
        print("  Nenhuma chave duplicada encontrada.")
        return

    print(f"  {len(duplicates)} repo_id com chave duplicada:")
    for repo_id, count in sorted(duplicates.items(), key=lambda x: -x[1]):
        print(f"    repo_id {repo_id}: aparece {count}x")


def main():
    if len(sys.argv) < 2:
        print("Uso: python verificar_duplicatas_progresso.py <run_dir>")
        sys.exit(1)

    run_dir = Path(sys.argv[1])
    reports_dir = run_dir / "reports"

    check_file(reports_dir / "etapa_2A_progresso.json")
    print()
    check_file(reports_dir / "etapa_2B_progresso.json")


if __name__ == "__main__":
    main()