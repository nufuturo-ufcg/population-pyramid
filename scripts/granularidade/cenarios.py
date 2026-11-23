"""Cenários de pirâmide: S1 (igual ao IEICE16), S2 (igual à pirâmide da rodada oficial) e S3 (IEICE16 com saída em 12 meses). Ver `hipoteses.md` de `projecao-cenarios-ieice/`.

  S1: recortes de 3 meses, ativo = contribuiu nos últimos 3 meses, idade = tempo desde a primeira contribuição em faixas de 3 meses sem desconto, todos os contribuidores, horizonte de 3 meses.
  S2: recorte em 31 de dezembro, faixas de 1 ano, idade descontada, janela de 12 meses, residentes pelo passado (P1), horizonte de 12 meses. Igual à versão A de `projecao-granularidade`.
  S3: como S1, com ativo = contribuiu nos últimos 12 meses.
  S1b e S3h: S1 e S3 com horizonte de 12 meses (4 recortes à frente), para separar o efeito do horizonte (em S3 com horizonte de 3 meses, 9 dos 12 meses da janela do alvo já estão observados na origem).

Roda os 41 métodos (mais a coorte exata do IEICE16 em S1 e S3) e o fatorial R0 a R3 de nascimento e parada de repositórios. Grava por linguagem e cenário, em `<saida>/unidades/`:
`<l>_<cenario>_pares.csv.gz` (41 métodos e R0), `<l>_<cenario>_R1_pares.csv.gz` a `_R3_` (métodos do fatorial), `_marcas.csv` (por último) e, com `--vazamento`, `_vazamento.csv`.
Em S2 confere os 41 métodos contra `<granularidade>/unidades/<l>_P1_12_pares.csv.gz` e para se algum diferir.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/cenarios.py --carga DIR --saida DIR --linguas elixir --cenarios S1 S3 S1b S3h [--vazamento] [--granularidade DIR] [--amostra N] [--refazer]
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vazamento
from estado import FIM, constroi_estado, corta_estado
from previsao import (
    POOL,
    gera_regras,
    metodos_b,
    metodos_intervalo_nova,
    metodos_intervalo_r,
    metodos_r,
    metodos_r_ieice,
    preve_estado,
)
from rodar import abre_ok, le_dados, memoria_maxima_gb, origens_do_teste

CENARIOS = {
    "S1": {"passo": 3, "janela": 1, "idade": "tempo", "pop": "P2", "horizonte": 1, "ieice": True},
    "S2": {
        "passo": 12,
        "janela": None,
        "idade": "descontada",
        "pop": "P1",
        "horizonte": 1,
        "ieice": False,
    },
    "S3": {"passo": 3, "janela": 4, "idade": "tempo", "pop": "P2", "horizonte": 1, "ieice": True},
    # mesmos recortes e regras de S1 e S3, com horizonte de 12 meses (a coorte avança 4 recortes até o alvo)
    "S1b": {"passo": 3, "janela": 1, "idade": "tempo", "pop": "P2", "horizonte": 4, "ieice": True},
    "S3h": {"passo": 3, "janela": 4, "idade": "tempo", "pop": "P2", "horizonte": 4, "ieice": True},
}
BASE = ["ingenua", "deriva", "holt_amortecido"]


def sem_sufixo(nome: str) -> str:
    return nome[:-2] if nome.endswith("_B") else nome


def roda_cenario(
    pessoas: pd.DataFrame,
    eventos: dict,
    lingua: str,
    cenario: str,
    pasta: Path,
    com_vazamento: bool = False,
    amostra: int | None = None,
    granularidade: Path | None = None,
) -> None:
    cfg = CENARIOS[cenario]
    prefixo = f"{lingua}_{cenario}"
    inicio = time.time()
    opcoes_estado = {"janela_blocos": cfg["janela"], "idade": cfg["idade"], "com_parada": True}
    est = constroi_estado(pessoas, eventos, cfg["passo"], cfg["pop"], FIM, **opcoes_estado)
    nb, K1, H = est["nb"], len(est["datas"]), cfg["horizonte"]
    ativas = est["ativas"]
    print(
        f"{prefixo}: estado pronto ({est['n_pessoas']} pessoas, {est['n_repos']} repositórios, {K1} recortes) em {time.time() - inicio:.0f}s, pico de memória {memoria_maxima_gb():.1f} GB",
        flush=True,
    )
    # calibração da parada: fração de pessoas que ficariam sem repositório (prevista na origem) contra a que ficou (observada no recorte seguinte)
    pasta.mkdir(parents=True, exist_ok=True)
    pessoas_na_faixa = est["pop_p_b"].sum(axis=1)
    calibracao = [
        (
            lingua,
            cenario,
            k,
            est["Q_b"][k].sum() / max(pessoas_na_faixa[k], 1),
            est["ORF_b"][k + 1].sum() / max(pessoas_na_faixa[k], 1),
        )
        for k in range(1, K1 - 1)
        if pessoas_na_faixa[k] > 0
    ]
    pd.DataFrame(
        calibracao,
        columns=[
            "linguagem",
            "cenario",
            "k",
            "saida_por_parada_prevista",
            "saida_por_parada_observada",
        ],
    ).to_csv(pasta / f"{prefixo}_calibracao.csv", index=False, float_format="%.6g")
    regras = gera_regras(len(POOL))
    nomes = [
        *BASE,
        *metodos_b(),
        *metodos_r(),
        *metodos_intervalo_r(),
        *metodos_intervalo_nova(),
    ] + (["coorte_IEICE_B", "conservador_IEICE_B", *metodos_r_ieice()] if cfg["ieice"] else [])
    hist = {
        "previsto": {m: np.full(K1, np.nan) for m in nomes},
        "rf": np.full((K1, len(regras)), np.nan),
        "rf_B": np.full((K1, len(regras)), np.nan),
    }
    for r in (1, 2, 3):
        hist[f"rf_R{r}_B"] = np.full((K1, len(regras)), np.nan)
    primeiro_ativo = int(np.argmax(ativas > 0)) if (ativas > 0).any() else K1
    ultima_origem = K1 - 1 - H
    primeira = (
        primeiro_ativo + 1
        if amostra is None
        else max(primeiro_ativo + 1, ultima_origem - amostra + 1)
    )
    pares, marcas = [], []
    t0 = time.time()
    for k in range(primeira, ultima_origem + 1):
        res = preve_estado(corta_estado(est, k), hist, regras, POOL, ("B",), H, cfg["ieice"])
        for m in nomes:
            hist["previsto"][m][k] = res["previsto"][m]
        for chave, matriz in hist.items():
            if chave.startswith("rf"):
                matriz[k] = res[chave]
        real = float(ativas[k + H])  # o alvo é calculado aqui, fora da função de previsão
        origem = str(est["datas"][k])
        for m in nomes:
            p = res["previsto"][m]
            pares.append((lingua, cenario, k, origem, sem_sufixo(m), p, real, abre_ok(real, p)))
        mk, esp = res["marcas"], res["esparsidade"].get("B", {})
        marcas.append(
            (lingua, cenario, k, origem, mk["holt_ingenua"], mk["w_B"], mk["w_sem_origem_anterior_B"], mk["escolha_c6_B"], mk["pesos_c7_B"],
             res["negativas"]["avaliacoes"], res["negativas"]["negativas"], esp.get("faixas_vazias", np.nan), esp.get("razoes_indefinidas", np.nan), esp.get("faixas_bloqueantes", np.nan))
        )  # fmt: skip
    print(
        f"{prefixo}: {(time.time() - t0) / max(len(marcas), 1):.2f}s por origem em {len(marcas)} origens, pico de memória {memoria_maxima_gb():.1f} GB",
        flush=True,
    )
    cabecalho = ["linguagem", "cenario", "k", "origem", "metodo", "previsto", "real", "abre"]
    tabela = pd.DataFrame(pares, columns=cabecalho)
    pasta.mkdir(parents=True, exist_ok=True)
    eh_r = tabela["metodo"].str.contains(r"_R[123]$")
    for r in (1, 2, 3):
        tabela[tabela["metodo"].str.endswith(f"_R{r}")].to_csv(
            pasta / f"{prefixo}_R{r}_pares.csv.gz", index=False, float_format="%.10g"
        )
    tabela[~eh_r].to_csv(pasta / f"{prefixo}_pares.csv.gz", index=False, float_format="%.10g")
    if cenario == "S2" and granularidade is not None and amostra is None:
        confere_com_a_granularidade(
            tabela,
            granularidade / "unidades" / f"{lingua}_P1_12_pares.csv.gz",
            prefixo,
            pasta.parent,
        )
    if com_vazamento:
        escolhidas = origens_do_teste(primeiro_ativo, nb, ultima_origem)
        t1 = time.time()
        linhas = vazamento.testa(
            pessoas,
            eventos,
            cfg["passo"],
            cfg["pop"],
            est,
            hist,
            escolhidas,
            regras,
            POOL,
            ("B",),
            H,
            opcoes_estado,
            {"ieice": cfg["ieice"]},
        )
        linhas.insert(0, "unidade", prefixo)
        linhas.to_csv(pasta / f"{prefixo}_vazamento.csv", index=False)
        print(
            f"{prefixo}: teste de vazamento em {time.time() - t1:.0f}s, estados iguais: {bool(linhas['estados_iguais'].all())}, maior diferença: {linhas['maior_diferenca_relativa'].max():.2e}, controle de eventos futuros difere em {int(linhas['controle_eventos_futuros_difere'].sum())} de {len(linhas)}",
            flush=True,
        )
    cab_marcas = ["linguagem", "cenario", "k", "origem", "holt_ingenua", "w", "w_sem_origem_anterior", "escolha_c6", "pesos_c7", "avaliacoes_negativas", "negativas", "esp_faixas_vazias", "esp_razoes_indefinidas", "esp_faixas_bloqueantes"]  # fmt: skip
    pd.DataFrame(marcas, columns=cab_marcas).to_csv(
        pasta / f"{prefixo}_marcas.csv", index=False
    )  # por último: marca o cenário como pronto
    print(f"{prefixo}: pronto em {time.time() - inicio:.0f}s", flush=True)


def confere_com_a_granularidade(
    tabela: pd.DataFrame, arquivo: Path, prefixo: str, saida: Path
) -> None:
    """S2 precisa reproduzir os 41 métodos da versão A de `projecao-granularidade` (P1, 12 meses). Para a execução se algum diferir."""
    if not arquivo.exists():
        print(
            f"{prefixo}: {arquivo.name} não existe, conferência com a granularidade pulada",
            flush=True,
        )
        return
    antigo = pd.read_csv(arquivo)
    comparados, diferentes = 0, []
    novo = tabela[~tabela["metodo"].str.contains(r"_R[0-3]$|IEICE")].set_index(["k", "metodo"])[
        "previsto"
    ]
    for alias, original in [
        ("coorte_R0", "coorte_V0"),
        ("conservador_R0", "conservador_V0"),
    ]:  # R0 é a V0
        assert np.allclose(
            tabela[tabela["metodo"] == alias]["previsto"].to_numpy(),
            tabela[tabela["metodo"] == original]["previsto"].to_numpy(),
            equal_nan=True,
        )
    for (k, metodo), p_antigo in antigo.set_index(["k", "metodo"])["previsto"].items():
        if (k, metodo) not in novo.index:
            continue
        p_novo = novo.loc[(k, metodo)]
        comparados += 1
        if not (
            (np.isnan(p_novo) and np.isnan(p_antigo))
            or abs(p_novo - p_antigo) <= 1e-9 * max(1.0, abs(p_antigo))
        ):
            diferentes.append((k, metodo, p_novo, p_antigo))
    print(
        f"{prefixo}: {comparados} previsões comparadas com a versão A da granularidade, {len(diferentes)} diferentes",
        flush=True,
    )
    with (saida / "conferencia_s2.txt").open("a", encoding="utf-8") as f:
        f.write(
            f"{prefixo}: {comparados} previsões comparadas com a versão A da granularidade, {len(diferentes)} diferentes\n"
        )
    if diferentes or comparados == 0:
        raise SystemExit(
            f"{prefixo}: S2 não reproduz a versão A da granularidade: {diferentes[:5]}. Parei."
        )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--carga", type=Path, required=True)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--linguas", nargs="+", required=True)
    ap.add_argument("--cenarios", nargs="+", default=["S1", "S3", "S2"], choices=list(CENARIOS))
    ap.add_argument("--vazamento", action="store_true")
    ap.add_argument("--refazer", action="store_true")
    ap.add_argument("--amostra", type=int, default=None)
    ap.add_argument("--granularidade", type=Path, default=None)
    a = ap.parse_args()
    pasta = a.saida / "unidades"
    for lingua in a.linguas:
        pessoas, eventos = le_dados(a.carga, lingua)
        print(
            f"{lingua}: {len(pessoas)} pessoas, {len(eventos['dia'])} pares pessoa-repositório-dia, pico de memória {memoria_maxima_gb():.1f} GB",
            flush=True,
        )
        for cenario in a.cenarios:
            if (pasta / f"{lingua}_{cenario}_marcas.csv").exists() and not a.refazer:
                print(f"{lingua}_{cenario}: já pronto, pulado", flush=True)
                continue
            roda_cenario(
                pessoas, eventos, lingua, cenario, pasta, a.vazamento, a.amostra, a.granularidade
            )
