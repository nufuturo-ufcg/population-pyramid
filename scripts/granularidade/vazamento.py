"""Teste de vazamento: a previsão em t não pode mudar quando entram dados posteriores a t.

Para cada origem escolhida, compara três estados e as previsões que saem deles:
  - produção: o estado construído uma vez com todos os dados, cortado na origem (`corta_estado`);
  - cortado em t: o estado construído só com os eventos até t;
  - cortado em t + 12 meses: o estado construído com os eventos até t + 12 meses, que a função de construção precisa cortar em t sozinha;
  - recebendo tudo: a mesma função recebendo todos os eventos.
As séries inteiras (pirâmides e contagens) precisam ser idênticas e as previsões de todos os métodos iguais (tolerância relativa de 1e-9, só para a ordem das somas).
Controles com vazamento de propósito (a previsão precisa mudar; o teste só vale no passo em que muda):
  - eventos futuros: os eventos de (t, t + 12 meses] entram com a data t. Vale para P1 e P2.
  - promoções: em P1, quem só vira residente até t + 12 meses entra como residente desde o início.
"""

import numpy as np
import pandas as pd
from estado import SERIES_NO_TEMPO, constroi_estado, corta_estado, grade
from previsao import preve_estado


def historico_ate(hist: dict, k: int) -> dict:
    """Cópia do histórico só com as origens antes de k, que é o que existia na origem k."""
    copia = {
        "previsto": {m: v.copy() for m, v in hist["previsto"].items()},
        "rf": hist["rf"].copy(),
        "rf_B": hist["rf_B"].copy(),
    }
    for v in copia["previsto"].values():
        v[k:] = np.nan
    copia["rf"][k:] = np.nan
    copia["rf_B"][k:] = np.nan
    return copia


def maior_diferenca(a: dict, b: dict) -> float:
    """Maior diferença relativa entre as previsões de dois conjuntos (NaN no mesmo lugar conta como igual; NaN de um lado só, infinito)."""
    maior = 0.0
    for nome, x in a.items():
        y = b[nome]
        if np.isnan(x) and np.isnan(y):
            continue
        if np.isnan(x) != np.isnan(y):
            return float("inf")
        maior = max(maior, abs(x - y) / max(1.0, abs(x), abs(y)))
    return maior


def testa(
    pessoas: pd.DataFrame,
    eventos: dict,
    passo: float,
    pop: str,
    est: dict,
    hist: dict,
    origens: list[int],
    regras: list,
    pool: list[str],
    versoes: tuple[str, ...] = ("A",),
) -> pd.DataFrame:
    nb = est["nb"]
    linhas = []
    for k in origens:
        t, t_mais_1 = est["datas"][k], est["datas"][k + nb]
        hist_k = historico_ate(hist, k)
        producao = corta_estado(est, k)
        # a função recebendo todos os eventos, só os até t e só os até t + 12 meses: em todos os casos corta sozinha em t
        recebido_t = {nome: v[eventos["dia"] <= t] for nome, v in eventos.items()}
        recebido_t_mais_1 = {nome: v[eventos["dia"] <= t_mais_1] for nome, v in eventos.items()}
        recebendo_tudo = constroi_estado(pessoas, eventos, passo, pop, t)
        cortado_em_t = constroi_estado(pessoas, recebido_t, passo, pop, t)
        cortado_em_t_mais_1 = constroi_estado(pessoas, recebido_t_mais_1, passo, pop, t)
        estados_iguais = True
        for nome in SERIES_NO_TEMPO:
            for outro in (recebendo_tudo, cortado_em_t, cortado_em_t_mais_1):
                estados_iguais = estados_iguais and np.array_equal(producao[nome], outro[nome])
        prevs = [
            preve_estado(e, hist_k, regras, pool, versoes)["previsto"]
            for e in (producao, cortado_em_t, cortado_em_t_mais_1)
        ]
        diferenca = max(maior_diferenca(prevs[0], prevs[1]), maior_diferenca(prevs[0], prevs[2]))
        linha = {
            "k": k,
            "origem": str(t),
            "alvo": str(t_mais_1),
            "estados_iguais": bool(estados_iguais),
            "maior_diferenca_relativa": diferenca,
            "metodos": len(prevs[0]),
        }
        comprimido = {nome: v.copy() for nome, v in recebido_t_mais_1.items()}
        comprimido["dia"] = np.minimum(comprimido["dia"], t)
        com_eventos_futuros = constroi_estado(pessoas, comprimido, passo, pop, t)
        prev_futura = preve_estado(com_eventos_futuros, hist_k, regras, pool, versoes)["previsto"]
        linha["controle_eventos_futuros_difere"] = bool(
            maior_diferenca(prevs[0], prev_futura) > 1e-9
        )
        if pop == "P1":
            vazado = pessoas.copy()
            segunda = vazado["segunda"].to_numpy().astype("datetime64[D]")
            futura = ~np.isnat(segunda) & (segunda > t) & (segunda <= t_mais_1)
            segunda[futura] = datas_primeira(passo)
            vazado["segunda"] = segunda
            controle = constroi_estado(vazado, recebido_t_mais_1, passo, pop, t)
            prev_vazada = preve_estado(controle, hist_k, regras, pool, versoes)["previsto"]
            linha["controle_promocoes_difere"] = bool(maior_diferenca(prevs[0], prev_vazada) > 1e-9)
            linha["pessoas_promovidas_no_ano_seguinte"] = int(futura.sum())
        linhas.append(linha)
    return pd.DataFrame(linhas)


def datas_primeira(passo: float) -> np.datetime64:
    return grade(passo)[0]
