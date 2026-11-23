"""Números das figuras 2 e 3 de `figuras-v3/`: projeção do S2 por faixa e cenários de Clojure. Roda na VM.

Usa o estado do S2 (P1, passo de 12 meses, idade descontada, com parada de repositórios) e as mesmas
funções de `previsao.py` do experimento, sem previsão nova. Grava em `<saida>`:
  - `fig2_faixas.csv`: por linguagem e faixa, a população real de 2024 e a projeção de cada método
    (origem 31/12/2023). Ingênua-Coorte^R é a média da ingênua e da Coorte^R (a C3 em R3).
  - `fig2_totais.csv`: o total real de 2024 e o projetado de cada método.
  - `fig3a_taxas.csv`: as taxas de permanência sem parada dos 5 anos da janela, por faixa, e as quatro
    marcas (último ano, média dos dois últimos, mínimo e máximo).
  - `fig3b_serie.csv`: o total real por ano (só de Clojure) e, por origem de 2017 a 2023, a Coorte^R e o
    intervalo pessimista a otimista de R0 e de R3.

Uso (na raiz do repo, na VM): .venv/bin/python scripts/granularidade/figuras_v3_dados.py <carga> <saida> [linguagens]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import previsao
from estado import FIM, constroi_estado, corta_estado, soma_em_faixas6
from estado import junta_aberta_vet as junta_aberta
from previsao import familia_coorte, historico_sem_parada
from rodar import le_dados

CARGA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
LINGUAS = sys.argv[3:] or ["clojure", "elixir", "ocaml", "python"]
FAIXAS = ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"]
ORIGEM = np.datetime64("2023-12-31")
SAIDA.mkdir(parents=True, exist_ok=True)


def roda_origem(est: dict, k: int) -> tuple[dict, dict, dict]:
    """Totais, vetores por faixa e o estado cortado em k, com a coorte e os intervalos de R0 e R3."""
    est_k = corta_estado(est, k)
    primeiro_ativo = int(np.argmax(est_k["ativas"] > 0))
    previsao.SUMIDOURO_FAIXAS = {}
    contagem = {"avaliacoes": 0, "negativas": 0}
    resultado = familia_coorte(est_k, k, "B", primeiro_ativo, contagem, 1, False)
    vetores = previsao.SUMIDOURO_FAIXAS
    previsao.SUMIDOURO_FAIXAS = None
    return resultado["previsto"], vetores, {"est": est_k, "primeiro_ativo": primeiro_ativo}


linhas_faixas, linhas_totais, linhas_taxas, linhas_serie = [], [], [], []
for lingua in LINGUAS:
    pessoas, eventos = le_dados(CARGA, lingua)
    est = constroi_estado(
        pessoas, eventos, 12, "P1", FIM, janela_blocos=None, idade="descontada", com_parada=True
    )
    datas = est["datas"]
    k = int(np.where(datas == ORIGEM)[0][0])
    previsto, vetores, contexto = roda_origem(est, k)
    ingenua = soma_em_faixas6(junta_aberta(est["pop_p_b"][k]), est["nb"])
    real = soma_em_faixas6(junta_aberta(est["pop_p_b"][k + 1]), est["nb"])
    por_faixa = {
        "Ingênua": ingenua,
        "Coorte": vetores["coorte_V0_B"],
        "Conservador^R": vetores["conservador_R3_B"],
        "Ingênua-Coorte^R": (ingenua + vetores["coorte_R3_B"]) / 2,
        "Pessimista R3": vetores["pessimista_R3_B"],
        "Otimista R3": vetores["otimista_R3_B"],
    }
    for i, faixa in enumerate(FAIXAS):
        linha = {"linguagem": lingua, "faixa": faixa, "real_2024": float(real[i])}
        for nome, vetor in por_faixa.items():
            linha[nome] = float(vetor[i])
        linhas_faixas.append(linha)
    total = {"linguagem": lingua, "real_2024": float(est["ativas"][k + 1])}
    for nome, vetor in por_faixa.items():
        total[nome] = float(vetor.sum())
    linhas_totais.append(total)

    if lingua == "clojure":
        est_k, primeiro = contexto["est"], contexto["primeiro_ativo"]
        historico = historico_sem_parada(est_k, k, primeiro, 5)  # a linha 0 é o último ano
        for j in range(len(historico)):
            for i, taxa in enumerate(historico[j]):
                linhas_taxas.append(
                    {"faixa": i, "ano_da_taxa": int(str(datas[k - j])[:4]), "taxa": float(taxa)}
                )
        sem_nenhuma = np.all(np.isnan(historico), axis=0)
        ultimo = historico[0]
        menor = np.where(
            sem_nenhuma, np.nan, np.nanmin(np.where(np.isnan(historico), np.inf, historico), axis=0)
        )
        maior = np.where(
            sem_nenhuma,
            np.nan,
            np.nanmax(np.where(np.isnan(historico), -np.inf, historico), axis=0),
        )
        menor, maior = (
            np.where(np.isnan(menor), ultimo, menor),
            np.where(np.isnan(maior), ultimo, maior),
        )
        recorte = historico[:2]
        quantos = np.maximum((~np.isnan(recorte)).sum(axis=0), 1)
        meio = np.where(
            np.all(np.isnan(recorte), axis=0), np.nan, np.nansum(recorte, axis=0) / quantos
        )
        meio = np.where(np.isnan(meio), ultimo, meio)
        for i in range(len(ultimo)):
            linhas_taxas.append({"faixa": i, "ano_da_taxa": "ultimo", "taxa": float(ultimo[i])})
            linhas_taxas.append({"faixa": i, "ano_da_taxa": "media_dois", "taxa": float(meio[i])})
            linhas_taxas.append({"faixa": i, "ano_da_taxa": "minimo", "taxa": float(menor[i])})
            linhas_taxas.append({"faixa": i, "ano_da_taxa": "maximo", "taxa": float(maior[i])})

        for ano in range(2010, 2025):
            posicao = int(np.where(datas == np.datetime64(f"{ano}-12-31"))[0][0])
            linhas_serie.append(
                {"tipo": "real", "ano": ano, "valor": float(est["ativas"][posicao])}
            )
        for ano_origem in range(2017, 2024):
            posicao = int(np.where(datas == np.datetime64(f"{ano_origem}-12-31"))[0][0])
            prev, _, _ = roda_origem(est, posicao)
            alvo = float(est["ativas"][posicao + 1])
            linha = {
                "tipo": "projecao",
                "ano": ano_origem + 1,
                "valor": alvo,
                "coorte_R": prev["coorte_R3_B"],
                "pessimista_R0": prev["pessimista_V0_B"],
                "otimista_R0": prev["otimista_V0_B"],
                "pessimista_R3": prev["pessimista_R3_B"],
                "otimista_R3": prev["otimista_R3_B"],
            }
            linha["fora_R0"] = bool(alvo < linha["pessimista_R0"] or alvo > linha["otimista_R0"])
            linha["fora_R3"] = bool(alvo < linha["pessimista_R3"] or alvo > linha["otimista_R3"])
            linhas_serie.append(linha)
    print(f"{lingua}: pronto", flush=True)

pd.DataFrame(linhas_faixas).to_csv(SAIDA / "fig2_faixas.csv", index=False)
pd.DataFrame(linhas_totais).to_csv(SAIDA / "fig2_totais.csv", index=False)
pd.DataFrame(linhas_taxas).to_csv(SAIDA / "fig3a_taxas.csv", index=False)
pd.DataFrame(linhas_serie).to_csv(SAIDA / "fig3b_serie.csv", index=False)
