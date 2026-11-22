"""Estado de uma linguagem, população e passo: pirâmides de pessoas e de repositórios e as séries que os métodos usam. Ver `hipoteses.md`.

Entradas (da carga oficial refeita, `origem/`):
  - `pessoas`: DataFrame com `pessoa`, `ocasioes`, `codigo_do_primeiro` e `segunda` (dia em que começou a segunda ocasião, NaT para casual);
  - `eventos`: dict de arrays `pessoa`, `codigo` e `dia` (datetime64[D]), um por par (pessoa, repositório, dia) com evento.

`constroi_estado(..., corte)` descarta tudo que passa de `corte` e confere isso com um assert. Cada valor de cada bloco depende só de eventos até o fim do bloco.

Blocos: o passo em meses define as datas de fim de bloco (12, 6, 3, 2 e 1 mês: fim de mês; 0,5: dia 15 e fim de mês). O bloco j vai de (data j-1, data j].
  - Ativo na data k: evento nos últimos `nb` blocos (nb = 12 / passo), ou seja, nos 12 meses até a data k. A janela é de 12 meses em todos os passos.
  - Idade em anos, como na rodada oficial (idade descontada): número de anos anteriores com atividade, recalculado em cada data só com dados até ela. Os anos são contados para trás a
    partir da data (12 meses cada um): idade(k) = número de datas k - nb, k - 2 nb, ... em que a pessoa estava ativa na janela de 12 meses. Em 31 de dezembro isso é o ano de calendário.
  - Faixas: de 1 ano, de 0 a 8 anos (`TOPO = 8`) e uma aberta para quem tem mais. As 6 faixas do artigo agrupam por ano (`faixa6`).
  - O passo só define as datas em que o estado é atualizado e o intervalo entre origens.

Populações: P0 = ocasiões da vida inteira (mais de uma), P1 = residente desde o bloco da segunda ocasião (só o passado), P2 = todos.
"""

import numpy as np
import pandas as pd

ANO0 = 2008
FIM = np.datetime64("2024-12-31")
BIG = 10**6
TOPO = 8


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


def soma_em_faixas6(v: np.ndarray) -> np.ndarray:
    """Soma a pirâmide (faixas de 1 ano, última aberta) nas 6 faixas: 0-1, 1-2, 2-3, 3-5, 5-8 e 8+."""
    soma = np.zeros(6)
    for b in range(len(v)):
        soma[faixa6_do_ano(b)] += v[b]
    return soma


def constroi_estado(
    pessoas: pd.DataFrame, eventos: dict, passo_meses: float, populacao: str, corte: np.datetime64
) -> dict:
    """Pirâmides e séries por bloco até `corte` (que precisa ser uma data da grade). `populacao` é P0, P1 ou P2."""
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

    ativ_p = np.zeros((n, K1), dtype=bool)
    ativ_p[p_idx, bloco] = True
    na_epoca = bloco >= R[p_idx]  # evento de quem já era residente no bloco do evento
    ativ_r = np.zeros((n_repos, K1), dtype=bool)
    ativ_r[r_idx[na_epoca], bloco[na_epoca]] = True
    primeiro_r = np.where(ativ_r.any(axis=1), ativ_r.argmax(axis=1), BIG)

    # pares (pessoa, repositório) ativos nos últimos nb blocos e residentes no bloco: cada evento vale o bloco e os nb - 1 seguintes, sem contar duas vezes
    chave = np.unique((p_idx * n_repos + r_idx) * K1 + bloco)
    par, b = chave // K1, chave % K1
    r_par = par % n_repos
    p_par = par // n_repos
    proximo_b = np.full(len(chave), BIG, dtype=np.int64)
    mesmo_par = par[1:] == par[:-1]
    proximo_b[:-1] = np.where(mesmo_par, b[1:], BIG)
    fim = np.minimum(np.minimum(b + nb - 1, proximo_b - 1), K1 - 1)
    inicio = np.maximum(b, R[p_par])
    vale = inicio <= fim
    mais_um = np.bincount(r_par[vale] * (K1 + 1) + inicio[vale], minlength=n_repos * (K1 + 1))
    menos_um = np.bincount(r_par[vale] * (K1 + 1) + fim[vale] + 1, minlength=n_repos * (K1 + 1))
    par_ativo = np.cumsum((mais_um - menos_um).reshape(n_repos, K1 + 1), axis=1)[:, :K1].astype(
        np.int32
    )
    del mais_um, menos_um, chave, par, b, r_par, p_par, proximo_b, fim, inicio, vale
    cum_r = np.zeros((n_repos, K1 + 1), dtype=np.int16)
    cum_r[:, 1:] = np.cumsum(ativ_r, axis=1, dtype=np.int16)
    inicio_janela = np.maximum(np.arange(K1) + 1 - nb, 0)
    janela_r = (
        cum_r[:, 1:] - cum_r[:, inicio_janela]
    ) > 0  # repositório com evento nos 12 meses até cada data
    if (
        populacao != "P1"
    ):  # sem residência por bloco, o repositório ativo é o que teve evento na janela
        assert ((par_ativo > 0) == janela_r).all(), (
            "pares ativos não conferem com a atividade do repositório"
        )
    idade_r = np.zeros(
        (n_repos, K1), dtype=np.int16
    )  # idade em anos: datas k - nb, k - 2 nb, ... com o repositório ativo
    for k in range(nb, K1):
        idade_r[:, k] = idade_r[:, k - nb] + janela_r[:, k - nb]
    del cum_r, janela_r

    pop_p = np.zeros((K1, topo + 2))
    pop_r = np.zeros((K1, topo + 2))
    NN, NE, PX, PN = (np.zeros(K1) for _ in range(4))
    janela = np.zeros(n, dtype=np.int16)
    idade_buf = np.zeros(
        (nb, n), dtype=np.int16
    )  # idade das últimas nb datas, para a recursão idade(k) = idade(k - nb) + ativo(k - nb)
    ativo_buf = np.zeros((nb, n), dtype=bool)
    for k in range(K1):
        janela += ativ_p[:, k]
        if k - nb >= 0:
            janela -= ativ_p[:, k - nb]
        ativo_janela = janela > 0
        espaco = k % nb
        idade = idade_buf[espaco] + ativo_buf[espaco] if k >= nb else np.zeros(n, dtype=np.int16)
        idade_buf[espaco], ativo_buf[espaco] = idade, ativo_janela
        ativo = ativo_janela & (k >= R)
        pop_p[k] = np.bincount(np.minimum(idade[ativo], topo + 1), minlength=topo + 2)
        idade_k = idade_r[:, k]
        ativo_r = par_ativo[:, k] > 0
        pop_r[k] = np.bincount(np.minimum(idade_k[ativo_r], topo + 1), minlength=topo + 2)
        PX[k] = par_ativo[ativo_r & (idade_k >= 1), k].sum()
        PN[k] = par_ativo[ativo_r & (idade_k == 0), k].sum()
        novato = ativo & (idade == 0)
        repos_dos_novatos = repo_do_primeiro[novato]
        em_repo_novo = idade_k[repos_dos_novatos] == 0
        NN[k] = em_repo_novo.sum()
        NE[k] = (~em_repo_novo).sum()
    assert np.allclose(NN + NE, pop_p[:, 0]), "novatos por repositório não somam os novatos"
    return {
        "datas": datas, "nb": nb, "topo": topo, "pop_p": pop_p, "pop_r": pop_r, "ativas": pop_p.sum(axis=1), "N": pop_p[:, 0], "R0": pop_r[:, 0],
        "E": pop_r[:, 1:].sum(axis=1), "NN": NN, "NE": NE, "PX": PX, "PN": PN, "pares": par_ativo.sum(axis=0).astype(float), "par_ativo": par_ativo,
        "idade_r": idade_r, "primeiro_r": primeiro_r, "n_repos": n_repos, "n_pessoas": n,
    }  # fmt: skip


def corta_estado(est: dict, k: int) -> dict:
    """O que se sabe na data do bloco k: as séries até k e nada depois. Repositório nascido depois de k não tem primeiro bloco."""
    saida = dict(est)
    saida["datas"] = est["datas"][: k + 1]
    for nome in ["pop_p", "pop_r", "ativas", "N", "R0", "E", "NN", "NE", "PX", "PN", "pares"]:
        saida[nome] = est[nome][: k + 1]
    saida["par_ativo"] = est["par_ativo"][:, : k + 1]
    saida["idade_r"] = est["idade_r"][:, : k + 1]
    saida["primeiro_r"] = np.where(est["primeiro_r"] <= k, est["primeiro_r"], BIG)
    return saida
