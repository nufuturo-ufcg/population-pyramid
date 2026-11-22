"""Projeção por repositório em S1 (IEICE16): ingênua, coorte e conservador de cada repositório, soma para a linguagem com nascimento e parada (R0 a R3). Ver `hipoteses.md`.

Regras do IEICE16 por repositório: recortes de 3 meses, ativo = evento nos últimos 3 meses, idade do par (pessoa, repositório) = tempo desde a primeira contribuição da pessoa naquele repositório
em faixas de 3 meses sem desconto, todos os contribuidores, horizonte de 3 meses. Taxa de permanência = faixa seguinte agora / faixa antes (um recorte atrás). Faixa 0: média da faixa
no recorte atual e no anterior (coorte) ou nos últimos 8 recortes (conservador, com a média das taxas dos últimos 8 recortes: 2 anos). Faixa com gente e sem taxa deixa o total do repositório
indefinido (fora do erro por repositório); na soma ela recebe a ingênua da faixa.

`constroi_repos(eventos, corte)` descarta o que passa de `corte` (assert). `preve_repos(rep, k)` recebe só o estado até o recorte k. O alvo é calculado fora, em `roda_repos`.
Cortes: todos os repositórios ativos na origem e só os com mais de 100 contribuidores ativos na origem (o corte do IEICE16).

Soma para a linguagem (pares): previsões dos repositórios do corte + repositórios fora do corte pela ingênua (pares da origem) + nascimento (R1: repositórios novos pela média dos últimos 8 recortes
vezes pares por repositório novo, média dos últimos 8 recortes) - parada (R2: soma, por repositório, da probabilidade de parar pela idade do repositório vezes o previsto). Pares viram pessoas
pela razão pessoas / pares da origem. O erro em pessoas separa-se em erro em pares e erro da conversão: (1 + erro em pessoas) = (1 + erro em pares) x (1 + erro da conversão).
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estado import DIAS_BANDA, FIM, TOPO, grade
from previsao import abre_vet
from rodar import le_dados, memoria_maxima_gb

NB_PASSO = 4  # recortes por ano
TOPO_R = TOPO * NB_PASSO  # faixas de 3 meses até 8 anos
COLUNAS = TOPO_R + 2
N2 = 2 * NB_PASSO
CORTES = ["mais_de_100", "todos"]
METODOS_R = ["ingenua", "coorte", "conservador"]


def constroi_repos(eventos: dict, corte: np.datetime64) -> dict:
    """Pirâmide de cada repositório (pares por faixa de idade do par) em cada recorte até `corte`, e as séries de pessoas, pares e nascimentos."""
    datas = grade(3, corte)
    assert datas[-1] == corte, "o corte precisa ser um recorte"
    K1 = len(datas)
    dentro = eventos["dia"] <= corte
    pessoa, codigo, dia = (
        eventos["pessoa"][dentro],
        eventos["codigo"][dentro],
        eventos["dia"][dentro],
    )
    assert len(dia) == 0 or dia.max() <= corte, "evento depois do corte"
    _, p_idx = np.unique(pessoa, return_inverse=True)
    codigos, r_idx = np.unique(codigo, return_inverse=True)
    n_repos = len(codigos)
    bloco = np.searchsorted(datas, dia, side="left").astype(np.int64)
    dia_int = dia.astype("datetime64[D]").astype(np.int64)
    datas_int = datas.astype("datetime64[D]").astype(np.int64)
    par = p_idx.astype(np.int64) * n_repos + r_idx
    pares_unicos, par_idx = np.unique(par, return_inverse=True)
    primeiro_dia_par = np.full(len(pares_unicos), np.iinfo(np.int64).max, dtype=np.int64)
    np.minimum.at(primeiro_dia_par, par_idx, dia_int)
    linhas = np.unique(par_idx.astype(np.int64) * K1 + bloco)  # (par, bloco) distintos
    par_l, bloco_l = linhas // K1, linhas % K1
    repo_l = (pares_unicos[par_l] % n_repos).astype(np.int64)
    pessoa_l = (pares_unicos[par_l] // n_repos).astype(np.int64)
    banda = np.clip(
        np.ceil((datas_int[bloco_l] - primeiro_dia_par[par_l]) / DIAS_BANDA) - 1, 0, COLUNAS - 1
    ).astype(np.int64)
    plano = (repo_l * K1 + bloco_l) * COLUNAS + banda
    unicos, contagens = np.unique(plano, return_counts=True)
    cnt = np.zeros(n_repos * K1 * COLUNAS, dtype=np.int32)
    cnt[unicos] = contagens
    cnt = cnt.reshape(n_repos, K1, COLUNAS)
    primeiro_dia_repo = np.full(n_repos, np.iinfo(np.int64).max, dtype=np.int64)
    np.minimum.at(primeiro_dia_repo, r_idx, dia_int)
    primeiro_bloco_repo = np.searchsorted(
        datas, primeiro_dia_repo.astype("datetime64[D]"), side="left"
    )
    pessoas_por_recorte = np.bincount(np.unique(pessoa_l * K1 + bloco_l) % K1, minlength=K1).astype(
        float
    )
    pares_por_recorte = cnt.sum(axis=(0, 2)).astype(float)
    nascimentos = np.bincount(primeiro_bloco_repo, minlength=K1).astype(float)
    pares_dos_novos = np.zeros(K1)
    for j in range(K1):
        novos = primeiro_bloco_repo == j
        pares_dos_novos[j] = cnt[novos, j].sum()
    idade_repo = np.clip(
        np.ceil((datas_int[None, :] - primeiro_dia_repo[:, None]) / DIAS_BANDA) - 1, 0, COLUNAS - 1
    ).astype(np.int16)
    return {
        "datas": datas, "cnt": cnt, "pessoas": pessoas_por_recorte, "pares": pares_por_recorte, "nascimentos": nascimentos, "pares_dos_novos": pares_dos_novos,
        "idade_repo": idade_repo, "primeiro_bloco_repo": primeiro_bloco_repo, "n_repos": n_repos,
    }  # fmt: skip


def corta_repos(rep: dict, k: int) -> dict:
    """O que se sabe no recorte k: as séries até k. Repositório que nasce depois de k fica de fora (sem pares até k)."""
    saida = dict(rep)
    saida["datas"] = rep["datas"][: k + 1]
    saida["cnt"] = rep["cnt"][:, : k + 1]
    saida["idade_repo"] = rep["idade_repo"][:, : k + 1]
    for nome in ["pessoas", "pares", "nascimentos", "pares_dos_novos"]:
        saida[nome] = rep[nome][: k + 1]
    saida["primeiro_bloco_repo"] = np.where(
        rep["primeiro_bloco_repo"] <= k, rep["primeiro_bloco_repo"], 10**6
    )
    return saida


def junta(v: np.ndarray) -> np.ndarray:
    """Junta as duas últimas faixas (faixa aberta de 8 anos ou mais) ao longo do último eixo."""
    saida = v[..., :-1].copy()
    saida[..., -1] += v[..., -1]
    return saida


def taxas_vet(agora: np.ndarray, antes: np.ndarray) -> np.ndarray:
    """Taxa de permanência por repositório e faixa (linhas = repositórios). NaN onde a faixa estava vazia antes."""
    topo = agora.shape[-1] - 2
    sr = np.full((*agora.shape[:-1], topo + 1), np.nan)
    com_gente = antes[..., :topo] > 0
    sr[..., :topo] = np.where(
        com_gente, agora[..., 1 : topo + 1] / np.where(com_gente, antes[..., :topo], 1), np.nan
    )
    na_aberta = antes[..., topo] + antes[..., topo + 1]
    sr[..., topo] = np.where(
        na_aberta > 0, agora[..., topo + 1] / np.where(na_aberta > 0, na_aberta, 1), np.nan
    )
    return sr


def avanca_vet(atual: np.ndarray, sr: np.ndarray, novatos: np.ndarray) -> np.ndarray:
    contribuicao = np.where(atual == 0, 0.0, atual * sr)
    proximo = np.zeros_like(atual, dtype=float)
    proximo[:, 1:] = contribuicao[:, :-1]
    proximo[:, -1] += contribuicao[:, -1]
    proximo[:, 0] = novatos
    return proximo


def preve_repos(rep: dict, k: int) -> dict:
    """Previsões por repositório um recorte à frente, só com os dados até k. Devolve, para os repositórios ativos em k, as faixas previstas (ingênua, coorte e conservador),
    o total com indefinição (NaN se faixa com gente sem taxa) e o total com a ingênua nas faixas sem taxa (para a soma), mais a probabilidade de parada e o necessário para nascimento."""
    assert len(rep["datas"]) == k + 1 and rep["cnt"].shape[1] == k + 1, "dado depois da origem"
    cnt = rep["cnt"]
    ativos = np.where(cnt[:, k].sum(axis=1) > 0)[0]
    atual = junta(cnt[ativos, k].astype(float))
    antes = cnt[ativos, k - 1].astype(float)
    sr_ultima = taxas_vet(cnt[ativos, k].astype(float), antes)
    historico = []
    for j in range(N2):
        if k - j - 1 < 0:
            break
        historico.append(
            taxas_vet(cnt[ativos, k - j].astype(float), cnt[ativos, k - j - 1].astype(float))
        )
    pilha = np.array(historico)
    quantos = np.maximum((~np.isnan(pilha)).sum(axis=0), 1)
    media = np.where(np.all(np.isnan(pilha), axis=0), np.nan, np.nansum(pilha, axis=0) / quantos)
    media = np.where(np.isnan(media), sr_ultima, media)
    novatos_coorte = (cnt[ativos, k, 0] + cnt[ativos, k - 1, 0]) / 2
    ultimos = cnt[ativos, max(k - N2 + 1, 0) : k + 1, 0].astype(float)
    novatos_conservador = ultimos.mean(axis=1)
    saida = {"ativos": ativos, "atual": atual}
    saida["pb_ingenua"] = atual
    for nome, sr, novatos in [
        ("coorte", sr_ultima, novatos_coorte),
        ("conservador", media, novatos_conservador),
    ]:
        contribuicao = np.where(atual == 0, 0.0, atual * sr)
        sem_taxa = np.isnan(contribuicao)
        saida[f"pb_{nome}"] = avanca_vet(atual, np.where(np.isnan(sr), np.nan, sr), novatos)
        saida[f"indefinido_{nome}"] = sem_taxa.any(axis=1)
        pb_fallback = avanca_vet(
            atual, np.where(np.isnan(sr), 1.0, sr), novatos
        )  # faixa sem taxa mantém a ingênua da faixa
        saida[f"total_{nome}"] = pb_fallback.sum(axis=1)
        saida[f"total_estrito_{nome}"] = np.where(
            saida[f"indefinido_{nome}"], np.nan, saida[f"pb_{nome}"].sum(axis=1)
        )
    saida["total_ingenua"] = atual.sum(axis=1)
    saida["total_estrito_ingenua"] = atual.sum(axis=1)
    saida["indefinido_ingenua"] = np.zeros(len(ativos), dtype=bool)
    # parada: probabilidade de o repositório ativo parar até o recorte seguinte, pela idade do repositório, com a última transição observada
    idade_antes = rep["idade_repo"][:, k - 1]
    ativo_antes = cnt[:, k - 1].sum(axis=1) > 0
    parou = ativo_antes & (cnt[:, k].sum(axis=1) == 0)
    ativos_por_idade = np.bincount(idade_antes[ativo_antes], minlength=COLUNAS).astype(float)
    pararam = np.bincount(idade_antes[parou], minlength=COLUNAS).astype(float)
    geral = pararam.sum() / max(ativos_por_idade.sum(), 1)
    pstop = np.where(ativos_por_idade > 0, pararam / np.maximum(ativos_por_idade, 1), geral)
    saida["p_parada"] = pstop[rep["idade_repo"][ativos, k]]
    nasc = rep["nascimentos"][max(k - N2 + 1, 0) : k + 1].mean()
    pares_novos = rep["pares_dos_novos"][max(k - N2 + 1, 0) : k + 1].sum() / max(
        rep["nascimentos"][max(k - N2 + 1, 0) : k + 1].sum(), 1
    )
    saida["nascimentos_previstos"] = float(nasc)
    saida["pares_por_repo_novo"] = float(pares_novos)
    saida["pares_origem"] = float(rep["pares"][k])
    saida["pessoas_origem"] = float(rep["pessoas"][k])
    return saida


def roda_repos(
    eventos: dict, lingua: str, pasta: Path, com_vazamento: bool = False, amostra: int | None = None
) -> None:
    """Roda todas as origens da projeção por repositório (S1) e grava `<l>_repos_erros.csv` (por origem, corte e método) e `<l>_repos_somas.csv` (soma para a linguagem)."""
    inicio = time.time()
    rep = constroi_repos(eventos, FIM)
    K1 = len(rep["datas"])
    print(
        f"{lingua}_repos: estado pronto ({rep['n_repos']} repositórios, {K1} recortes) em {time.time() - inicio:.0f}s, pico de memória {memoria_maxima_gb():.1f} GB",
        flush=True,
    )
    primeiro_ativo = int(np.argmax(rep["pares"] > 0))
    primeira = max(primeiro_ativo + N2 + 1, 2) if amostra is None else K1 - 1 - amostra
    erros, somas = [], []
    for corte in CORTES:
        for k in range(primeira, K1 - 1):
            prev = preve_repos(corta_repos(rep, k), k)
            ativos = prev["ativos"]
            mascara = (
                np.ones(len(ativos), dtype=bool)
                if corte == "todos"
                else prev["atual"].sum(axis=1) > 100
            )
            real_faixas = rep["cnt"][ativos, k + 1].astype(
                float
            )  # alvo: calculado aqui, fora da função de previsão
            real_total = real_faixas.sum(axis=1)
            vazias = float((prev["atual"][mascara] == 0).mean()) if mascara.any() else np.nan
            for metodo in METODOS_R:
                estrito = prev[f"total_estrito_{metodo}"][mascara]
                abre_total = abre_vet(real_total[mascara], estrito)
                pb = prev[f"pb_{metodo}"][mascara]
                rf = junta(
                    real_faixas[mascara]
                )  # faixas reais na mesma régua das previstas (faixa aberta junta)
                celula = abre_vet(
                    rf[:, 1:].ravel(), pb[:, 1:].ravel()
                )  # célula = (repositório, faixa de idade), a unidade do ABRE do IEICE16
                erros.append(
                    (lingua, corte, k, str(rep["datas"][k]), metodo, int(mascara.sum()), int(np.isfinite(abre_total).sum()), np.nanmean(abre_total) if np.isfinite(abre_total).any() else np.nan,
                     np.nanmedian(abre_total) if np.isfinite(abre_total).any() else np.nan, np.nanmedian(celula) if np.isfinite(celula).any() else np.nan, vazias)
                )  # fmt: skip
            # soma para a linguagem, em pares, e conversão em pessoas pela razão da origem
            razao_origem = prev["pessoas_origem"] / max(prev["pares_origem"], 1)
            pares_real, pessoas_real = rep["pares"][k + 1], rep["pessoas"][k + 1]
            razao_alvo = pessoas_real / max(pares_real, 1)
            fora = ~mascara
            ingenua_fora = float(prev["atual"][fora].sum())
            for metodo in METODOS_R:
                base_corte = float(prev[f"total_{metodo}"][mascara].sum()) + ingenua_fora
                parada = float(
                    (prev["p_parada"][mascara] * prev[f"total_{metodo}"][mascara]).sum()
                ) + float((prev["p_parada"][fora] * prev["atual"][fora].sum(axis=1)).sum())
                nasc = prev["nascimentos_previstos"] * prev["pares_por_repo_novo"]
                for r, (com_nasc, com_parada) in enumerate(
                    [(False, False), (True, False), (False, True), (True, True)]
                ):
                    pares_pred = (
                        base_corte + (nasc if com_nasc else 0.0) - (parada if com_parada else 0.0)
                    )
                    somas.append(
                        (
                            lingua,
                            corte,
                            k,
                            str(rep["datas"][k]),
                            metodo,
                            f"R{r}",
                            pares_pred,
                            pares_real,
                            pares_pred * razao_origem,
                            pessoas_real,
                            razao_origem,
                            razao_alvo,
                        )
                    )
    pasta.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        somas,
        columns=[
            "linguagem",
            "corte",
            "k",
            "origem",
            "metodo",
            "r",
            "pares_previstos",
            "pares_reais",
            "pessoas_previstas",
            "pessoas_reais",
            "razao_origem",
            "razao_alvo",
        ],
    ).to_csv(pasta / f"{lingua}_repos_somas.csv", index=False, float_format="%.10g")
    pd.DataFrame(
        erros,
        columns=[
            "linguagem",
            "corte",
            "k",
            "origem",
            "metodo",
            "repositorios",
            "repositorios_com_abre",
            "abre_medio",
            "abre_mediano",
            "abre_mediano_por_faixa",
            "fracao_faixas_vazias",
        ],
    ).to_csv(pasta / f"{lingua}_repos_erros.csv", index=False, float_format="%.8g")
    if com_vazamento:
        testa_repos(eventos, rep, lingua, pasta, primeiro_ativo)
    print(f"{lingua}_repos: pronto em {time.time() - inicio:.0f}s", flush=True)


def resumo_previsao(prev: dict) -> np.ndarray:
    """Números que não dependem da numeração dos repositórios, para comparar duas construções do mesmo estado."""
    saida = [
        prev["pares_origem"],
        prev["pessoas_origem"],
        prev["nascimentos_previstos"],
        prev["pares_por_repo_novo"],
        len(prev["ativos"]),
    ]
    for metodo in METODOS_R:
        saida += [
            np.nansum(prev[f"total_{metodo}"]),
            np.nansum(prev[f"total_estrito_{metodo}"]),
            float(prev[f"indefinido_{metodo}"].sum()),
        ]
    saida += [float((prev["p_parada"] * prev["total_coorte"]).sum())]
    return np.array(saida)


def testa_repos(eventos: dict, rep: dict, lingua: str, pasta: Path, primeiro_ativo: int) -> None:
    """Teste de vazamento da projeção por repositório, com o controle de eventos futuros: a previsão em t não muda com dados posteriores e muda com o controle."""
    K1 = len(rep["datas"])
    candidatas = np.arange(primeiro_ativo + N2 + 4, K1 - 2)
    if len(candidatas) == 0:
        return
    escolhidas = [
        int(candidatas[p])
        for p in np.unique(np.round(np.linspace(0.1, 0.9, 5) * (len(candidatas) - 1)).astype(int))
    ]
    linhas = []
    for k in escolhidas:
        t, t_alvo = rep["datas"][k], rep["datas"][k + 1]
        producao = resumo_previsao(preve_repos(corta_repos(rep, k), k))
        so_t = {n: v[eventos["dia"] <= t] for n, v in eventos.items()}
        ate_alvo = {n: v[eventos["dia"] <= t_alvo] for n, v in eventos.items()}
        iguais = True
        for dados in (eventos, so_t, ate_alvo):
            outro = constroi_repos(dados, t)
            iguais = iguais and bool(
                np.allclose(
                    producao,
                    resumo_previsao(preve_repos(outro, k)),
                    rtol=1e-9,
                    atol=1e-9,
                    equal_nan=True,
                )
            )
        comprimido = {n: v.copy() for n, v in ate_alvo.items()}
        comprimido["dia"] = np.minimum(comprimido["dia"], t)
        com_futuro = resumo_previsao(preve_repos(constroi_repos(comprimido, t), k))
        difere = not np.allclose(producao, com_futuro, rtol=1e-9, atol=1e-9, equal_nan=True)
        linhas.append((f"{lingua}_repos", k, str(t), iguais, difere))
    tabela = pd.DataFrame(
        linhas,
        columns=["unidade", "k", "origem", "estados_iguais", "controle_eventos_futuros_difere"],
    )
    tabela.to_csv(pasta / f"{lingua}_repos_vazamento.csv", index=False)
    print(
        f"{lingua}_repos: teste de vazamento, previsões iguais: {bool(tabela['estados_iguais'].all())}, controle difere em {int(tabela['controle_eventos_futuros_difere'].sum())} de {len(tabela)}",
        flush=True,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--carga", type=Path, required=True)
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--linguas", nargs="+", required=True)
    ap.add_argument("--vazamento", action="store_true")
    ap.add_argument("--refazer", action="store_true")
    ap.add_argument("--amostra", type=int, default=None)
    a = ap.parse_args()
    for lingua in a.linguas:
        if (a.saida / "unidades" / f"{lingua}_repos_erros.csv").exists() and not a.refazer:
            print(f"{lingua}_repos: já pronto, pulado", flush=True)
            continue
        _, eventos = le_dados(a.carga, lingua)
        roda_repos(eventos, lingua, a.saida / "unidades", a.vazamento, a.amostra)
