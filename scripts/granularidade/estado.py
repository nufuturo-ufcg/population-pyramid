"""Estado de uma linguagem, população e passo: pirâmides de pessoas e de repositórios e as séries que os métodos usam. Ver `hipoteses.md`.

Entradas (da carga oficial refeita, `origem/`):
  - `pessoas`: DataFrame com `pessoa`, `ocasioes`, `codigo_do_primeiro` e `segunda` (dia em que começou a segunda ocasião, NaT para casual);
  - `eventos`: dict de arrays `pessoa`, `codigo` e `dia` (datetime64[D]), um por par (pessoa, repositório, dia) com evento.

`constroi_estado(..., corte)` descarta tudo que passa de `corte` e confere isso com um assert. Cada valor de cada bloco depende só de eventos até o fim do bloco.

Blocos: o passo em meses define as datas de fim de bloco (12, 6, 3, 2 e 1 mês: fim de mês; 0,5: dia 15 e fim de mês). O bloco j vai de (data j-1, data j].
  - Ativo na data k: evento nos últimos `nb` blocos (nb = 12 / passo), ou seja, nos 12 meses até a data k. A janela é de 12 meses em todos os passos.
  - Idade em anos, como na rodada oficial (idade descontada): número de anos anteriores com atividade, recalculado em cada data só com dados até ela. Os anos são contados para trás a
    partir da data (12 meses cada um): idade(k) = número de datas k - nb, k - 2 nb, ... em que a pessoa estava ativa na janela de 12 meses. Em 31 de dezembro isso é o ano de calendário.
  - Versão A (faixa anual): faixas de 1 ano, de 0 a 8 anos (`TOPO = 8`) e uma aberta para quem tem mais. As 6 faixas do artigo agrupam por ano (`faixa6`).
  - Versão B (faixa do passo, `*_b`): idade na régua da largura do passo, idade(k) = número das datas k - 1, k - 2, ... em que a pessoa estava ativa na janela de 12 meses. Faixas
    de um passo, de 0 a 8 anos (`TOPO * nb` faixas) e uma aberta. Com passo de 12 meses A e B são iguais.
  - O passo só define as datas em que o estado é atualizado e o intervalo entre origens.

Populações: P0 = ocasiões da vida inteira (mais de uma), P1 = residente desde o bloco da segunda ocasião (só o passado), P2 = todos.
"""

import numpy as np
import pandas as pd

ANO0 = 2008
FIM = np.datetime64("2024-12-31")
BIG = 10**6
TOPO = 8
DIAS_BANDA = (
    365.25 / 4
)  # banda de 3 meses do IEICE16: (0, 3], (3, 6], ... meses desde a primeira contribuição


def grade(passo_meses: float, ate: np.datetime64 = FIM) -> np.ndarray:
    """Datas de fim de bloco desde 2008, até `ate` (inclusive)."""
    datas = []
    for ano in range(ANO0, 2025):
        for mes in range(1, 13):
            fim_mes = (
                (pd.Timestamp(ano, mes, 1) + pd.offsets.MonthEnd(0))
                .to_datetime64()
                .astype("datetime64[D]")
            )
            numero_do_mes = (ano - ANO0) * 12 + mes
            if passo_meses == 0.5:
                datas.append(np.datetime64(f"{ano}-{mes:02d}-15"))
                datas.append(fim_mes)
            elif numero_do_mes % int(passo_meses) == 0:
                datas.append(fim_mes)
    datas = np.array(datas, dtype="datetime64[D]")
    return datas[datas <= ate]


def faixa6_do_ano(ano: int) -> int:
    if ano >= 8:
        return 5
    if ano >= 5:
        return 4
    if ano >= 3:
        return 3
    return ano


def junta_aberta_vet(v: np.ndarray) -> np.ndarray:
    p = v[:-1].copy()
    p[-1] = p[-1] + v[-1]
    return p


def soma_em_faixas6(v: np.ndarray, por_ano: int = 1) -> np.ndarray:
    """Soma a pirâmide (última faixa aberta) nas 6 faixas: 0-1, 1-2, 2-3, 3-5, 5-8 e 8+. `por_ano` é o número de faixas finas em 1 ano (1 na versão A, nb na B)."""
    soma = np.zeros(6)
    for b in range(len(v)):
        soma[faixa6_do_ano(b // por_ano)] += v[b]
    return soma


def constroi_estado(
    pessoas: pd.DataFrame,
    eventos: dict,
    passo_meses: float,
    populacao: str,
    corte: np.datetime64,
    janela_blocos: int | None = None,
    idade: str = "descontada",
    com_parada: bool = False,
) -> dict:
    """Pirâmides e séries por bloco até `corte` (que precisa ser uma data da grade). `populacao` é P0, P1 ou P2.

    `janela_blocos`: janela de atividade em blocos (padrão 12 meses). `idade`: "descontada" (rodada oficial, só com janela de 12 meses) ou "tempo" (IEICE16: tempo desde a primeira
    contribuição em bandas de 3 meses, sem desconto; só as pirâmides B). `com_parada`: calcula também, na régua B, a probabilidade de parada dos repositórios por idade, a soma por
    banda da probabilidade de a pessoa ficar sem repositório (`Q_b`) e as pessoas que ficaram sem repositório entre duas datas (`ORF_b`).
    """
    datas = grade(passo_meses, corte)
    assert len(datas) > 0 and datas[-1] == corte, "o corte precisa ser uma data da grade"
    nb = round(12 / passo_meses)
    topo = TOPO
    K1 = len(datas)

    dentro = eventos["dia"] <= corte
    ev_pessoa, ev_codigo, ev_dia = (
        eventos["pessoa"][dentro],
        eventos["codigo"][dentro],
        eventos["dia"][dentro],
    )
    assert len(ev_dia) == 0 or ev_dia.max() <= corte, "evento depois do corte"

    # população: quem entra e a partir de que bloco conta como residente
    segunda = pessoas["segunda"].to_numpy().astype("datetime64[D]")
    segunda_vale = ~np.isnat(segunda) & (
        segunda <= corte
    )  # segunda ocasião depois do corte ainda não aconteceu
    if populacao == "P0":
        incluida = pessoas["ocasioes"].to_numpy() > 1
        bloco_residente = np.zeros(len(pessoas), dtype=np.int64)
    elif populacao == "P1":
        incluida = segunda_vale
        bloco_residente = np.zeros(len(pessoas), dtype=np.int64)
        bloco_residente[segunda_vale] = np.searchsorted(datas, segunda[segunda_vale], side="left")
    else:
        assert populacao == "P2"
        incluida = np.ones(len(pessoas), dtype=bool)
        bloco_residente = np.zeros(len(pessoas), dtype=np.int64)
    ids_pessoas = pessoas["pessoa"].to_numpy()
    ordem = np.argsort(ids_pessoas)
    ids_pessoas, incluida, bloco_residente = (
        ids_pessoas[ordem],
        incluida[ordem],
        bloco_residente[ordem],
    )
    cod_primeiro_todos = pessoas["codigo_do_primeiro"].to_numpy()[ordem]
    pos = np.searchsorted(ids_pessoas, ev_pessoa)
    pos = np.minimum(pos, len(ids_pessoas) - 1)
    assert (ids_pessoas[pos] == ev_pessoa).all(), "evento de pessoa fora da tabela de pessoas"
    mantem = incluida[pos]
    pos, ev_codigo, ev_dia = pos[mantem], ev_codigo[mantem], ev_dia[mantem]
    usadas, p_idx = np.unique(pos, return_inverse=True)  # só pessoas com evento até o corte
    p_idx = p_idx.astype(np.int64)
    n = len(usadas)
    R = bloco_residente[usadas]
    cod_primeiro = cod_primeiro_todos[usadas]
    bloco = np.searchsorted(datas, ev_dia, side="left").astype(np.int64)
    assert (bloco < K1).all()

    # repositórios: os que têm evento de pessoa da população
    codigos, r_idx = np.unique(ev_codigo, return_inverse=True)
    r_idx = r_idx.astype(np.int64)
    n_repos = len(codigos)
    repo_do_primeiro = np.searchsorted(codigos, cod_primeiro)
    assert (codigos[np.minimum(repo_do_primeiro, n_repos - 1)] == cod_primeiro).all(), (
        "repositório do primeiro evento fora do conjunto"
    )

    W = (
        janela_blocos if janela_blocos is not None else nb
    )  # janela de atividade em blocos (12 meses por padrão)
    por_tempo = idade == "tempo"
    if not por_tempo:
        assert nb == W, "a idade descontada pede janela de 12 meses"
    ativ_p = np.zeros((n, K1), dtype=bool)
    ativ_p[p_idx, bloco] = True
    na_epoca = bloco >= R[p_idx]  # evento de quem já era residente no bloco do evento
    ativ_r = np.zeros((n_repos, K1), dtype=bool)
    ativ_r[r_idx[na_epoca], bloco[na_epoca]] = True
    primeiro_r = np.where(ativ_r.any(axis=1), ativ_r.argmax(axis=1), BIG)
    if por_tempo:  # idade pelo tempo desde a primeira contribuição, sem desconto (IEICE16)
        dia_int = ev_dia.astype("datetime64[D]").astype(np.int64)
        sem_dia = np.iinfo(np.int64).max
        primeiro_dia_p = np.full(n, sem_dia, dtype=np.int64)
        np.minimum.at(primeiro_dia_p, p_idx, dia_int)
        primeiro_dia_r = np.full(n_repos, sem_dia, dtype=np.int64)
        np.minimum.at(primeiro_dia_r, r_idx[na_epoca], dia_int[na_epoca])
        datas_int = datas.astype("datetime64[D]").astype(np.int64)

    # pares (pessoa, repositório) ativos na janela e residentes no bloco: cada evento vale o bloco e os W - 1 seguintes, sem contar duas vezes
    chave = np.unique((p_idx * n_repos + r_idx) * K1 + bloco)
    par, b = chave // K1, chave % K1
    r_par = par % n_repos
    p_par = par // n_repos
    proximo_b = np.full(len(chave), BIG, dtype=np.int64)
    mesmo_par = par[1:] == par[:-1]
    proximo_b[:-1] = np.where(mesmo_par, b[1:], BIG)
    fim = np.minimum(np.minimum(b + W - 1, proximo_b - 1), K1 - 1)
    inicio = np.maximum(b, R[p_par])
    vale = inicio <= fim
    mais_um = np.bincount(r_par[vale] * (K1 + 1) + inicio[vale], minlength=n_repos * (K1 + 1))
    menos_um = np.bincount(r_par[vale] * (K1 + 1) + fim[vale] + 1, minlength=n_repos * (K1 + 1))
    par_ativo = np.cumsum((mais_um - menos_um).reshape(n_repos, K1 + 1), axis=1)[:, :K1].astype(
        np.int32
    )
    if com_parada:
        p_par, r_par, inicio, fim = p_par[vale], r_par[vale], inicio[vale], fim[vale]
    del mais_um, menos_um, chave, par, b, proximo_b, vale
    if not com_parada:
        del r_par, p_par, inicio, fim
    cum_r = np.zeros((n_repos, K1 + 1), dtype=np.int16)
    cum_r[:, 1:] = np.cumsum(ativ_r, axis=1, dtype=np.int16)
    inicio_janela = np.maximum(np.arange(K1) + 1 - W, 0)
    janela_r = (
        cum_r[:, 1:] - cum_r[:, inicio_janela]
    ) > 0  # repositório com evento na janela até cada data
    if (
        populacao != "P1"
    ):  # sem residência por bloco, o repositório ativo é o que teve evento na janela
        assert ((par_ativo > 0) == janela_r).all(), (
            "pares ativos não conferem com a atividade do repositório"
        )
    del cum_r

    topo_b = TOPO * nb  # versão B: faixas da largura do passo, de 0 a 8 anos
    pop_p, pop_r = np.zeros((K1, topo + 2)), np.zeros((K1, topo + 2))
    pop_p_b, pop_r_b = np.zeros((K1, topo_b + 2)), np.zeros((K1, topo_b + 2))
    NN, NE, PX, PN, NN_b, NE_b, PX_b, PN_b = (np.zeros(K1) for _ in range(8))
    Q_b, ORF_b, PSTOP_b = (np.zeros((K1, topo_b + 2)) for _ in range(3))
    PSTOP_b[:] = np.nan
    janela = np.zeros(n, dtype=np.int16)
    # versão A: idade(k) = idade(k - nb) + ativo(k - nb). Versão B: idade(k) = idade(k - 1) + ativo(k - 1). Idade pelo tempo: banda = teto(dias desde a primeira contribuição / 91,3125) - 1.
    idade_buf = np.zeros((nb, n), dtype=np.int16)
    ativo_buf = np.zeros((nb, n), dtype=bool)
    idade_r_buf = np.zeros((nb, n_repos), dtype=np.int16)
    ativo_r_buf = np.zeros((nb, n_repos), dtype=bool)
    idade_b = np.zeros(n, dtype=np.int32)
    idade_r_b = np.zeros(n_repos, dtype=np.int32)
    ativo_anterior = np.zeros(n, dtype=bool)
    ativo_r_anterior = np.zeros(n_repos, dtype=bool)
    banda_r_anterior = np.zeros(n_repos, dtype=np.int64)
    for k in range(K1):
        janela += ativ_p[:, k]
        if k - W >= 0:
            janela -= ativ_p[:, k - W]
        ativo_janela = janela > 0
        janela_do_repo = janela_r[:, k]
        ativo = ativo_janela & (k >= R)
        ativo_r = par_ativo[:, k] > 0
        par_k = par_ativo[:, k]
        if por_tempo:
            idade_b = np.clip(
                np.ceil((datas_int[k] - primeiro_dia_p) / DIAS_BANDA) - 1, 0, None
            ).astype(np.int32)
            idade_r_b = np.clip(
                np.ceil((datas_int[k] - primeiro_dia_r) / DIAS_BANDA) - 1, 0, None
            ).astype(np.int32)
        else:
            espaco = k % nb
            idade = (
                idade_buf[espaco] + ativo_buf[espaco] if k >= nb else np.zeros(n, dtype=np.int16)
            )
            idade_buf[espaco], ativo_buf[espaco] = idade, ativo_janela
            idade_r_a = (
                idade_r_buf[espaco] + ativo_r_buf[espaco]
                if k >= nb
                else np.zeros(n_repos, dtype=np.int16)
            )
            idade_r_buf[espaco], ativo_r_buf[espaco] = idade_r_a, janela_do_repo
            idade_b = idade_b + ativo_anterior
            idade_r_b = idade_r_b + ativo_r_anterior
            ativo_anterior, ativo_r_anterior = ativo_janela, janela_do_repo
            pop_p[k], pop_r[k], NN[k], NE[k], PX[k], PN[k] = linha_do_estado(
                idade, ativo, idade_r_a, ativo_r, par_k, repo_do_primeiro, topo
            )
        pop_p_b[k], pop_r_b[k], NN_b[k], NE_b[k], PX_b[k], PN_b[k] = linha_do_estado(
            idade_b, ativo, idade_r_b, ativo_r, par_k, repo_do_primeiro, topo_b
        )
        if com_parada:
            banda_p = np.minimum(idade_b, topo_b + 1)
            banda_r = np.minimum(idade_r_b, topo_b + 1)
            pstop_k = np.full(topo_b + 2, np.nan)
            geral = 0.0
            if k >= 1:  # parada observada entre k - 1 e k, por idade do repositório em k - 1
                antes = par_ativo[:, k - 1] > 0
                ativos_por_idade = np.bincount(banda_r_anterior[antes], minlength=topo_b + 2)
                pararam = np.bincount(banda_r_anterior[antes & ~ativo_r], minlength=topo_b + 2)
                com_ativos = ativos_por_idade > 0
                pstop_k[com_ativos] = pararam[com_ativos] / ativos_por_idade[com_ativos]
                geral = pararam.sum() / max(ativos_por_idade.sum(), 1)
            PSTOP_b[k] = pstop_k
            p_uso = np.where(
                np.isnan(pstop_k), geral, pstop_k
            )  # idade sem repositório ativo recebe a taxa geral
            agora = np.where((inicio <= k) & (fim >= k))[
                0
            ]  # pares ativos em k, só de residentes no bloco
            pessoa_k, repo_k = p_par[agora], r_par[agora]
            soma_log = np.bincount(
                pessoa_k, weights=np.log(np.clip(p_uso[banda_r[repo_k]], 1e-9, 1.0)), minlength=n
            )
            em_pares = np.bincount(pessoa_k, minlength=n) > 0
            Q_b[k] = np.bincount(
                banda_p[em_pares], weights=np.exp(soma_log[em_pares]), minlength=topo_b + 2
            )
            if (
                k + 1 < K1
            ):  # pessoa cujos repositórios ativos em k estão todos inativos em k + 1 (guardada em k + 1)
                vivos = par_ativo[repo_k, k + 1] > 0
                com_repo_vivo = np.bincount(pessoa_k[vivos], minlength=n) > 0
                ORF_b[k + 1] = np.bincount(banda_p[em_pares & ~com_repo_vivo], minlength=topo_b + 2)
            banda_r_anterior = banda_r
    if por_tempo:
        pop_p, pop_r = pop_p_b, pop_r_b
        NN, NE, PX, PN = NN_b, NE_b, PX_b, PN_b
    assert np.allclose(NN_b + NE_b, pop_p_b[:, 0]), (
        "novatos por repositório (B) não somam os novatos"
    )
    assert np.allclose(pop_p.sum(axis=1), pop_p_b.sum(axis=1)), (
        "A e B têm total de ativos diferente"
    )
    est = {
        "datas": datas, "nb": nb, "topo": topo, "topo_b": topo_b, "pop_p": pop_p, "pop_r": pop_r, "ativas": pop_p.sum(axis=1), "N": pop_p[:, 0], "R0": pop_r[:, 0],
        "E": pop_r[:, 1:].sum(axis=1), "NN": NN, "NE": NE, "PX": PX, "PN": PN, "pares": par_ativo.sum(axis=0).astype(float), "par_ativo": par_ativo,
        "pop_p_b": pop_p_b, "pop_r_b": pop_r_b, "N_b": pop_p_b[:, 0], "R0_b": pop_r_b[:, 0], "E_b": pop_r_b[:, 1:].sum(axis=1), "NN_b": NN_b, "NE_b": NE_b, "PX_b": PX_b, "PN_b": PN_b,
        "primeiro_r": primeiro_r, "n_repos": n_repos, "n_pessoas": n,
    }  # fmt: skip
    if com_parada:
        est.update({"Q_b": Q_b, "ORF_b": ORF_b, "PSTOP_b": PSTOP_b})
    return est


def linha_do_estado(
    idade: np.ndarray,
    ativo: np.ndarray,
    idade_repo: np.ndarray,
    ativo_repo: np.ndarray,
    pares_do_repo: np.ndarray,
    repo_do_primeiro: np.ndarray,
    topo: int,
) -> tuple:
    """Pirâmides de pessoas e de repositórios numa data, na régua de idade dada, e novatos e pares por tipo de repositório."""
    pessoas_por_faixa = np.bincount(np.minimum(idade[ativo], topo + 1), minlength=topo + 2)
    repos_por_faixa = np.bincount(np.minimum(idade_repo[ativo_repo], topo + 1), minlength=topo + 2)
    pares_em_existentes = pares_do_repo[ativo_repo & (idade_repo >= 1)].sum()
    pares_em_novos = pares_do_repo[ativo_repo & (idade_repo == 0)].sum()
    novato = ativo & (idade == 0)
    em_repo_novo = idade_repo[repo_do_primeiro[novato]] == 0
    return (
        pessoas_por_faixa, repos_por_faixa, em_repo_novo.sum(), (~em_repo_novo).sum(),
        pares_em_existentes, pares_em_novos,
    )  # fmt: skip


SERIES_NO_TEMPO = [
    "pop_p", "pop_r", "ativas", "N", "R0", "E", "NN", "NE", "PX", "PN", "pares",
    "pop_p_b", "pop_r_b", "N_b", "R0_b", "E_b", "NN_b", "NE_b", "PX_b", "PN_b",
]  # fmt: skip
SERIES_DA_PARADA = ["Q_b", "ORF_b", "PSTOP_b"]


def corta_estado(est: dict, k: int) -> dict:
    """O que se sabe na data do bloco k: as séries até k e nada depois. Repositório nascido depois de k não tem primeiro bloco."""
    saida = dict(est)
    saida["datas"] = est["datas"][: k + 1]
    for nome in SERIES_NO_TEMPO + [n for n in SERIES_DA_PARADA if n in est]:
        saida[nome] = est[nome][: k + 1]
    saida["par_ativo"] = est["par_ativo"][:, : k + 1]
    saida["primeiro_r"] = np.where(est["primeiro_r"] <= k, est["primeiro_r"], BIG)
    return saida
