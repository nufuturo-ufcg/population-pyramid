"""Previsão do total de ativos 12 meses à frente, em qualquer passo e população. Ver `hipoteses.md`.

Idade em anos como na rodada oficial, faixas de 1 ano. As taxas de permanência são de 12 meses (pirâmides de duas datas da grade 12 meses afastadas) e a pirâmide avança
um ano de uma vez. O passo define as datas da grade: de quantas datas saem as médias, as retas, as janelas dos cenários e a série do Holt.

`preve_estado(est, hist, pool)` recebe o estado cortado na origem (`estado.corta_estado`: só séries até a origem) e o histórico das previsões de origens anteriores.
Não abre arquivo e não enxerga o alvo. O valor real do alvo é calculado fora, por quem chama.
Tudo que um método estima com o passado (taxas, médias de novatos, retas, w da coorte amortecida, alfa, beta e phi do Holt, subconjuntos de C6, pesos de C7) é refeito em cada chamada.

Métodos: ingênua; coorte, conservador, pessimista e otimista nas variantes V0 a V4b; deriva; Holt amortecido; Hamilton-Perry de 3 e 5 anos; coorte amortecida; C1 a C7.
"""

import itertools

import numpy as np
from estado import BIG, soma_em_faixas6
from estado import junta_aberta_vet as junta_aberta
from scipy.optimize import minimize

VARIANTES = ["V0", "V1", "V2", "V3a", "V3b", "V4a", "V4b"]
FAMILIAS = ["coorte", "conservador", "pessimista", "otimista"]
POOL = [
    "ingenua",
    "coorte_V0",
    "conservador_V0",
    "deriva",
    "holt_amortecido",
    "hp3",
    "hp5",
    "coorte_amortecida",
]
POOL7 = ["ingenua", "coorte_V0", "deriva", "holt_amortecido", "hp3", "hp5", "coorte_amortecida"]
COMBOS = ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]
MIN_HIST = 3
FAIXAS_COM_DETALHE = ["ingenua", "coorte_V0", "conservador_V0"]


def todos_os_metodos() -> list[str]:
    nomes = ["ingenua"]
    for familia in FAMILIAS:
        for v in VARIANTES:
            nomes.append(f"{familia}_{v}")
    return [*nomes, "deriva", "holt_amortecido", "hp3", "hp5", "coorte_amortecida", *COMBOS]


def gera_regras(n_metodos: int) -> list:
    """Cada subconjunto com a média; com a mediana só a partir de 3 métodos (com 1 ou 2 a mediana é a média). Os `n_metodos` primeiros são os métodos sozinhos."""
    regras = []
    for tamanho in range(1, n_metodos + 1):
        for sub in itertools.combinations(range(n_metodos), tamanho):
            regras.append((sub, "media"))
            if tamanho >= 3:
                regras.append((sub, "mediana"))
    for m in range(n_metodos):
        assert regras[m] == ((m,), "media")
    return regras


def aplica_regra(regra: tuple, v: np.ndarray) -> float:
    sub, agg = regra
    valores = v[list(sub)]
    if np.isnan(valores).any():
        return np.nan
    if agg == "media":
        return float(valores.mean())
    return float(np.median(valores))


def nome_regra(regra: tuple, pool: list[str]) -> str:
    sub, agg = regra
    return agg + "(" + "+".join(pool[i] for i in sub) + ")"


def abre_vet(real: np.ndarray, previsto: np.ndarray) -> np.ndarray:
    """ABRE com NaN onde um lado não é positivo."""
    r = np.where(real > 0, real, np.nan)
    p = np.where(previsto > 0, previsto, np.nan)
    return np.abs(p - r) / np.minimum(p, r)


def taxas(agora: np.ndarray, antes: np.ndarray) -> np.ndarray:
    """Taxa de permanência de cada faixa: quem está na faixa k+1 agora dividido por quem estava na faixa k 12 meses antes. A faixa aberta junta as duas últimas."""
    topo = len(agora) - 2
    sr = np.full(topo + 1, np.nan)
    com_gente = antes[:topo] > 0
    sr[:topo][com_gente] = agora[1 : topo + 1][com_gente] / antes[:topo][com_gente]
    na_aberta = antes[topo] + antes[topo + 1]
    if na_aberta > 0:
        sr[topo] = agora[topo + 1] / na_aberta
    return sr


def taxa_dos_repos_maduros(agora: np.ndarray, antes: np.ndarray) -> float:
    """Taxa média dos repositórios da faixa 1 em diante (a faixa 0 fica de fora): quantos seguem ativos no passo seguinte, como nos experimentos anteriores."""
    topo = len(agora) - 2
    sobem = agora[2 : topo + 1].sum() + agora[topo + 1]
    eram = antes[1:topo].sum() + antes[topo] + antes[topo + 1]
    return float(sobem / eram) if eram > 0 else 1.0


def avanca(atual: np.ndarray, sr: np.ndarray, novatos: float) -> np.ndarray:
    """Um passo da coorte: cada faixa com gente sobe uma faixa com a sua taxa e entram os novatos. Faixa sem gente não leva ninguém."""
    proximo = np.zeros_like(atual)
    contribuicao = np.where(atual == 0, 0.0, atual * sr)
    proximo[1:] = contribuicao[:-1]
    proximo[-1] += contribuicao[-1]
    proximo[0] = novatos
    return proximo


def projeta_repos(atual: np.ndarray, sr: np.ndarray, fallback: float, nascimentos: float) -> float:
    """Repositórios existentes (faixa 1 em diante) daqui a 12 meses. Faixa sem taxa recebe a taxa média dos repositórios com 1 ano ou mais."""
    sr_cheia = np.where(np.isnan(sr), fallback, sr)
    return float(avanca(atual, sr_cheia, nascimentos)[1:].sum())


def serie(v: np.ndarray, k: int, n: int) -> np.ndarray:
    """Os n últimos valores até o bloco k (NaN antes do bloco 0)."""
    p = np.arange(k - n + 1, k + 1)
    saida = np.full(n, np.nan)
    dentro = p >= 0
    saida[dentro] = v[p[dentro]]
    return saida


def media_n(v: np.ndarray, k: int, n: int) -> float:
    x = serie(v, k, n)
    return float(np.nanmean(x)) if not np.all(np.isnan(x)) else 0.0


def minimo(x: np.ndarray) -> float:
    return float(np.nanmin(x)) if not np.all(np.isnan(x)) else 0.0


def maximo(x: np.ndarray) -> float:
    return float(np.nanmax(x)) if not np.all(np.isnan(x)) else 0.0


def reta(v: np.ndarray, k: int, n3: int, h: int, contagem: dict) -> float:
    """Reta dos últimos 3 anos (n3 datas, ignora as sem valor), extrapolada h datas à frente. Negativo vira zero e é contado."""
    y = serie(v, k, n3)
    x = np.arange(n3)
    bom = ~np.isnan(y)
    if bom.sum() >= 2:
        angular, linear = np.polyfit(x[bom], y[bom], 1)
        bruto = angular * (n3 - 1 + h) + linear
    elif bom.sum() == 1:
        bruto = float(y[bom][0])
    else:
        bruto = 0.0
    contagem["avaliacoes"] += 1
    contagem["negativas"] += int(bruto < 0)
    return float(max(bruto, 0.0))


def holt_amortecido(serie_total: np.ndarray, nb: int) -> tuple[float, float, float]:
    """Ajusta (alfa, beta, phi) por mínimos quadrados do erro de um passo e devolve (nível, tendência, phi) no fim da série.

    O phi por passo fica entre 0,80^(1/nb) e 0,98^(1/nb): o amortecimento em 12 meses vai de 0,80 a 0,98, como no passo anual.
    """

    def percorre(par: np.ndarray) -> tuple[float, float, float]:
        alfa, beta, phi = par
        nivel, tendencia = serie_total[0], serie_total[1] - serie_total[0]
        soma = 0.0
        for t in range(1, len(serie_total)):
            previsto = nivel + phi * tendencia
            soma += (serie_total[t] - previsto) ** 2
            novo_nivel = alfa * serie_total[t] + (1 - alfa) * previsto
            tendencia = beta * (novo_nivel - nivel) + (1 - beta) * phi * tendencia
            nivel = novo_nivel
        return soma, nivel, tendencia

    phi_min, phi_max = 0.80 ** (1 / nb), 0.98 ** (1 / nb)
    melhor = None
    for inicio in [(0.5, 0.1, 0.9), (0.8, 0.2, 0.95), (0.3, 0.05, 0.85)]:
        phi0 = min(max(inicio[2] ** (1 / nb), phi_min), phi_max)
        ajuste = minimize(
            lambda p: percorre(p)[0],
            np.array([inicio[0], inicio[1], phi0]),
            method="L-BFGS-B",
            bounds=[(0.01, 0.99), (0.01, 0.99), (phi_min, phi_max)],
        )
        if melhor is None or ajuste.fun < melhor.fun:
            melhor = ajuste
    _, nivel, tendencia = percorre(melhor.x)
    return nivel, tendencia, float(melhor.x[2])


def combinacoes(
    valores: np.ndarray, rf_hist: np.ndarray, reais_hist: np.ndarray, regras: list, pool: list[str]
) -> dict:
    """C1 a C7 a partir dos valores do pool na origem e do histórico de origens com alvo já observado (rf_hist, reais_hist têm uma linha por origem)."""
    n = len(pool)
    i_ing, i_coo, i_holt = (
        pool.index("ingenua"),
        pool.index("coorte_V0"),
        pool.index("holt_amortecido"),
    )
    tudo = tuple(range(n))
    saida = {
        "C1": aplica_regra((tudo, "media"), valores), "C2": aplica_regra((tudo, "mediana"), valores),
        "C3": aplica_regra(((i_ing, i_coo), "media"), valores), "C4": aplica_regra(((i_ing, i_coo, i_holt), "media"), valores),
        "C5": aplica_regra(((i_ing, i_coo, i_holt), "mediana"), valores),
    }  # fmt: skip
    rf_agora = np.array([aplica_regra(r, valores) for r in regras])
    erros = (
        abre_vet(reais_hist[:, None], rf_hist) if len(reais_hist) else np.zeros((0, len(regras)))
    )
    contagem = (~np.isnan(erros)).sum(axis=0)
    soma = np.nansum(erros, axis=0)
    # C6: a regra de menor ABRE médio no histórico, entre as definidas agora
    melhor, melhor_media = -1, np.inf
    for j in range(len(regras)):
        if contagem[j] < MIN_HIST or np.isnan(rf_agora[j]) or rf_agora[j] <= 0:
            continue
        media_hist = soma[j] / contagem[j]
        if media_hist < melhor_media:
            melhor_media, melhor = media_hist, j
    if melhor >= 0:
        saida["C6"] = float(rf_agora[melhor])
        escolha = nome_regra(regras[melhor], pool)
    else:
        saida["C6"] = saida["C3"]
        escolha = "C3 (histórico insuficiente)"
    # C7: pesos proporcionais a 1 / ABRE médio do histórico, só dos métodos com histórico e valor agora
    pesos = np.zeros(n)
    for m in range(n):
        if contagem[m] >= MIN_HIST and not np.isnan(valores[m]):
            pesos[m] = 1.0 / max(soma[m] / contagem[m], 1e-9)
    if (pesos > 0).sum() >= 2:
        pesos = pesos / pesos.sum()
        saida["C7"] = float(np.sum(pesos * np.nan_to_num(valores)))
        texto_pesos = ";".join(f"{pool[m]}={pesos[m]:.3f}" for m in range(n) if pesos[m] > 0)
    else:
        saida["C7"] = saida["C3"]
        texto_pesos = "C3 (histórico insuficiente)"
    return {"previsto": saida, "rf": rf_agora, "escolha_c6": escolha, "pesos_c7": texto_pesos}


def preve_estado(est: dict, hist: dict, regras: list, pool: list[str]) -> dict:
    """Previsões do total daqui a 12 meses na última data de `est`.

    `hist["previsto"][metodo][s]` e `hist["rf"][s]` guardam o que foi previsto nas origens s anteriores (só s <= k - nb têm alvo observado e só essas entram nos erros).
    Devolve `previsto` (total por método), `faixas` (6 faixas, para alguns métodos), `marcas` e a linha de regras `rf` para o histórico.
    """
    k = len(est["datas"]) - 1
    nb = est["nb"]  # datas da grade em 12 meses; o horizonte de 12 meses é nb datas à frente
    n2, n3, n5 = 2 * nb, 3 * nb, 5 * nb
    for nome in ["pop_p", "pop_r", "ativas", "N", "R0", "E", "NN", "NE", "PX", "PN", "pares"]:
        assert len(est[nome]) == k + 1, f"{nome} tem dado depois da origem"
    assert est["par_ativo"].shape[1] == k + 1 and est["idade_r"].shape[1] == k + 1
    pop_p, pop_r, ativas = est["pop_p"], est["pop_r"], est["ativas"]
    N, R0, E, NN, NE, PX = est["N"], est["R0"], est["E"], est["NN"], est["NE"], est["PX"]
    par_ativo, primeiro_r = est["par_ativo"], est["primeiro_r"]
    assert (primeiro_r[primeiro_r < BIG] <= k).all(), "repositório nascido depois da origem"
    previsto = {m: np.nan for m in todos_os_metodos()}
    faixas = {}
    marcas = {
        "holt_ingenua": False,
        "w_sem_origem_anterior": False,
        "w": np.nan,
        "escolha_c6": "",
        "pesos_c7": "",
    }
    contagem_negativas = {"avaliacoes": 0, "negativas": 0}
    previsto["ingenua"] = float(ativas[k])
    primeiro_ativo = int(np.argmax(ativas > 0)) if (ativas > 0).any() else BIG
    if k - nb < primeiro_ativo:  # sem a pirâmide de 12 meses antes não há taxa
        previsto["holt_amortecido"] = previsto["ingenua"]
        marcas["holt_ingenua"] = True
        return {
            "previsto": previsto,
            "faixas": faixas,
            "marcas": marcas,
            "rf": np.full(len(regras), np.nan),
            "negativas": contagem_negativas,
        }

    atual = junta_aberta(pop_p[k])
    faixas["ingenua"] = soma_em_faixas6(atual)

    # cenários: taxas dos últimos 5 anos
    historico_desc = []
    for j in range(n5):
        kk = k - j
        if kk - nb < primeiro_ativo:
            break
        historico_desc.append(taxas(pop_p[kk], pop_p[kk - nb]))
    historico = np.array(historico_desc[::-1])
    sem_nenhuma = np.all(np.isnan(historico), axis=0)
    menor = np.where(
        sem_nenhuma, np.nan, np.nanmin(np.where(np.isnan(historico), np.inf, historico), axis=0)
    )
    maior = np.where(
        sem_nenhuma, np.nan, np.nanmax(np.where(np.isnan(historico), -np.inf, historico), axis=0)
    )
    ultimo = historico[-1]
    menor, maior = (
        np.where(np.isnan(menor), ultimo, menor),
        np.where(np.isnan(maior), ultimo, maior),
    )
    recorte = historico[-n2:]
    quantos = np.maximum((~np.isnan(recorte)).sum(axis=0), 1)
    meio = np.where(np.all(np.isnan(recorte), axis=0), np.nan, np.nansum(recorte, axis=0) / quantos)
    meio = np.where(np.isnan(meio), ultimo, meio)
    sr_ultimo = taxas(pop_p[k], pop_p[k - nb])
    janela = np.arange(k - len(historico) + 1, k + 1)

    # pirâmide dos repositórios
    sr_repos = taxas(pop_r[k], pop_r[k - nb])
    fallback = taxa_dos_repos_maduros(pop_r[k], pop_r[k - nb])
    atual_r = junta_aberta(pop_r[k])
    with np.errstate(divide="ignore", invalid="ignore"):
        M_NOVO = np.where(R0 > 0, NN / np.where(R0 > 0, R0, 1), np.nan)
        M_EX = np.where(E > 0, NE / np.where(E > 0, E, 1), np.nan)
    R0m = media_n(R0, k, n2)
    E_v2 = projeta_repos(atual_r, sr_repos, fallback, R0m)
    E_sem_nasc = projeta_repos(atual_r, sr_repos, fallback, 0.0)

    nov, pess_nov, otim_nov = {}, {}, {}
    n_media = media_n(N, k, n2)
    nov["V0"] = n_media
    pess_v0, otim_v0 = float(N[janela].min()), float(N[janela].max())
    pess_nov["V0"], otim_nov["V0"] = pess_v0, otim_v0
    nov["V1"] = reta(N, k, n3, nb, contagem_negativas)
    pess_nov["V1"], otim_nov["V1"] = pess_v0, otim_v0
    pess_v2 = minimo(R0[janela]) * minimo(M_NOVO[janela]) + minimo(E[janela]) * minimo(M_EX[janela])
    otim_v2 = maximo(R0[janela]) * maximo(M_NOVO[janela]) + maximo(E[janela]) * maximo(M_EX[janela])
    mn_m, me_m = media_n(M_NOVO, k, n2), media_n(M_EX, k, n2)
    nov["V2"] = R0m * mn_m + E_v2 * me_m
    pess_nov["V2"], otim_nov["V2"] = pess_v2, otim_v2
    r0_t = reta(R0, k, n3, nb, contagem_negativas)
    mn_t = reta(M_NOVO, k, n3, nb, contagem_negativas)
    me_t = reta(M_EX, k, n3, nb, contagem_negativas)
    nov["V3a"] = r0_t * mn_t + E_v2 * me_t
    pess_nov["V3a"], otim_nov["V3a"] = pess_v2, otim_v2
    nn_t = reta(NN, k, n3, nb, contagem_negativas)
    ne_t = reta(NE, k, n3, nb, contagem_negativas)
    nov["V3b"] = nn_t + ne_t
    pess_nov["V3b"] = minimo(NN[janela]) + minimo(NE[janela])
    otim_nov["V3b"] = maximo(NN[janela]) + maximo(NE[janela])

    # V4: tendência por repositório
    ativo_k = par_ativo[:, k] > 0
    elegivel = ativo_k & (primeiro_r <= k - (n3 - 1)) & (par_ativo[:, k] >= 5)
    outros = ativo_k & ~elegivel
    idx_el, idx_ou = np.where(elegivel)[0], np.where(outros)[0]
    p3 = np.arange(k - n3 + 1, k + 1)
    p2 = np.arange(k - n2 + 1, k + 1)
    y3 = par_ativo[idx_el][:, np.maximum(p3, 0)].astype(
        float
    )  # sem elegíveis quando p3 tem posição negativa
    y2 = par_ativo[idx_ou][:, np.maximum(p2, 0)].astype(float)
    y2[(p2[None, :] < primeiro_r[idx_ou][:, None]) | (p2[None, :] < 0)] = np.nan
    if len(idx_ou):
        validos = (~np.isnan(y2)).sum(axis=1)
        media_outros = np.where(
            validos > 0, np.nansum(y2, axis=1) / np.maximum(validos, 1), par_ativo[idx_ou, k]
        )
    else:
        media_outros = np.zeros(0)
    x = np.arange(n3, dtype=float)
    xc = x - x.mean()
    angular = (y3 - y3.mean(axis=1, keepdims=True)) @ xc / (xc @ xc) if len(idx_el) else np.zeros(0)
    razoes = (
        np.where(y3[:, :-1] > 0, y3[:, 1:] / np.where(y3[:, :-1] > 0, y3[:, :-1], 1), np.nan)
        if len(idx_el)
        else np.zeros((0, n3 - 1))
    )
    g = np.nanmean(razoes, axis=1) if len(idx_el) else np.zeros(0)
    g = np.where(np.isnan(g), 1.0, g)
    nu_den = float(np.nansum(serie(PX, k, n2)))
    nu = float(np.nansum(serie(NE, k, n2)) / nu_den) if nu_den > 0 else 0.0
    for forma in ["a", "b"]:
        v = f"V4{forma}"
        if forma == "a":
            bruto = (
                y3.mean(axis=1) + angular * (n3 - 1 + nb - x.mean()) if len(idx_el) else np.zeros(0)
            )
            contagem_negativas["avaliacoes"] += len(idx_el)
            contagem_negativas["negativas"] += int((bruto < 0).sum())
            pred_el = np.maximum(bruto, 0.0)
        else:
            pred_el = y3[:, -1] * g**nb if len(idx_el) else np.zeros(0)
        pred = np.zeros(par_ativo.shape[0])
        pred[idx_el] = pred_el
        pred[idx_ou] = media_outros
        vivos = ativo_k & (pred >= 0.5)
        novas = float(pred[vivos].sum()) * nu
        nasceram = E_v2 - E_sem_nasc
        nov[v] = novas + nasceram * me_m + r0_t * mn_t
        pn_den = np.where(PX[janela] > 0, PX[janela], np.nan)
        razao_ne = NE[janela] / pn_den
        pess_nov[v] = minimo(PX[janela]) * minimo(razao_ne) + minimo(R0[janela]) * minimo(
            M_NOVO[janela]
        )
        otim_nov[v] = maximo(PX[janela]) * maximo(razao_ne) + maximo(R0[janela]) * maximo(
            M_NOVO[janela]
        )

    for v in VARIANTES:
        vetores = {
            "coorte": avanca(atual, sr_ultimo, nov[v]),
            "conservador": avanca(atual, meio, nov[v]),
            "pessimista": avanca(atual, menor, pess_nov[v]),
            "otimista": avanca(atual, maior, otim_nov[v]),
        }
        for familia, vetor in vetores.items():
            previsto[f"{familia}_{v}"] = float(vetor.sum())
            if f"{familia}_{v}" in FAIXAS_COM_DETALHE:
                faixas[f"{familia}_{v}"] = soma_em_faixas6(vetor)

    # Hamilton-Perry: a coorte V0 com novatos pela média de 3 e de 5 anos
    if k - n3 + 1 >= primeiro_ativo:
        previsto["hp3"] = float(avanca(atual, sr_ultimo, media_n(N, k, n3)).sum())
    if k - n5 + 1 >= primeiro_ativo:
        previsto["hp5"] = float(avanca(atual, sr_ultimo, media_n(N, k, n5)).sum())
    # deriva: total da origem + variação média anual dos últimos 3 anos
    if k - n3 >= primeiro_ativo:
        bruto = ativas[k] + (ativas[k] - ativas[k - n3]) / 3
        contagem_negativas["avaliacoes"] += 1
        contagem_negativas["negativas"] += int(bruto < 0)
        previsto["deriva"] = float(max(bruto, 0.0))
    # Holt amortecido sobre a série do total desde o primeiro bloco com ativos
    pontos = ativas[primeiro_ativo : k + 1]
    if len(pontos) >= 5 * nb + 1:
        nivel, tendencia, phi = holt_amortecido(pontos, nb)
        bruto = nivel + sum(phi**j for j in range(1, nb + 1)) * tendencia
        contagem_negativas["avaliacoes"] += 1
        contagem_negativas["negativas"] += int(bruto < 0)
        previsto["holt_amortecido"] = float(max(bruto, 0.0))
    else:
        previsto["holt_amortecido"] = previsto["ingenua"]
        marcas["holt_ingenua"] = True
    # coorte amortecida: w pelas origens anteriores já observadas (s + nb <= k)
    coorte_v0 = previsto["coorte_V0"]
    s_max = k - nb
    numerador, denominador = 0.0, 0.0
    for s in range(0, s_max + 1):
        i, c, r = hist["previsto"]["ingenua"][s], hist["previsto"]["coorte_V0"][s], ativas[s + nb]
        if np.isnan(i) or np.isnan(c):
            continue
        numerador += (r - i) * (c - i)
        denominador += (c - i) ** 2
    if denominador == 0:
        w, marcas["w_sem_origem_anterior"] = 0.5, True
    else:
        w = float(np.clip(numerador / denominador, 0.0, 1.0))
    marcas["w"] = w
    if not np.isnan(coorte_v0):
        previsto["coorte_amortecida"] = previsto["ingenua"] + w * (coorte_v0 - previsto["ingenua"])
    # combinações
    valores = np.array([previsto[m] for m in pool])
    rf_hist = hist["rf"][: s_max + 1] if s_max >= 0 else np.zeros((0, len(regras)))
    reais_hist = ativas[nb : k + 1] if s_max >= 0 else np.zeros(0)
    assert len(rf_hist) == len(reais_hist)
    comb = combinacoes(valores, rf_hist, reais_hist, regras, pool)
    previsto.update(comb["previsto"])
    marcas["escolha_c6"], marcas["pesos_c7"] = comb["escolha_c6"], comb["pesos_c7"]
    return {
        "previsto": previsto,
        "faixas": faixas,
        "marcas": marcas,
        "rf": comb["rf"],
        "negativas": contagem_negativas,
    }
