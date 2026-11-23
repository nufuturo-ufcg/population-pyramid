"""`duplicatas_por_repo` ignora `collection_started_at` na chave e conta as linhas extras."""

import csv

from adapters.coleta_csv.contagem_por_repo import duplicatas_por_repo

CABECALHO = ["repo_id", "event_type", "sha", "message", "collection_started_at"]


def test_repetida_so_pela_data_da_coleta(tmp_path):
    arquivo = tmp_path / "eventos.csv"
    with arquivo.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f, delimiter="|")
        escritor.writerow(CABECALHO)
        escritor.writerow(["1", "commit", "a", "msg\ncom quebra", "2026-01-01"])
        escritor.writerow(["1", "commit", "a", "msg\ncom quebra", "2026-02-02"])
        escritor.writerow(["1", "commit", "b", "", "2026-01-01"])
        escritor.writerow(["2", "commit", "a", "msg\ncom quebra", "2026-01-01"])
    saida = tmp_path / "dup.csv"
    duplicatas_por_repo(arquivo, saida, memoria_gb=1, threads=1)
    linhas = {}
    with saida.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            linhas[r["repo_id"]] = (int(r["linhas"]), int(r["repetidas"]))
    assert linhas == {"1": (3, 1), "2": (1, 0)}
