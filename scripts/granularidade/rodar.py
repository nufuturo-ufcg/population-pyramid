"""Roda unidades (linguagem, população, passo) do experimento de granularidade. Ver `hipoteses.md`.

Lê `pessoas.parquet` e `pessoas_repos_por_dia.parquet` da carga oficial refeita (`<carga>/<linguagem>/origem/`) e grava, por unidade, em `<saida>/unidades/`:
  `<l>_<pop>_<passo>_pares.csv.gz` (uma linha por método e origem), `_faixas.csv.gz` (6 faixas), `_marcas.csv` (w, marcas de C6 e C7, negativas) e, com `--vazamento`,
  `<l>_<pop>_<passo>_vazamento.csv`. Em P0 com passo de 12 meses grava também `_conferencia.csv` com as combinações do pool de 7 métodos de `projecao-combinacoes/`.
Unidade já gravada é pulada (use `--refazer`). Passo em meses: 12, 6, 3, 2, 1 e 0.5.

Com `--amostra N` roda só as N últimas origens de cada unidade e imprime tempo e memória (medição antes de lançar tudo; use outra `--saida`).

Uso (na raiz do repo, na VM): .venv/bin/python scripts/granularidade/rodar.py --carga DIR --saida DIR --linguas elixir --passos 12 --pops P0 P1 P2 [--vazamento] [--refazer] [--amostra N]
"""

import argparse
import platform
import resource
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "src")
import vazamento
from estado import FIM, constroi_estado, corta_estado, junta_aberta_vet, soma_em_faixas6
from previsao import (
    FAIXAS_COM_DETALHE,
    FAIXAS_COM_DETALHE_B,
    POOL,
    POOL7,
    combinacoes,
    gera_regras,
    metodos_b,
    preve_estado,
    todos_os_metodos,
)

from pyramid.projection import abre

NOME_PASSO = {12: "12", 6: "6", 3: "3", 2: "2", 1: "1", 0.5: "0.5"}


def le_dados(carga: Path, lingua: str) -> tuple[pd.DataFrame, dict]:
    pasta = carga / lingua / "origem"
    pessoas = pd.read_parquet(
        pasta / "pessoas.parquet",
        columns=["pessoa", "ocasioes", "codigo_do_primeiro", "segunda_ocasiao"],
    )
    pessoas["segunda"] = pessoas["segunda_ocasiao"].dt.floor("D").to_numpy().astype("datetime64[D]")
    pessoas = pessoas.drop(columns=["segunda_ocasiao"])
    dias = pd.read_parquet(pasta / "pessoas_repos_por_dia.parquet")
    eventos = {
        "pessoa": dias["pessoa"].to_numpy(),
        "codigo": dias["codigo"].to_numpy(),
        "dia": pd.to_datetime(dias["dia"]).to_numpy().astype("datetime64[D]"),
    }
    return pessoas, eventos


def abre_ok(real: float, previsto: float) -> float:
    if np.isnan(previsto) or real <= 0 or previsto <= 0:
        return np.nan
    return abre(float(real), float(previsto))


def memoria_maxima_gb() -> float:
    """Pico de memória residente do processo, em GB."""
    pico = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return pico / 1e9 if platform.system() == "Darwin" else pico / 1e6


def iguais_com_nan(a: np.ndarray, b: np.ndarray) -> bool:
    return bool(np.allclose(a, b, rtol=1e-9, atol=1e-9, equal_nan=True))


def roda_versao(
    est: dict,
    hist: dict,
    versao: str,
    lingua: str,
    pop: str,
    passo: float,
    prefixo: str,
    pasta: Path,
    amostra: int | None,
) -> None:
    """Roda todas as origens de uma versão (A ou B) e grava `<prefixo>[_B]_pares`, `_faixas` e `_marcas`."""
    nb, K1 = est["nb"], len(est["datas"])
    ativas = est["ativas"]
    sufixo = "" if versao == "A" else "_B"
    regras = gera_regras(len(POOL))
    metodos = (
        todos_os_metodos()
        if versao == "A"
        else ["ingenua", "deriva", "holt_amortecido", *metodos_b()]
    )
    primeiro_ativo = int(np.argmax(ativas > 0)) if (ativas > 0).any() else K1
    ultima_origem = K1 - 1 - nb
    primeira_origem = (
        primeiro_ativo + 1
        if amostra is None
        else max(primeiro_ativo + 1, ultima_origem - amostra + 1)
    )
    regras7 = gera_regras(len(POOL7))
    hist7 = np.full((K1, len(regras7)), np.nan)
    com_conferencia = pop == "P0" and passo == 12 and versao == "A"
    pares, faixas, marcas, conferencia = [], [], [], []
    t_origens = time.time()
    for k in range(primeira_origem, ultima_origem + 1):
        res = preve_estado(corta_estado(est, k), hist, regras, POOL, (versao,))
        for m in metodos:
            hist["previsto"][m][k] = res["previsto"][m]
        hist["rf" + sufixo][k] = res["rf" + sufixo]
        # alvo: calculado aqui, fora da função de previsão; as 6 faixas reais usam a idade em anos da rodada oficial nas duas versões
        real = float(ativas[k + nb])
        real_faixas = soma_em_faixas6(junta_aberta_vet(est["pop_p"][k + nb]))
        origem = str(est["datas"][k])
        for m in metodos:
            if versao == "B" and m in ("ingenua", "deriva", "holt_amortecido"):
                continue  # os métodos sem pirâmide já estão na versão A
            p = res["previsto"][m]
            pares.append((lingua, pop, passo, k, origem, m, p, real, abre_ok(real, p)))
        for m, previsto_faixas in res["faixas"].items():
            if m not in (FAIXAS_COM_DETALHE if versao == "A" else FAIXAS_COM_DETALHE_B):
                continue
            for f in range(6):
                faixas.append(
                    (lingua, pop, passo, k, origem, m, f, previsto_faixas[f], real_faixas[f], abre_ok(real_faixas[f], previsto_faixas[f]))
                )  # fmt: skip
        mk, esp = res["marcas"], res["esparsidade"].get(versao, {})
        marcas.append(
            (
                lingua, pop, passo, k, origem, mk["holt_ingenua"], mk["w" + sufixo], mk["w_sem_origem_anterior" + sufixo],
                mk["escolha_c6" + sufixo], mk["pesos_c7" + sufixo], res["negativas"]["avaliacoes"], res["negativas"]["negativas"],
                esp.get("faixas_vazias", np.nan), esp.get("razoes_indefinidas", np.nan), esp.get("faixas_bloqueantes", np.nan),
            )
        )  # fmt: skip
        if com_conferencia:
            valores7 = np.array([res["previsto"][m] for m in POOL7])
            s_max = k - nb
            rf7 = hist7[: s_max + 1] if s_max >= 0 else np.zeros((0, len(regras7)))
            reais = ativas[nb : k + 1] if s_max >= 0 else np.zeros(0)
            c7 = combinacoes(valores7, rf7, reais, regras7, POOL7)
            hist7[k] = c7["rf"]
            for nome, p in c7["previsto"].items():
                conferencia.append((lingua, k, origem, nome + "_7", p, real))
    por_origem = (time.time() - t_origens) / max(len(marcas), 1)
    print(
        f"{prefixo}{sufixo}: {por_origem:.2f}s por origem em {len(marcas)} origens, pico de memória {memoria_maxima_gb():.1f} GB",
        flush=True,
    )
    cabecalho = [
        "linguagem",
        "populacao",
        "passo_meses",
        "k",
        "origem",
        "metodo",
        "previsto",
        "real",
        "abre",
    ]
    pasta.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(pares, columns=cabecalho).to_csv(
        pasta / f"{prefixo}{sufixo}_pares.csv.gz", index=False, float_format="%.10g"
    )
    pd.DataFrame(faixas, columns=[*cabecalho[:6], "faixa", "previsto", "real", "abre"]).to_csv(
        pasta / f"{prefixo}{sufixo}_faixas.csv.gz", index=False, float_format="%.10g"
    )
    if com_conferencia:
        pd.DataFrame(
            conferencia, columns=["linguagem", "k", "origem", "metodo", "previsto", "real"]
        ).to_csv(pasta / f"{prefixo}_conferencia.csv", index=False, float_format="%.10g")
    cab_marcas = [
        "linguagem", "populacao", "passo_meses", "k", "origem", "holt_ingenua", "w", "w_sem_origem_anterior", "escolha_c6", "pesos_c7",
        "avaliacoes_negativas", "negativas", "esp_faixas_vazias", "esp_razoes_indefinidas", "esp_faixas_bloqueantes",
    ]  # fmt: skip
    pd.DataFrame(marcas, columns=cab_marcas).to_csv(
        pasta / f"{prefixo}{sufixo}_marcas.csv", index=False
    )  # por último: marca a versão como pronta


def roda_unidade(
    pessoas: pd.DataFrame,
    eventos: dict,
    lingua: str,
    pop: str,
    passo: float,
    pasta: Path,
    com_vazamento: bool,
    amostra: int | None = None,
    versoes: tuple[str, ...] = ("A", "B"),
    refazer: bool = False,
) -> None:
    """Uma unidade (linguagem, população, passo): constrói o estado uma vez e roda a versão A e depois a B (P0 só tem a A)."""
    prefixo = f"{lingua}_{pop}_{NOME_PASSO[passo]}"
    versoes = tuple(v for v in versoes if v == "A" or pop != "P0")
    pendentes = tuple(
        v
        for v in versoes
        if refazer or not (pasta / f"{prefixo}{'' if v == 'A' else '_B'}_marcas.csv").exists()
    )
    if not pendentes:
        print(f"{prefixo}: já pronto, pulado", flush=True)
        return
    inicio = time.time()
    est = constroi_estado(pessoas, eventos, passo, pop, FIM)
    nb, K1 = est["nb"], len(est["datas"])
    print(
        f"{prefixo}: estado pronto ({est['n_pessoas']} pessoas, {est['n_repos']} repositórios, {K1} datas) em {time.time() - inicio:.0f}s, pico de memória {memoria_maxima_gb():.1f} GB",
        flush=True,
    )
    regras = gera_regras(len(POOL))
    nomes = [*todos_os_metodos(), *metodos_b()]
    hist = {
        "previsto": {m: np.full(K1, np.nan) for m in nomes},
        "rf": np.full((K1, len(regras)), np.nan),
        "rf_B": np.full((K1, len(regras)), np.nan),
    }
    ativas = est["ativas"]
    primeiro_ativo = int(np.argmax(ativas > 0)) if (ativas > 0).any() else K1
    ultima_origem = K1 - 1 - nb
    for versao in pendentes:  # a B depende só do histórico dela e da ingênua: roda depois da A
        roda_versao(est, hist, versao, lingua, pop, passo, prefixo, pasta, amostra)
    if (
        "A" in pendentes and "B" in pendentes and passo == 12
    ):  # com passo de 12 meses A e B são iguais
        for mb in metodos_b():
            if not iguais_com_nan(hist["previsto"][mb[:-2]], hist["previsto"][mb]):
                raise SystemExit(f"{prefixo}: a versão A e a B diferem em 12 meses em {mb}. Parei.")
        assert iguais_com_nan(hist["rf"], hist["rf_B"]), (
            "as regras de C6 e C7 diferem entre A e B em 12 meses"
        )
        print(f"{prefixo}: A e B iguais em 12 meses ({len(metodos_b())} métodos)", flush=True)
    if com_vazamento and pop != "P0":
        escolhidas = origens_do_teste(primeiro_ativo, nb, ultima_origem)
        t0 = time.time()
        linhas = vazamento.testa(
            pessoas, eventos, passo, pop, est, hist, escolhidas, regras, POOL, pendentes
        )
        linhas.insert(0, "unidade", prefixo)
        linhas.to_csv(pasta / f"{prefixo}_vazamento.csv", index=False)
        print(
            f"{prefixo}: teste de vazamento em {time.time() - t0:.0f}s, estados iguais: {bool(linhas['estados_iguais'].all())}, maior diferença: {linhas['maior_diferenca_relativa'].max():.2e}",
            flush=True,
        )
    print(f"{prefixo}: pronto em {time.time() - inicio:.0f}s", flush=True)


def origens_do_teste(primeiro_ativo: int, nb: int, ultima_origem: int) -> list[int]:
    """5 origens espalhadas entre a primeira com 5 anos de histórico (todos os métodos ativos) e a última."""
    primeira = primeiro_ativo + 5 * nb
    if primeira > ultima_origem:
        return []
    candidatas = np.arange(primeira, ultima_origem + 1)
    posicoes = np.unique(np.round(np.linspace(0.1, 0.9, 5) * (len(candidatas) - 1)).astype(int))
    return [int(candidatas[p]) for p in posicoes]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--carga", type=Path, required=True)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--linguas", nargs="+", required=True)
    ap.add_argument("--passos", nargs="+", type=float, default=[12, 6, 3, 2, 1, 0.5])
    ap.add_argument("--pops", nargs="+", default=["P1", "P2"])
    ap.add_argument("--vazamento", action="store_true")
    ap.add_argument("--refazer", action="store_true")
    ap.add_argument("--amostra", type=int, default=None)
    ap.add_argument("--versoes", nargs="+", default=["A", "B"], choices=["A", "B"])
    a = ap.parse_args()
    pasta = a.saida / "unidades"
    for lingua in a.linguas:
        pessoas, eventos = le_dados(a.carga, lingua)
        print(
            f"{lingua}: {len(pessoas)} pessoas, {len(eventos['dia'])} pares pessoa-repositório-dia, pico de memória {memoria_maxima_gb():.1f} GB",
            flush=True,
        )
        for passo in a.passos:
            for pop in a.pops:
                if pop == "P0" and passo != 12:
                    continue
                roda_unidade(
                    pessoas,
                    eventos,
                    lingua,
                    pop,
                    passo,
                    pasta,
                    a.vazamento,
                    a.amostra,
                    tuple(a.versoes),
                    a.refazer,
                )
