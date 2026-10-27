"""Roda as métricas de todas as linguagens e populações em paralelo, um processo por tarefa.

    uv run python scripts/vitalidade_grade.py --saida PASTA --populacoes todos,passou_30_dias

Cada tarefa é uma linguagem numa população, ou o comparativo numa população. Processos, e não
threads, para o GIL não serializar o pandas. A ordem respeita uma dependência só: o cache dos
eventos de uma linguagem nasce na primeira tarefa dela (a que lê os GB), e o resto só começa
depois. O comparativo espera o cache de todas as linguagens.

As métricas são as do padrão, sem as que exigem o pipeline do motor (tudo em memória).
`processos` no yaml (ou `--processos`) limita quantas rodam juntas: cada uma cabe na memória do
Python inteiro, uns 8 GB.
"""

import argparse
import sys
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Executor, Future, ProcessPoolExecutor, wait
from multiprocessing import get_context
from pathlib import Path

import carga_fonte
import vitalidade as v


def _prepara(config: dict, populacao: str) -> v.Parametros:
    v.aplica_saida(Path(config["saida"]).expanduser())
    v.carrega_estilo(config["estilo"])
    return v.carrega_parametros([*config["sobrepostos"], f"populacao={populacao}"])


def _nomes(escopo: str) -> list[str]:
    nomes = []
    for nome in v.METRICAS:
        if v.ESCOPO[nome] == escopo and v.PADRAO[nome] and not v.USA_PIPELINE[nome]:
            nomes.append(nome)
    return nomes


def tarefa_linguagem(config: dict, slug: str, populacao: str) -> None:
    p = _prepara(config, populacao)
    v.roda(_nomes("linguagem"), p, slug, config["figuras"], v.Entrada(), False)


def tarefa_comparativo(config: dict, populacao: str) -> None:
    p = _prepara(config, populacao)
    v.roda(_nomes("comparativo"), p, p.linguagens_rq2[0], config["figuras"], v.Entrada(), False)


def executa(
    pool: Executor,
    config: dict,
    linguagens: list[str],
    populacoes: list[str],
    em_linguagem: Callable = tarefa_linguagem,
    em_comparativo: Callable = tarefa_comparativo,
) -> list[str]:
    """Agenda as tarefas no `pool` respeitando as dependências. Devolve as que falharam."""
    pendentes: dict[Future, tuple[str, ...]] = {}
    for slug in linguagens:
        futuro = pool.submit(em_linguagem, config, slug, populacoes[0])
        pendentes[futuro] = ("linguagem", slug, populacoes[0])

    caches_prontos = 0
    falhas: list[str] = []
    while pendentes:
        feitas, _ = wait(pendentes, return_when=FIRST_COMPLETED)
        for futuro in feitas:
            tarefa = pendentes.pop(futuro)
            erro = futuro.exception()
            if erro is not None:
                falhas.append(f"{' '.join(tarefa)}: {erro!r}")
                print(f"FALHOU {' '.join(tarefa)}: {erro!r}", file=sys.stderr, flush=True)
                continue
            print(f"pronto {' '.join(tarefa)}", flush=True)
            if tarefa[0] != "linguagem" or tarefa[2] != populacoes[0]:
                continue
            for populacao in populacoes[1:]:
                novo = pool.submit(em_linguagem, config, tarefa[1], populacao)
                pendentes[novo] = ("linguagem", tarefa[1], populacao)
            caches_prontos += 1
            if caches_prontos == len(linguagens):
                for populacao in populacoes:
                    novo = pool.submit(em_comparativo, config, populacao)
                    pendentes[novo] = ("comparativo", populacao)
    return falhas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", default=str(v.PADRAO_SAIDA))
    parser.add_argument(
        "--populacoes", help="separadas por vírgula. Padrão: a `populacao` do yaml", default=None
    )
    parser.add_argument("--processos", type=int, help="padrão: `processos` do yaml")
    parser.add_argument("--figuras", default="nenhuma", help="como em vitalidade.py")
    parser.add_argument("--set", dest="sobrepostos", action="append", default=[])
    parser.add_argument("--estilo", action="append", default=[])
    args = parser.parse_args()

    p = v.carrega_parametros(args.sobrepostos)
    populacoes = args.populacoes.split(",") if args.populacoes else [p.populacao]
    processos = args.processos or p.processos
    # Os maiores primeiro: a fila é FIFO e a leitura de centenas de GB é o que demora.
    linguagens = sorted(
        p.linguagens_rq2,
        key=lambda s: carga_fonte.resolve_fonte(s, None, None, None).bytes_de_eventos(),
        reverse=True,
    )

    config = {
        "saida": args.saida,
        "sobrepostos": args.sobrepostos,
        "estilo": args.estilo,
        "figuras": args.figuras,
    }
    with ProcessPoolExecutor(processos, mp_context=get_context("spawn")) as pool:
        falhas = executa(pool, config, linguagens, populacoes)
    if falhas:
        raise SystemExit("falharam:\n" + "\n".join(falhas))


if __name__ == "__main__":
    main()
