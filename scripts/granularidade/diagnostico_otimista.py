"""Diagnóstico do otimista e do pessimista de R1 e R3 no S2 (ver `hipoteses.md` de `projecao-rq3/cobertura-v2/`). Roda na VM.

Para cada origem de dezembro de 2017 a 2023 (Elixir de 2020), refaz com as funções de `previsao.py` os novatos do ponto central da V2
e os do otimista e do pessimista da V2, e confere o que o resultado da `cobertura/` já mostra:
  - os fatores (repositórios novos, repositórios existentes projetados) contra o máximo e o mínimo da janela;
  - se o ponto central (Coorte^R e Conservador^R de R3) passa do otimista ou fica abaixo do pessimista;
  - o contrafactual: o otimista (pessimista) com o novato trocado pelo maior (menor) entre o do passado e o central. Isso é o que a regra nova faz.
O diagnóstico não muda nenhuma previsão. Confere o que recalculou contra as previsões salvas na `cobertura/`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/diagnostico_otimista.py <carga> <cobertura> <saida.csv> clojure elixir ocaml python
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estado import FIM, constroi_estado, corta_estado, junta_aberta_vet
from previsao import (
    historico_sem_parada,
    maximo,
    media_n,
    minimo,
    projeta,
    projeta_repos,
    taxa_dos_repos_maduros,
    taxas,
)
from rodar import le_dados

CARGA, COBERTURA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
LINGUAS = sys.argv[4:]


def carrega_previsto(lingua: str) -> pd.DataFrame:
    partes = [pd.read_csv(COBERTURA / "unidades" / f"{lingua}_S2_pares.csv.gz")]
    for r in (1, 2, 3):
        partes.append(pd.read_csv(COBERTURA / "unidades" / f"{lingua}_S2_R{r}_pares.csv.gz"))
    todos = pd.concat(partes, ignore_index=True)
    return todos.pivot(index="k", columns="metodo", values="previsto")


linhas = []
for lingua in LINGUAS:
    pessoas, eventos = le_dados(CARGA, lingua)
    est_total = constroi_estado(
        pessoas, eventos, 12, "P1", FIM, janela_blocos=None, idade="descontada", com_parada=True
    )
    salvo = carrega_previsto(lingua)
    ativas = est_total["ativas"]
    primeiro_ativo = int(np.argmax(ativas > 0))
    n2, n5 = 2, 5
    for k in salvo.index:
        origem = str(est_total["datas"][k])
        if origem < "2017-12-31":
            continue
        est = corta_estado(est_total, k)
        atual = junta_aberta_vet(est["pop_p_b"][k])
        R0, E, NN, NE = est["R0_b"], est["E_b"], est["NN_b"], est["NE_b"]
        historico = historico_sem_parada(est, k, primeiro_ativo, n5)
        janela = np.arange(k - len(historico) + 1, k + 1)
        # taxas de permanência por faixa: as de R3 (sem parada vezes um menos a saída por parada), como em `intervalos_r`
        na_faixa = np.where(atual > 0, atual, 1.0)
        saida_parada = np.clip(junta_aberta_vet(est["Q_b"][k]) / na_faixa, 0.0, 1.0)
        sem_nenhuma = np.all(np.isnan(historico), axis=0)
        menor = np.where(
            sem_nenhuma, np.nan, np.nanmin(np.where(np.isnan(historico), np.inf, historico), axis=0)
        )
        maior = np.where(
            sem_nenhuma,
            np.nan,
            np.nanmax(np.where(np.isnan(historico), -np.inf, historico), axis=0),
        )
        menor = np.where(np.isnan(menor), historico[0], menor)
        maior = np.where(np.isnan(maior), historico[0], maior)
        ultima = historico[0]
        media = np.where(
            np.all(np.isnan(historico[:n2]), axis=0),
            np.nan,
            np.nansum(historico[:n2], axis=0)
            / np.maximum((~np.isnan(historico[:n2])).sum(axis=0), 1),
        )
        media = np.where(np.isnan(media), ultima, media)
        # fatores dos novatos da V2
        with np.errstate(divide="ignore", invalid="ignore"):
            M_NOVO = np.where(R0 > 0, NN / np.where(R0 > 0, R0, 1), np.nan)
            M_EX = np.where(E > 0, NE / np.where(E > 0, E, 1), np.nan)
        pop_r = est["pop_r_b"]
        sr_repos = taxas(pop_r[k], pop_r[k - 1])
        fallback = taxa_dos_repos_maduros(pop_r[k], pop_r[k - 1])
        R0m = media_n(R0, k, n2)
        E_v2 = projeta_repos(junta_aberta_vet(pop_r[k]), sr_repos, fallback, R0m, 1)[0]
        mn_m, me_m = media_n(M_NOVO, k, n2), media_n(M_EX, k, n2)
        central = R0m * mn_m + E_v2 * me_m
        otim_novatos = maximo(R0[janela]) * maximo(M_NOVO[janela]) + maximo(E[janela]) * maximo(
            M_EX[janela]
        )
        pess_novatos = minimo(R0[janela]) * minimo(M_NOVO[janela]) + minimo(E[janela]) * minimo(
            M_EX[janela]
        )
        # contrafactual (regra nova): fator de novos e de existentes pelo maior (menor) entre o passado e o projetado
        otim_nova = max(maximo(R0[janela]), R0m) * maximo(M_NOVO[janela]) + max(
            maximo(E[janela]), E_v2
        ) * maximo(M_EX[janela])
        pess_nova = min(minimo(R0[janela]), R0m) * minimo(M_NOVO[janela]) + min(
            minimo(E[janela]), E_v2
        ) * minimo(M_EX[janela])
        sr_coorte = (1 - saida_parada) * ultima
        sr_cons = (1 - saida_parada) * media
        pontos = {
            "coorte_R3": float(projeta(atual, sr_coorte, [central]).sum()),
            "conservador_R3": float(projeta(atual, sr_cons, [central]).sum()),
        }
        otim_antiga = float(projeta(atual, (1 - saida_parada) * maior, [otim_novatos]).sum())
        pess_antiga = float(projeta(atual, (1 - saida_parada) * menor, [pess_novatos]).sum())
        otim_n = float(projeta(atual, (1 - saida_parada) * maior, [otim_nova]).sum())
        pess_n = float(projeta(atual, (1 - saida_parada) * menor, [pess_nova]).sum())
        # conferência contra o que já estava salvo
        conferido = {
            "coorte_R3": pontos["coorte_R3"],
            "conservador_R3": pontos["conservador_R3"],
            "otimista_R3": otim_antiga,
            "pessimista_R3": pess_antiga,
        }
        maior_dif = max(
            abs(conferido[m] - salvo.loc[k, m]) / max(1.0, abs(salvo.loc[k, m])) for m in conferido
        )
        if maior_dif > 1e-6:
            sys.exit(
                f"{lingua} {origem}: o que recalculei difere do salvo ({maior_dif:.2e}). Parei."
            )
        linhas.append(
            {
                "linguagem": lingua,
                "origem": origem,
                "R0_projetado": R0m,
                "R0_max_janela": maximo(R0[janela]),
                "E_projetado": E_v2,
                "E_max_janela": maximo(E[janela]),
                "E_min_janela": minimo(E[janela]),
                "novatos_central": central,
                "novatos_otimista": otim_novatos,
                "novatos_pessimista": pess_novatos,
                "novatos_otimista_novo": otim_nova,
                "novatos_pessimista_novo": pess_nova,
                "coorte_R3": pontos["coorte_R3"],
                "conservador_R3": pontos["conservador_R3"],
                "pessimista_R3": pess_antiga,
                "otimista_R3": otim_antiga,
                "pessimista_R3_novo": pess_n,
                "otimista_R3_novo": otim_n,
                "diferenca_maxima_ao_salvo": maior_dif,
            }
        )
    print(f"{lingua}: diagnóstico feito", flush=True)
    pd.DataFrame(linhas).to_csv(SAIDA, index=False, float_format="%.10g")
print("pronto")
