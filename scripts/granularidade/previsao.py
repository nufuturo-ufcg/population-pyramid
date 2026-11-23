"""Previsão do total de ativos 12 meses à frente, em qualquer passo e população. Ver `hipoteses.md`.

Duas versões dos métodos de coorte:
  - A (faixa anual): idade em anos como na rodada oficial, faixas de 1 ano. As taxas de permanência são de 12 meses (pirâmides de duas datas da grade 12 meses afastadas) e a pirâmide
    avança um ano de uma vez.
  - B (faixa do passo, sufixo `_B`): faixas da largura do passo, idade na régua do passo. As taxas são de um passo e a pirâmide avança um passo por vez, `nb` vezes (nb = datas por ano).
O passo define as datas da grade: de quantas datas saem as médias, as retas, as janelas dos cenários e a série do Holt. Com passo de 12 meses A e B são iguais.

`preve_estado(est, hist, pool)` recebe o estado cortado na origem (`estado.corta_estado`: só séries até a origem) e o histórico das previsões de origens anteriores.
Não abre arquivo e não enxerga o alvo. O valor real do alvo é calculado fora, por quem chama.
Tudo que um método estima com o passado (taxas, médias de novatos, retas, w da coorte amortecida, alfa, beta e phi do Holt, subconjuntos de C6, pesos de C7) é refeito em cada chamada.

Métodos: ingênua; coorte, conservador, pessimista e otimista nas variantes V0 a V4b; deriva; Holt amortecido; Hamilton-Perry de 3 e 5 anos; coorte amortecida; C1 a C7.
"""

import itertools

import numpy as np
from estado import BIG, SERIES_NO_TEMPO, soma_em_faixas6
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


POOL_B = [
    "ingenua",
    "coorte_V0_B",
    "conservador_V0_B",
    "deriva",
    "holt_amortecido",
    "hp3_B",
    "hp5_B",
    "coorte_amortecida_B",
]
FAIXAS_COM_DETALHE_B = ["coorte_V0_B", "conservador_V0_B"]


def metodos_b() -> list[str]:
    """Métodos que existem na versão B (ingênua, deriva e Holt não têm pirâmide e ficam só na A)."""
    nomes = [f"{familia}_{v}_B" for familia in FAMILIAS for v in VARIANTES]
    return [*nomes, "hp3_B", "hp5_B", "coorte_amortecida_B", *[f"{c}_B" for c in COMBOS]]


BASES_R = ["coorte", "conservador", "coorte_amortecida", *COMBOS]


def metodos_r() -> list[str]:
    """Fatorial de nascimento e parada de repositórios (R0 nenhum, R1 só nascimento, R2 só parada, R3 os dois), na versão B. R0 repete o método sem R."""
    return [f"{base}_R{r}_B" for base in BASES_R for r in range(4)]


def metodos_intervalo_r() -> list[str]:
    """Pessimista e otimista em R0 a R3 (R0 é a V0 e R1 é a V2; R2 e R3 trazem a parada de repositórios), na versão B."""
    return [f"{familia}_R{r}_B" for familia in ["pessimista", "otimista"] for r in range(4)]


def metodos_r_ieice() -> list[str]:
    """Fatorial R0 a R3 da coorte exata do IEICE16, do conservador com os novatos dela e da C3 com ela (só em S1, S3 e nos cenários com horizonte de 12 meses)."""
    nomes = []
    for base in ["coorte_IEICE", "conservador_IEICE", "C3_IEICE"]:
        nomes.extend(f"{base}_R{r}_B" for r in range(4))
    return nomes


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


def taxas_sem_parada(
    agora: np.ndarray, antes: np.ndarray, sem_repositorio_antes: np.ndarray
) -> np.ndarray:
    """Taxa de permanência sem a saída por parada de repositório: a base de cada faixa tira quem ficou sem repositório ativo."""
    return taxas(agora, np.maximum(antes - sem_repositorio_antes, 0.0))


def historico_sem_parada(est: dict, k: int, primeiro_ativo: int, n: int) -> np.ndarray:
    """Taxas sem parada das `n` últimas origens até k (a de k primeiro), parando antes de faltar a pirâmide do passo anterior."""
    pop_p, orf = est["pop_p_b"], est["ORF_b"]
    historico = []
    for j in range(n):
        kk = k - j
        if kk - 1 < primeiro_ativo:
            break
        historico.append(taxas_sem_parada(pop_p[kk], pop_p[kk - 1], orf[kk]))
    return np.array(historico)


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


def projeta(atual: np.ndarray, sr: np.ndarray, novatos_por_passo: list[float]) -> np.ndarray:
    for novatos in novatos_por_passo:
        atual = avanca(atual, sr, novatos)
    return atual


def projeta_repos(
    atual: np.ndarray, sr: np.ndarray, fallback: float, nascimentos: float, passos: int
) -> list[float]:
    """Repositórios existentes (faixa 1 em diante) depois de cada passo. Faixa sem taxa recebe a taxa média dos repositórios com 1 ano ou mais."""
    existentes = []
    sr_cheia = np.where(np.isnan(sr), fallback, sr)
    for _ in range(passos):
        atual = avanca(atual, sr_cheia, nascimentos)
        existentes.append(float(atual[1:].sum()))
    return existentes


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


def reta(v: np.ndarray, k: int, n3: int, hs: list[int], contagem: dict) -> list[float]:
    """Reta dos últimos 3 anos (n3 datas, ignora as sem valor), extrapolada h datas à frente para cada h. Negativo vira zero e é contado."""
    y = serie(v, k, n3)
    x = np.arange(n3)
    bom = ~np.isnan(y)
    if bom.sum() >= 2:
        angular, linear = np.polyfit(x[bom], y[bom], 1)
        brutos = [angular * (n3 - 1 + h) + linear for h in hs]
    elif bom.sum() == 1:
        brutos = [float(y[bom][0])] * len(hs)
    else:
        brutos = [0.0] * len(hs)
    for bruto in brutos:
        contagem["avaliacoes"] += 1
        contagem["negativas"] += int(bruto < 0)
    return [float(max(bruto, 0.0)) for bruto in brutos]


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
    i_ing, i_holt = pool.index("ingenua"), pool.index("holt_amortecido")
    i_coo = next(  # a coorte do pool: coorte_V0, coorte_V0_B ou coorte_R1_B a coorte_R3_B
        i
        for i, nome in enumerate(pool)
        if nome.startswith("coorte_") and not nome.startswith("coorte_amortecida")
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


def familia_coorte(
    est: dict,
    k: int,
    versao: str,
    primeiro_ativo: int,
    contagem: dict,
    horizonte: int | None = None,
    ieice: bool = False,
) -> dict:
    """Coorte, conservador, pessimista e otimista nas variantes V0 a V4b e Hamilton-Perry de 3 e 5 anos, na versão A (faixa anual) ou B (faixa do passo).

    Devolve `previsto` e `faixas` (nomes com sufixo `_B` na versão B) e a esparsidade da pirâmide na origem.
    """
    nb = est["nb"]
    n2, n3, n5 = 2 * nb, 3 * nb, 5 * nb
    if versao == "A":
        sufixo, lag, passos, hs, por_ano = "", nb, 1, [nb], 1
        pop_p, pop_r = est["pop_p"], est["pop_r"]
        N, R0, E, NN, NE, PX = est["N"], est["R0"], est["E"], est["NN"], est["NE"], est["PX"]
    else:
        passos = horizonte if horizonte is not None else nb  # passos à frente até o alvo
        sufixo, lag, hs, por_ano = "_B", 1, list(range(1, passos + 1)), nb
        pop_p, pop_r = est["pop_p_b"], est["pop_r_b"]
        N, R0, E, NN, NE, PX = (est[n] for n in ["N_b", "R0_b", "E_b", "NN_b", "NE_b", "PX_b"])
    par_ativo, primeiro_r = est["par_ativo"], est["primeiro_r"]
    previsto, faixas = {}, {}
    atual = junta_aberta(pop_p[k])
    sr_ultimo = taxas(pop_p[k], pop_p[k - lag])
    com_gente = atual > 0
    esparsidade = {
        "faixas_vazias": float((~com_gente).mean()),
        "razoes_indefinidas": float(np.isnan(sr_ultimo).mean()),
        "faixas_bloqueantes": float(
            (com_gente & np.isnan(sr_ultimo)).sum() / max(com_gente.sum(), 1)
        ),
    }

    # cenários: taxas dos últimos 5 anos
    historico_desc = []
    for j in range(n5):
        kk = k - j
        if kk - lag < primeiro_ativo:
            break
        historico_desc.append(taxas(pop_p[kk], pop_p[kk - lag]))
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
    janela = np.arange(k - len(historico) + 1, k + 1)

    # pirâmide dos repositórios
    sr_repos = taxas(pop_r[k], pop_r[k - lag])
    fallback = taxa_dos_repos_maduros(pop_r[k], pop_r[k - lag])
    atual_r = junta_aberta(pop_r[k])
    with np.errstate(divide="ignore", invalid="ignore"):
        M_NOVO = np.where(R0 > 0, NN / np.where(R0 > 0, R0, 1), np.nan)
        M_EX = np.where(E > 0, NE / np.where(E > 0, E, 1), np.nan)
    R0m = media_n(R0, k, n2)
    E_v2 = projeta_repos(atual_r, sr_repos, fallback, R0m, passos)
    E_sem_nasc = projeta_repos(atual_r, sr_repos, fallback, 0.0, passos)

    nov, pess_nov, otim_nov = {}, {}, {}
    n_media = media_n(N, k, n2)
    nov["V0"] = [n_media] * passos
    pess_v0, otim_v0 = float(N[janela].min()), float(N[janela].max())
    pess_nov["V0"], otim_nov["V0"] = pess_v0, otim_v0
    nov["V1"] = reta(N, k, n3, hs, contagem)
    pess_nov["V1"], otim_nov["V1"] = pess_v0, otim_v0
    pess_v2 = minimo(R0[janela]) * minimo(M_NOVO[janela]) + minimo(E[janela]) * minimo(M_EX[janela])
    otim_v2 = maximo(R0[janela]) * maximo(M_NOVO[janela]) + maximo(E[janela]) * maximo(M_EX[janela])
    mn_m, me_m = media_n(M_NOVO, k, n2), media_n(M_EX, k, n2)
    nov["V2"] = [R0m * mn_m + E_v2[i] * me_m for i in range(passos)]
    pess_nov["V2"], otim_nov["V2"] = pess_v2, otim_v2
    r0_t = reta(R0, k, n3, hs, contagem)
    mn_t = reta(M_NOVO, k, n3, hs, contagem)
    me_t = reta(M_EX, k, n3, hs, contagem)
    nov["V3a"] = [r0_t[i] * mn_t[i] + E_v2[i] * me_t[i] for i in range(passos)]
    pess_nov["V3a"], otim_nov["V3a"] = pess_v2, otim_v2
    nn_t = reta(NN, k, n3, hs, contagem)
    ne_t = reta(NE, k, n3, hs, contagem)
    nov["V3b"] = [nn_t[i] + ne_t[i] for i in range(passos)]
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
    nasceram = [E_v2[i] - E_sem_nasc[i] for i in range(passos)]
    for forma in ["a", "b"]:
        v = f"V4{forma}"
        novas = []
        for h in hs:
            if forma == "a":
                bruto = (
                    y3.mean(axis=1) + angular * (n3 - 1 + h - x.mean())
                    if len(idx_el)
                    else np.zeros(0)
                )
                contagem["avaliacoes"] += len(idx_el)
                contagem["negativas"] += int((bruto < 0).sum())
                pred_el = np.maximum(bruto, 0.0)
            else:
                pred_el = y3[:, -1] * g**h if len(idx_el) else np.zeros(0)
            pred = np.zeros(par_ativo.shape[0])
            pred[idx_el] = pred_el
            pred[idx_ou] = media_outros
            vivos = ativo_k & (pred >= 0.5)
            novas.append(float(pred[vivos].sum()) * nu)
        nov[v] = [novas[i] + nasceram[i] * me_m + r0_t[i] * mn_t[i] for i in range(passos)]
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
            "coorte": projeta(atual, sr_ultimo, nov[v]),
            "conservador": projeta(atual, meio, nov[v]),
            "pessimista": projeta(atual, menor, [pess_nov[v]] * passos),
            "otimista": projeta(atual, maior, [otim_nov[v]] * passos),
        }
        for familia, vetor in vetores.items():
            nome = f"{familia}_{v}{sufixo}"
            previsto[nome] = float(vetor.sum())
            if nome in FAIXAS_COM_DETALHE + FAIXAS_COM_DETALHE_B:
                faixas[nome] = soma_em_faixas6(vetor, por_ano)

    # Hamilton-Perry: a coorte V0 com novatos pela média de 3 e de 5 anos (última razão de permanência da versão)
    if k - n3 + 1 >= primeiro_ativo:
        previsto[f"hp3{sufixo}"] = float(
            projeta(atual, sr_ultimo, [media_n(N, k, n3)] * passos).sum()
        )
    if k - n5 + 1 >= primeiro_ativo:
        previsto[f"hp5{sufixo}"] = float(
            projeta(atual, sr_ultimo, [media_n(N, k, n5)] * passos).sum()
        )
    if (
        ieice
    ):  # coorte exatamente como no IEICE16: faixa 0 pela média do recorte atual e do anterior
        previsto[f"coorte_IEICE{sufixo}"] = float(
            projeta(atual, sr_ultimo, [media_n(N, k, 2)] * passos).sum()
        )
        # conservador com a mesma regra de novatos: taxa média dos últimos 2 anos e faixa 0 pela média de 2 recortes
        previsto[f"conservador_IEICE{sufixo}"] = float(
            projeta(atual, meio, [media_n(N, k, 2)] * passos).sum()
        )
    if "Q_b" in est and versao == "B":
        novatos_ieice = [media_n(N, k, 2)] * passos if ieice else None
        previsto.update(
            fatorial_r(est, k, atual, nov, primeiro_ativo, n2, novatos_ieice, sr_ultimo)
        )
        previsto.update(intervalos_r(est, k, atual, primeiro_ativo, n5, pess_nov, otim_nov, passos))
    return {"previsto": previsto, "faixas": faixas, "esparsidade": esparsidade}


def fatorial_r(
    est: dict,
    k: int,
    atual: np.ndarray,
    nov: dict,
    primeiro_ativo: int,
    n2: int,
    novatos_ieice: list | None = None,
    sr_ultimo: np.ndarray | None = None,
) -> dict:
    """Coorte e conservador com nascimento (R1, novatos da V2), parada (R2) ou os dois (R3).

    A parada tira da taxa de permanência a saída por repositório parado, para não contar a mesma saída duas vezes:
      - taxa sem parada de uma faixa: quem está na faixa seguinte agora dividido por quem estava na faixa antes menos quem ficou sem repositório ativo (todos os repositórios dele inativos no recorte seguinte);
      - saída por parada na origem: a probabilidade de a pessoa ficar sem repositório (produto das probabilidades de parada dos seus repositórios ativos, pela idade do repositório) somada na faixa e dividida por quem está nela;
      - taxa de projeção = (1 - saída por parada) x taxa sem parada.
    """
    pop_p, orf, q = est["pop_p_b"], est["ORF_b"], est["Q_b"]
    na_faixa = np.where(atual > 0, atual, 1.0)
    saida_parada = np.clip(junta_aberta(q[k]) / na_faixa, 0.0, 1.0)
    ultima = taxas_sem_parada(pop_p[k], pop_p[k - 1], orf[k])
    historico = historico_sem_parada(est, k, primeiro_ativo, n2)
    quantos = np.maximum((~np.isnan(historico)).sum(axis=0), 1)
    media = np.where(
        np.all(np.isnan(historico), axis=0), np.nan, np.nansum(historico, axis=0) / quantos
    )
    media = np.where(np.isnan(media), ultima, media)
    sr_coorte, sr_conservador = (1 - saida_parada) * ultima, (1 - saida_parada) * media
    novatos_r0, novatos_r1 = nov["V0"], nov["V2"]
    saida = {}
    for r, novatos in [(2, novatos_r0), (3, novatos_r1)]:
        saida[f"coorte_R{r}_B"] = float(projeta(atual, sr_coorte, novatos).sum())
        saida[f"conservador_R{r}_B"] = float(projeta(atual, sr_conservador, novatos).sum())
    if (
        novatos_ieice is not None
    ):  # coorte do IEICE16: taxa do último recorte e faixa 0 pela média de 2 recortes (R0, em preve_estado)
        saida["coorte_IEICE_R1_B"] = float(projeta(atual, sr_ultimo, novatos_r1).sum())
        saida["coorte_IEICE_R2_B"] = float(projeta(atual, sr_coorte, novatos_ieice).sum())
        saida["coorte_IEICE_R3_B"] = float(projeta(atual, sr_coorte, novatos_r1).sum())
        saida["conservador_IEICE_R2_B"] = float(projeta(atual, sr_conservador, novatos_ieice).sum())
    return saida


def intervalos_r(
    est: dict,
    k: int,
    atual: np.ndarray,
    primeiro_ativo: int,
    n5: int,
    pess_nov: dict,
    otim_nov: dict,
    passos: int,
) -> dict:
    """Pessimista e otimista com a parada de repositórios, como no `fatorial_r`.

    A taxa sem parada de cada faixa é a menor (pessimista) ou a maior (otimista) das últimas `n5` origens, com a regra da V0: faixa sem taxa em nenhuma das origens usa a da última.
    A taxa de projeção é (1 - saída por parada na origem) x essa taxa, a mesma saída nos dois limites.
    R2 usa os novatos da V0 (menor e maior valor da janela) e R3 os da V2.
    """
    q = est["Q_b"]
    na_faixa = np.where(atual > 0, atual, 1.0)
    saida_parada = np.clip(junta_aberta(q[k]) / na_faixa, 0.0, 1.0)
    historico = historico_sem_parada(est, k, primeiro_ativo, n5)
    ultima = historico[0]
    sem_nenhuma = np.all(np.isnan(historico), axis=0)
    menor = np.where(
        sem_nenhuma, np.nan, np.nanmin(np.where(np.isnan(historico), np.inf, historico), axis=0)
    )
    maior = np.where(
        sem_nenhuma, np.nan, np.nanmax(np.where(np.isnan(historico), -np.inf, historico), axis=0)
    )
    menor = np.where(np.isnan(menor), ultima, menor)
    maior = np.where(np.isnan(maior), ultima, maior)
    saida = {}
    for r, versao in [(2, "V0"), (3, "V2")]:
        saida[f"pessimista_R{r}_B"] = float(
            projeta(atual, (1 - saida_parada) * menor, [pess_nov[versao]] * passos).sum()
        )
        saida[f"otimista_R{r}_B"] = float(
            projeta(atual, (1 - saida_parada) * maior, [otim_nov[versao]] * passos).sum()
        )
    return saida


def peso_da_coorte_amortecida(
    hist: dict, ativas: np.ndarray, k: int, nb: int, nome_coorte: str
) -> tuple[float, bool]:
    """w de `ingenua + w x (coorte - ingenua)` por mínimos quadrados nas origens anteriores com alvo já observado (s + nb <= k). Sem origem anterior, 0,5 e marca."""
    numerador, denominador = 0.0, 0.0
    for s in range(0, k - nb + 1):
        i, c, r = hist["previsto"]["ingenua"][s], hist["previsto"][nome_coorte][s], ativas[s + nb]
        if np.isnan(i) or np.isnan(c):
            continue
        numerador += (r - i) * (c - i)
        denominador += (c - i) ** 2
    if denominador == 0:
        return 0.5, True
    return float(np.clip(numerador / denominador, 0.0, 1.0)), False


def preve_estado(
    est: dict,
    hist: dict,
    regras: list,
    pool: list[str],
    versoes: tuple[str, ...] = ("A",),
    horizonte: int | None = None,
    ieice: bool = False,
) -> dict:
    """Previsões do total daqui a 12 meses na última data de `est`, nas versões pedidas (`("A",)`, `("B",)` ou as duas).

    `hist["previsto"][metodo][s]`, `hist["rf"][s]` e `hist["rf_B"][s]` guardam o que foi previsto nas origens s anteriores (só s <= k - nb têm alvo observado e só essas entram nos erros).
    Devolve `previsto` (total por método), `faixas` (6 faixas, para alguns métodos), `marcas` e as linhas de regras `rf` e `rf_B` para o histórico.
    """
    k = len(est["datas"]) - 1
    nb = est[
        "nb"
    ]  # datas da grade em 12 meses; por padrão o horizonte de 12 meses é nb datas à frente
    H = (
        horizonte if horizonte is not None else nb
    )  # passos até o alvo (versão B e métodos de série)
    for nome in SERIES_NO_TEMPO:
        assert len(est[nome]) == k + 1, f"{nome} tem dado depois da origem"
    assert est["par_ativo"].shape[1] == k + 1
    ativas, primeiro_r = est["ativas"], est["primeiro_r"]
    assert (primeiro_r[primeiro_r < BIG] <= k).all(), "repositório nascido depois da origem"
    nomes = todos_os_metodos() if "A" in versoes else ["ingenua", "deriva", "holt_amortecido"]
    nomes = nomes + (metodos_b() if "B" in versoes else [])
    if "B" in versoes and "Q_b" in est:
        nomes = nomes + metodos_r() + metodos_intervalo_r()
    if ieice:
        nomes = [*nomes, "coorte_IEICE_B", "conservador_IEICE_B"]
        if "B" in versoes and "Q_b" in est:
            nomes = nomes + metodos_r_ieice()
    previsto = {m: np.nan for m in nomes}
    faixas = {}
    marcas = {
        "holt_ingenua": False, "w_sem_origem_anterior": False, "w": np.nan, "escolha_c6": "", "pesos_c7": "",
        "w_sem_origem_anterior_B": False, "w_B": np.nan, "escolha_c6_B": "", "pesos_c7_B": "",
    }  # fmt: skip
    esparsidade = {}
    contagem_negativas = {"avaliacoes": 0, "negativas": 0}
    previsto["ingenua"] = float(ativas[k])
    n3 = 3 * nb
    primeiro_ativo = int(np.argmax(ativas > 0)) if (ativas > 0).any() else BIG
    linhas_rf = {"rf": np.full(len(regras), np.nan), "rf_B": np.full(len(regras), np.nan)}
    for r in (1, 2, 3):
        linhas_rf[f"rf_R{r}_B"] = np.full(len(regras), np.nan)
    if k - 1 < primeiro_ativo:  # sem a pirâmide do passo anterior não há taxa em nenhuma versão
        previsto["holt_amortecido"] = previsto["ingenua"]
        marcas["holt_ingenua"] = True
        return {"previsto": previsto, "faixas": faixas, "marcas": marcas, "esparsidade": esparsidade, **linhas_rf, "negativas": contagem_negativas}  # fmt: skip

    possiveis = [
        v for v in versoes if v == "B" or k - nb >= primeiro_ativo
    ]  # a versão A precisa da pirâmide de 12 meses antes
    for versao in possiveis:
        res = familia_coorte(est, k, versao, primeiro_ativo, contagem_negativas, H, ieice)
        previsto.update(res["previsto"])
        faixas.update(res["faixas"])
        esparsidade[versao] = res["esparsidade"]
    faixas["ingenua"] = soma_em_faixas6(junta_aberta(est["pop_p"][k]))
    # deriva: total da origem + variação média anual dos últimos 3 anos
    if k - n3 >= primeiro_ativo:
        bruto = ativas[k] + H * (ativas[k] - ativas[k - n3]) / n3
        contagem_negativas["avaliacoes"] += 1
        contagem_negativas["negativas"] += int(bruto < 0)
        previsto["deriva"] = float(max(bruto, 0.0))
    # Holt amortecido sobre a série do total desde o primeiro bloco com ativos
    pontos = ativas[primeiro_ativo : k + 1]
    if len(pontos) >= 5 * nb + 1:
        nivel, tendencia, phi = holt_amortecido(pontos, nb)
        bruto = nivel + sum(phi**j for j in range(1, H + 1)) * tendencia
        contagem_negativas["avaliacoes"] += 1
        contagem_negativas["negativas"] += int(bruto < 0)
        previsto["holt_amortecido"] = float(max(bruto, 0.0))
    else:
        previsto["holt_amortecido"] = previsto["ingenua"]
        marcas["holt_ingenua"] = True
    # coorte amortecida e combinações, em cada versão
    for versao in possiveis:
        sufixo = "" if versao == "A" else "_B"
        h_v = nb if versao == "A" else H  # passos até o alvo nessa versão
        s_max = k - h_v
        reais_hist = ativas[h_v : k + 1] if s_max >= 0 else np.zeros(0)
        nome_coorte = f"coorte_V0{sufixo}"
        w, sem_anterior = peso_da_coorte_amortecida(hist, ativas, k, h_v, nome_coorte)
        marcas[f"w{sufixo}"], marcas[f"w_sem_origem_anterior{sufixo}"] = w, sem_anterior
        if not np.isnan(previsto[nome_coorte]):
            previsto[f"coorte_amortecida{sufixo}"] = previsto["ingenua"] + w * (
                previsto[nome_coorte] - previsto["ingenua"]
            )
        pool_da_versao = pool if versao == "A" else POOL_B
        valores = np.array([previsto[m] for m in pool_da_versao])
        rf_hist = hist["rf" + sufixo][: s_max + 1] if s_max >= 0 else np.zeros((0, len(regras)))
        assert len(rf_hist) == len(reais_hist)
        comb = combinacoes(valores, rf_hist, reais_hist, regras, pool_da_versao)
        for c, valor in comb["previsto"].items():
            previsto[c + sufixo] = valor
        marcas[f"escolha_c6{sufixo}"], marcas[f"pesos_c7{sufixo}"] = (
            comb["escolha_c6"],
            comb["pesos_c7"],
        )
        linhas_rf["rf" + sufixo] = comb["rf"]
    if (
        "B" in possiveis and "Q_b" in est
    ):  # fatorial R: coorte amortecida e C1 a C7 refeitas com a coorte e o conservador de cada R
        s_max = k - H
        reais_hist = ativas[H : k + 1] if s_max >= 0 else np.zeros(0)
        previsto["coorte_R0_B"], previsto["conservador_R0_B"] = (
            previsto["coorte_V0_B"],
            previsto["conservador_V0_B"],
        )
        previsto["coorte_R1_B"], previsto["conservador_R1_B"] = (
            previsto["coorte_V2_B"],
            previsto["conservador_V2_B"],
        )
        previsto["coorte_amortecida_R0_B"] = previsto["coorte_amortecida_B"]
        for familia in ["pessimista", "otimista"]:  # R0 é a V0 e R1 é a V2
            previsto[f"{familia}_R0_B"] = previsto[f"{familia}_V0_B"]
            previsto[f"{familia}_R1_B"] = previsto[f"{familia}_V2_B"]
        if ieice:
            previsto["coorte_IEICE_R0_B"] = previsto["coorte_IEICE_B"]
            previsto["conservador_IEICE_R0_B"] = previsto["conservador_IEICE_B"]
            # com os novatos da V2 (R1 e R3) a coorte e o conservador do IEICE16 coincidem com os da V2
            previsto["conservador_IEICE_R1_B"] = previsto["conservador_V2_B"]
            previsto["conservador_IEICE_R3_B"] = previsto["conservador_R3_B"]
            for r in range(
                4
            ):  # C3 com a coorte do IEICE16: média simples da ingênua e dela; a previsão de repositórios entra só na coorte
                previsto[f"C3_IEICE_R{r}_B"] = (
                    previsto["ingenua"] + previsto[f"coorte_IEICE_R{r}_B"]
                ) / 2
        for c in COMBOS:
            previsto[f"{c}_R0_B"] = previsto[f"{c}_B"]
        for r in (1, 2, 3):
            nome_coorte = f"coorte_R{r}_B"
            w, _ = peso_da_coorte_amortecida(hist, ativas, k, H, nome_coorte)
            if not np.isnan(previsto[nome_coorte]):
                previsto[f"coorte_amortecida_R{r}_B"] = previsto["ingenua"] + w * (
                    previsto[nome_coorte] - previsto["ingenua"]
                )
            pool_r = [
                "ingenua",
                nome_coorte,
                f"conservador_R{r}_B",
                "deriva",
                "holt_amortecido",
                "hp3_B",
                "hp5_B",
                f"coorte_amortecida_R{r}_B",
            ]
            valores = np.array([previsto[m] for m in pool_r])
            rf_hist = hist[f"rf_R{r}_B"][: s_max + 1] if s_max >= 0 else np.zeros((0, len(regras)))
            comb = combinacoes(valores, rf_hist, reais_hist, regras, pool_r)
            for c, valor in comb["previsto"].items():
                previsto[f"{c}_R{r}_B"] = valor
            linhas_rf[f"rf_R{r}_B"] = comb["rf"]
    return {"previsto": previsto, "faixas": faixas, "marcas": marcas, "esparsidade": esparsidade, **linhas_rf, "negativas": contagem_negativas}  # fmt: skip
