"""Teste sem framework: RowSpool grava exatamente os mesmos bytes que o método antigo.

O método antigo guardava as linhas numa lista e o _process_single_repo as gravava
com csv.DictWriter(delimiter='|'). O spool tem de produzir o mesmo CSV, inclusive
com campos difíceis (quebra de linha, aspas, '|', acentos, campo enorme).

Rodar: cd scripts && ../venv/bin/python test_row_spool.py
"""

import csv
import gc
import io
import os

import common


def linha(tipo: str, **campos: object) -> dict:
    """Linha mínima de saída; os campos que faltam ficam de fora, como nos coletores."""
    base = {"repo_id": 1, "repo_name": "o/r", "event_type": tipo, "collection_status": "complete",
            "collection_started_at": "2026-10-09T00:00:00+00:00"}
    base.update(campos)
    return base


LINHAS = [
    linha("issue", number=1, title="com | pipe e \"aspas\"", labels="a;b", files=""),
    linha("pr", number=2, title="acentuação: ção ã é 日本語", files=";".join(f"d/f{i}.py" for i in range(20000))),
    linha("issue_comment", message="primeira\nsegunda\r\nterceira\rquarta", language="Python"),
    linha("issue_event", number=None, title=None, message="closed", language=None),
    linha("pr_comment", message="x" * 200_000, files="a.py", language="Python"),  # acima do limite de campo do csv
    linha("commit_comment", number="", sha="abc", message="", language="Python"),
]


def formato_antigo(linhas: list) -> str:
    """O que _process_single_repo gravava: DictWriter direto no arquivo de saída."""
    saida = io.StringIO(newline="")
    escritor = csv.DictWriter(saida, fieldnames=common.OUTPUT_FIELDS, delimiter="|")
    for item in linhas:
        escritor.writerow(item)
    return saida.getvalue()


def main() -> None:
    """Spool e método antigo geram o mesmo texto; o arquivo temporário some depois."""
    esperado = formato_antigo(LINHAS)

    spool = common.RowSpool(common.OUTPUT_FIELDS)
    spool.extend(iter(LINHAS))  # aceita gerador, como os coletores
    spool.close()
    saida = io.StringIO(newline="")
    spool.copy_to(saida)
    assert saida.getvalue() == esperado, "o spool gravou algo diferente do método antigo"
    assert spool.counts["issue"] == 1 and spool.counts["pr"] == 1 and spool.counts["issue_event"] == 1
    assert sum(spool.counts.values()) == len(LINHAS)

    # caminho de verdade: _process_single_repo copia o spool para o arquivo de saída
    destino = io.StringIO(newline="")
    spool.copy_to(destino)
    assert destino.getvalue() == esperado

    caminho = spool.path
    assert os.path.exists(caminho)
    del spool
    gc.collect()
    assert not os.path.exists(caminho), "o arquivo temporário devia sumir quando o spool é descartado"

    # falha no meio: discard() apaga o arquivo e nada vai para a saída
    spool = common.RowSpool(common.OUTPUT_FIELDS)
    spool.extend(iter(LINHAS[:2]))
    caminho = spool.path
    spool.discard()
    assert not os.path.exists(caminho)

    # spool de processo que morreu é limpo na partida; o de processo vivo não
    morto = os.path.join(os.path.dirname(caminho), "spool2a_999999999_teste.csv")
    vivo = os.path.join(os.path.dirname(caminho), f"spool2a_{os.getpid()}_teste.csv")
    for p in (morto, vivo):
        open(p, "w").close()
    common.remove_orphan_spools()
    assert not os.path.exists(morto) and os.path.exists(vivo)
    os.remove(vivo)
    print("ok")


if __name__ == "__main__":
    main()
