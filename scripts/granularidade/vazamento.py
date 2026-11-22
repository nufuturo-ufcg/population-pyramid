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
from estado import SERIES_DA_PARADA, SERIES_NO_TEMPO, constroi_estado, corta_estado, grade
from previsao import preve_estado


def historico_ate(hist: dict, k: int) -> dict:
    """Cópia do histórico só com as origens antes de k, que é o que existia na origem k."""
    copia = {"previsto": {m: x.copy() for m, x in hist["previsto"].items()}}
    for x in copia["previsto"].values():
        x[k:] = np.nan
    for chave, matriz in hist.items():
        if chave.startswith("rf"):
            copia[chave] = matriz.copy()
            copia[chave][k:] = np.nan
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
    horizonte: int | None = None,
    opcoes_estado: dict | None = None,
    opcoes_previsao: dict | None = None,
) -> pd.DataFrame:
    """Teste de vazamento. `horizonte` é o número de datas até o alvo (padrão, 12 meses); `opcoes_estado` e `opcoes_previsao` repetem as opções do estado e da previsão da produção."""
    nb = est["nb"]
    h = horizonte if horizonte is not None else nb
    opcoes_estado = opcoes_estado or {}
    kw_prev = {"versoes": versoes, "horizonte": horizonte, **(opcoes_previsao or {})}
    linhas = []
    for k in origens:
        t, t_alvo = est["datas"][k], est["datas"][k + h]
        hist_k = historico_ate(hist, k)
        producao = corta_estado(est, k)
        # a função recebendo todos os eventos, só os até t e só os até o alvo: em todos os casos corta sozinha em t
        recebido_t = {nome: v[eventos["dia"] <= t] for nome, v in eventos.items()}
        recebido_alvo = {nome: v[eventos["dia"] <= t_alvo] for nome, v in eventos.items()}
        recebendo_tudo = constroi_estado(pessoas, eventos, passo, pop, t, **opcoes_estado)
        cortado_em_t = constroi_estado(pessoas, recebido_t, passo, pop, t, **opcoes_estado)
        cortado_no_alvo = constroi_estado(pessoas, recebido_alvo, passo, pop, t, **opcoes_estado)
        estados_iguais = True
        nomes_series = SERIES_NO_TEMPO + [n for n in SERIES_DA_PARADA if n in producao]
        for nome in nomes_series:
            for outro in (recebendo_tudo, cortado_em_t, cortado_no_alvo):
                estados_iguais = estados_iguais and bool(
                    np.allclose(producao[nome], outro[nome], rtol=1e-12, atol=1e-12, equal_nan=True)
                )
        prevs = [
            preve_estado(e, hist_k, regras, pool, **kw_prev)["previsto"]
            for e in (producao, cortado_em_t, cortado_no_alvo)
        ]
        diferenca = max(maior_diferenca(prevs[0], prevs[1]), maior_diferenca(prevs[0], prevs[2]))
        linha = {
            "k": k,
            "origem": str(t),
            "alvo": str(t_alvo),
            "estados_iguais": bool(estados_iguais),
            "maior_diferenca_relativa": diferenca,
            "metodos": len(prevs[0]),
        }
        comprimido = {nome: x.copy() for nome, x in recebido_alvo.items()}
        comprimido["dia"] = np.minimum(comprimido["dia"], t)
        com_eventos_futuros = constroi_estado(pessoas, comprimido, passo, pop, t, **opcoes_estado)
        prev_futura = preve_estado(com_eventos_futuros, hist_k, regras, pool, **kw_prev)["previsto"]
        linha["controle_eventos_futuros_difere"] = bool(
            maior_diferenca(prevs[0], prev_futura) > 1e-9
        )
        if pop == "P1":
            vazado = pessoas.copy()
            segunda = vazado["segunda"].to_numpy().astype("datetime64[D]")
            futura = ~np.isnat(segunda) & (segunda > t) & (segunda <= t_alvo)
            segunda[futura] = datas_primeira(passo)
            vazado["segunda"] = segunda
            controle = constroi_estado(vazado, recebido_alvo, passo, pop, t, **opcoes_estado)
            prev_vazada = preve_estado(controle, hist_k, regras, pool, **kw_prev)["previsto"]
            linha["controle_promocoes_difere"] = bool(maior_diferenca(prevs[0], prev_vazada) > 1e-9)
            linha["pessoas_promovidas_no_ano_seguinte"] = int(futura.sum())
        linhas.append(linha)
    return pd.DataFrame(linhas)


def datas_primeira(passo: float) -> np.datetime64:
    return grade(passo)[0]
