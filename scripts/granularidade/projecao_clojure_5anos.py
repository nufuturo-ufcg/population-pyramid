"""Projeção de Clojure para os próximos 5 anos (20 passos de 3 meses) pelos seis métodos, e o erro histórico por horizonte. Roda na VM.

Cenário Longo, não casuais (P1, idade descontada, ativo nos 12 meses até o recorte, faixas e passos de 3 meses), com as janelas curtas (`JANELA_DAS_CONTAGENS = 2`, `transicoes_parada = 2`)
e o Conservador de 5 anos (`JANELA_DO_CONSERVADOR = 20`). Origem: o último fim de trimestre com a pirâmide completa nos dados. Usa só o passado da origem.
Métodos: Ingênua, Coorte (`coorte_V0_B`), Coorte^R (`coorte_R3_B`), Conservador (`conservador_V0_B`), Conservador^R (`conservador_R3_B`) e Ingênua-Coorte^R (média da Ingênua e da Coorte^R).
A pirâmide de cada passo sai de `previsao.avanca` com a taxa e os novatos que o método usou (`previsao.DETALHE`); confere que o último passo é o vetor do método e que a soma é a `previsto`.

Conferências (param se falharem): as previsões de 4 passos de todas as origens reproduzem as do `S4k` (se `<pares S4k>` for dado); os 4 primeiros passos da projeção de 20 são a de 4;
teste de vazamento nas origens de amostra e na origem final (cortar os eventos em t não muda a previsão; entrar com eventos futuros ou promoções muda).

Grava em `<saida>`: `origem.md`, `trajetorias.csv`, `serie_anual.csv`, `erro_por_origem_e_passo.csv`, `erro_por_passo.csv`, `erro_por_horizonte.md`, `populacao_projetada.md` e `.csv`, `vazamento.md`.

Uso (na raiz do repo, na VM): .venv/bin/python scripts/granularidade/projecao_clojure_5anos.py <carga> <saida> [<pasta de unidades do S4k> ou - [<origem pedida, fim de trimestre>]]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import previsao
import vazamento
from estado import constroi_estado, corta_estado, grade, soma_em_faixas6
from estado import junta_aberta_vet as junta_aberta
from previsao import (
    POOL,
    avanca,
    gera_regras,
    metodos_b,
    metodos_intervalo_nova,
    metodos_intervalo_r,
    metodos_r,
    preve_estado,
)
from rodar import le_dados

CARGA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
UNIDADES_S4K = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "-" else None
ORIGEM_PEDIDA = (
    pd.Timestamp(sys.argv[4]) if len(sys.argv) > 4 else None
)  # padrão: o último fim de trimestre com a pirâmide completa
SAIDA.mkdir(parents=True, exist_ok=True)
NB = 4  # faixas e passos de 3 meses
PASSOS = 20
METODOS = ["Ingênua", "Coorte", "Coorte^R", "Conservador", "Conservador^R", "Ingênua-Coorte^R"]
CHAVE_DETALHE = {
    "Coorte": "coorte_V0_B",
    "Coorte^R": "coorte_R3_B",
    "Conservador": "conservador_V0_B",
    "Conservador^R": "conservador_R3_B",
}
CHAVE_PREVISTO = {
    "Ingênua": "ingenua",
    "Coorte": "coorte_V0_B",
    "Coorte^R": "coorte_R3_B",
    "Conservador": "conservador_V0_B",
    "Conservador^R": "conservador_R3_B",
    "Ingênua-Coorte^R": "C3_R3_B",
}
NOME_NOS_PARES = {
    "Ingênua": "ingenua",
    "Coorte": "coorte_R0",
    "Coorte^R": "coorte_R3",
    "Conservador": "conservador_R0",
    "Conservador^R": "conservador_R3",
    "Ingênua-Coorte^R": "C3_R3",
}
FAIXAS6 = ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"]
OPCOES_ESTADO = {
    "janela_blocos": NB,
    "idade": "descontada",
    "com_parada": True,
    "transicoes_parada": 2,
}


def milhar(x: float) -> str:
    return "n/d" if pd.isna(x) else f"{x:,.0f}".replace(",", ".")


def dec(x: float, casas: int = 1) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


# 1. Ponto de partida
pessoas, eventos = le_dados(CARGA, "clojure")
fim_dados = pd.Timestamp(eventos["dia"].max())
candidatas = [pd.Timestamp(d) for d in grade(3, np.datetime64("2030-12-31"))]
ORIGEM = max(d for d in candidatas if d <= fim_dados)
if ORIGEM_PEDIDA is not None:
    assert ORIGEM_PEDIDA in candidatas and ORIGEM_PEDIDA <= ORIGEM, (
        f"{ORIGEM_PEDIDA.date()} não é fim de trimestre com pirâmide completa"
    )
    ORIGEM = ORIGEM_PEDIDA
eventos_no_trimestre_aberto = int((eventos["dia"] > np.datetime64(ORIGEM)).sum())
(SAIDA / "origem.md").write_text(
    "\n".join(
        [
            "# Ponto de partida",
            "",
            f"- Último evento dos dados de Clojure: {fim_dados.date()}.",
            f"- Último fim de trimestre até essa data: {ORIGEM.date()}. O trimestre seguinte (até {(ORIGEM + pd.offsets.QuarterEnd(1)).date()}) só tem {eventos_no_trimestre_aberto} eventos, de {(ORIGEM + pd.Timedelta(days=1)).date()} a {fim_dados.date()}, e fica de fora.",
            f"- Origem usada: {ORIGEM.date()}{' (pedida, para comparação com a origem mais recente)' if ORIGEM_PEDIDA is not None else ''}. A pirâmide dessa data tem os 12 meses de janela completos, e a classificação de não casuais usa só as segundas ocasiões até essa data.",
            "",
        ]
    )
    + "\n",
    encoding="utf-8",
)

previsao.JANELA_DAS_CONTAGENS = 2
previsao.JANELA_DO_CONSERVADOR = 5 * NB
est = constroi_estado(pessoas, eventos, 3, "P1", np.datetime64(ORIGEM), **OPCOES_ESTADO)
datas = pd.to_datetime(est["datas"])
K1 = len(datas)
K0 = K1 - 1
assert datas[K0] == ORIGEM
K_2024 = int(np.where(datas == pd.Timestamp("2024-12-31"))[0][0])
K_ULTIMA_4 = K_2024 - NB  # 31/12/2023: a última origem com alvo de 1 ano conhecido
ativas = est["pop_p_b"].sum(axis=1)

regras = gera_regras(len(POOL))
nomes_hist = [
    "ingenua",
    "deriva",
    "holt_amortecido",
    *metodos_b(),
    *metodos_r(),
    *metodos_intervalo_r(),
    *metodos_intervalo_nova(),
]
hist = {
    "previsto": {m: np.full(K1, np.nan) for m in nomes_hist},
    "rf": np.full((K1, len(regras)), np.nan),
    "rf_B": np.full((K1, len(regras)), np.nan),
}
for r in (1, 2, 3):
    hist[f"rf_R{r}_B"] = np.full((K1, len(regras)), np.nan)
primeiro_ativo = int(np.argmax(ativas > 0))


def roda_origem(k: int, passos: int) -> tuple[dict, dict]:
    """Pirâmide de cada método em cada passo (lista de `passos` vetores) e o `previsto` do `preve_estado`."""
    previsao.DETALHE = {}
    res = preve_estado(corta_estado(est, k), hist, regras, POOL, ("B",), passos, False)
    detalhe, previsao.DETALHE = previsao.DETALHE, None
    atual = junta_aberta(est["pop_p_b"][k])
    traj = {"Ingênua": [atual.copy() for _ in range(passos)]}
    for metodo, chave in CHAVE_DETALHE.items():
        d = detalhe[chave]
        assert len(d["novatos"]) == passos, f"{metodo}: {len(d['novatos'])} passos de novatos"
        v, vs = atual, []
        for n in d["novatos"]:
            v = avanca(v, d["taxa"], n)
            vs.append(v)
        assert np.allclose(vs[-1], d["vetor"], rtol=1e-9, atol=1e-9, equal_nan=True), (
            f"{metodo}: o último passo não é o vetor do método"
        )
        traj[metodo] = vs
    traj["Ingênua-Coorte^R"] = [
        (a + b) / 2 for a, b in zip(traj["Ingênua"], traj["Coorte^R"], strict=True)
    ]
    for metodo in METODOS:
        total = float(np.sum(traj[metodo][-1]))
        esperado = res["previsto"][CHAVE_PREVISTO[metodo]]
        assert (np.isnan(total) and np.isnan(esperado)) or abs(total - esperado) <= 1e-8 * max(
            1.0, abs(esperado)
        ), f"{metodo} em {datas[k].date()}: soma {total} contra previsto {esperado}"
    return traj, res["previsto"]


# 2. Origens do cenário: o início da sequência em que os seis métodos projetam em todos os trimestres seguintes
previsto4 = {}
for k in range(primeiro_ativo + 1, K_ULTIMA_4 + 1):
    previsto4[k] = roda_origem(k, 4)[1]
definida = {
    k: all(not np.isnan(previsto4[k][CHAVE_PREVISTO[m]]) for m in METODOS) for k in previsto4
}
sem_definir = [k for k, ok in definida.items() if not ok]
K_INICIO = max(sem_definir) + 1 if sem_definir else min(previsto4)

# 2a. As previsões de 4 passos reproduzem as do S4k
if UNIDADES_S4K is not None:
    partes = [
        pd.read_csv(UNIDADES_S4K / f"clojure_S4k{sufixo}_pares.csv.gz")
        for sufixo in ("", "_R1", "_R2", "_R3")
    ]
    s4k = (
        pd.concat(partes, ignore_index=True)
        .drop_duplicates(["k", "metodo"])
        .set_index(["k", "metodo"])["previsto"]
    )
    comparadas, diferentes = 0, []
    for k in previsto4:
        for metodo in METODOS:
            if (k, NOME_NOS_PARES[metodo]) not in s4k.index:
                continue
            a, b = previsto4[k][CHAVE_PREVISTO[metodo]], float(s4k.loc[(k, NOME_NOS_PARES[metodo])])
            comparadas += 1
            if not ((np.isnan(a) and np.isnan(b)) or abs(a - b) <= 1e-8 * max(1.0, abs(b))):
                diferentes.append((str(datas[k].date()), metodo, a, b))
    if comparadas == 0 or diferentes:
        sys.exit(
            f"as previsões de 1 ano não reproduzem o S4k: {len(diferentes)} diferentes de {comparadas}, por exemplo {diferentes[:3]}"
        )
    conferencia_s4k = f"{comparadas} previsões de 1 ano (seis métodos, todas as origens até 31/12/2023) comparadas com as do S4k, 0 diferentes."
else:
    conferencia_s4k = "não conferido (sem pasta do S4k)."

# 3. Trajetórias de 20 passos: origens históricas (com alvo conhecido) e a origem final
trajetorias = {}
for k in [*range(K_INICIO, K_ULTIMA_4 + 1), K0]:
    trajetorias[k] = roda_origem(k, PASSOS)[0]
for k in range(K_INICIO, K_ULTIMA_4 + 1):  # H3: os 4 primeiros passos são a projeção de 4
    for metodo in METODOS:
        a = float(np.sum(trajetorias[k][metodo][NB - 1]))
        b = previsto4[k][CHAVE_PREVISTO[metodo]]
        assert abs(a - b) <= 1e-8 * max(1.0, abs(b)), (
            f"os 4 primeiros passos de 20 diferem dos 4 passos: {metodo} {datas[k].date()}: {a} contra {b}"
        )

# 4. Erro por origem e passo
linhas = []
for k in range(K_INICIO, K_ULTIMA_4 + 1):
    for metodo in METODOS:
        for s in range(1, PASSOS + 1):
            if k + s > K_2024:
                break
            p, r = float(np.sum(trajetorias[k][metodo][s - 1])), float(ativas[k + s])
            linhas.append(
                {
                    "metodo": metodo,
                    "origem": str(datas[k].date()),
                    "passo": s,
                    "alvo": str(datas[k + s].date()),
                    "previsto": p,
                    "real": r,
                    "erro_com_sinal": (p - r) / r,
                    "real_sobre_previsto_menos_1": (r - p) / p,
                }
            )
erros = pd.DataFrame(linhas)
erros.to_csv(SAIDA / "erro_por_origem_e_passo.csv", index=False, float_format="%.10g")
resumo = []
for (metodo, passo), g in erros.groupby(["metodo", "passo"]):
    e1, e2 = g["erro_com_sinal"].to_numpy(), g["real_sobre_previsto_menos_1"].to_numpy()
    resumo.append(
        {
            "metodo": metodo,
            "passo": passo,
            "horizonte_anos": passo / NB,
            "origens": len(g),
            "primeira_origem": g["origem"].min(),
            "ultima_origem": g["origem"].max(),
            "media": e1.mean(),
            "mediana": float(np.median(e1)),
            "p10": float(np.percentile(e1, 10)),
            "p90": float(np.percentile(e1, 90)),
            "real_sobre_previsto_media": e2.mean(),
            "real_sobre_previsto_mediana": float(np.median(e2)),
            "real_sobre_previsto_p10": float(np.percentile(e2, 10)),
            "real_sobre_previsto_p90": float(np.percentile(e2, 90)),
        }
    )
por_passo = pd.DataFrame(resumo)
por_passo.to_csv(SAIDA / "erro_por_passo.csv", index=False, float_format="%.10g")
H = [
    "# Erro histórico por horizonte (Clojure, Longo, não casuais)",
    "",
    f"Origens: todo fim de trimestre de {datas[K_INICIO].date()} (início da sequência em que os seis métodos projetam em todos os trimestres seguintes) até 31/12/2024 menos o horizonte, com o alvo já conhecido (até 31/12/2024). Percentis pelo método linear do numpy.",
    "",
    "Erro com sinal = (previsto − real) / real, em %; positivo é superestimar. Faixa de incerteza: previsão × (1 + p10) a previsão × (1 + p90), com p10 e p90 do erro **(real − previsto) / previsto**, que são as colunas da direita; com o erro na convenção (previsto − real) / real a mesma fórmula daria a faixa espelhada.",
    "",
    "| Método | Horizonte (anos) | Origens | Erro com sinal: média (%) | mediana (%) | p10 (%) | p90 (%) | (real − previsto)/previsto: p10 (%) | p90 (%) | Aviso |",
    "|---|---|---|---|---|---|---|---|---|---|",
]
for metodo in METODOS:
    for h in range(1, 6):
        x = por_passo[(por_passo["metodo"] == metodo) & (por_passo["passo"] == NB * h)].iloc[0]
        aviso = "menos de 10 origens" if x["origens"] < 10 else ""
        H.append(
            f"| {metodo} | {h} | {x['origens']} | {dec(100 * x['media'])} | {dec(100 * x['mediana'])} | {dec(100 * x['p10'])} | {dec(100 * x['p90'])} | {dec(100 * x['real_sobre_previsto_p10'])} | {dec(100 * x['real_sobre_previsto_p90'])} | {aviso} |"
        )
H.append("")
(SAIDA / "erro_por_horizonte.md").write_text("\n".join(H) + "\n", encoding="utf-8")

# 5. Pirâmides projetadas e população
trajetoria_final = trajetorias[K0]
linhas = []
for metodo in METODOS:
    linhas.append(
        {
            "metodo": metodo,
            "passo": 0,
            "data": str(datas[K0].date()),
            "total": float(ativas[K0]),
            **dict(
                zip(FAIXAS6, soma_em_faixas6(junta_aberta(est["pop_p_b"][K0]), NB), strict=True)
            ),
        }
    )
    for s in range(1, PASSOS + 1):
        v = trajetoria_final[metodo][s - 1]
        data = (datas[K0] + pd.offsets.QuarterEnd(s)).date()
        linhas.append(
            {
                "metodo": metodo,
                "passo": s,
                "data": str(data),
                "total": float(np.sum(v)),
                **dict(zip(FAIXAS6, soma_em_faixas6(v, NB), strict=True)),
            }
        )
pd.DataFrame(linhas).to_csv(SAIDA / "trajetorias.csv", index=False, float_format="%.10g")
# pirâmides observadas na origem e nos fins de ano
observadas = []
for ano in range(2009, 2026):
    k = int(np.where(datas == pd.Timestamp(f"{ano}-12-31"))[0][0])
    v = junta_aberta(est["pop_p_b"][k])
    observadas.append(
        {
            "ano": ano,
            "ativos": float(v.sum()),
            **dict(zip(FAIXAS6, soma_em_faixas6(v, NB), strict=True)),
        }
    )
pd.DataFrame(observadas).to_csv(
    SAIDA / "observadas_fim_de_ano.csv", index=False, float_format="%.10g"
)


def faixa(metodo: str, passo: int) -> tuple[float, float, float]:
    """Previsão e faixa de incerteza (previsão × (1 + p10) a previsão × (1 + p90)) no passo."""
    p = float(np.sum(trajetoria_final[metodo][passo - 1]))
    x = por_passo[(por_passo["metodo"] == metodo) & (por_passo["passo"] == passo)]
    if x.empty:
        return p, float("nan"), float("nan")
    x = x.iloc[0]
    return p, p * (1 + x["real_sobre_previsto_p10"]), p * (1 + x["real_sobre_previsto_p90"])


# 6. Série anual (Figura B): entrada = novatos do ano; saída líquida = ativos + novatos do ano seguinte − ativos do ano seguinte
ANOS_OBS = range(2009, 2026)
ANOS_PROJ = range(2026, 2031)  # 31/12/2030 é o último fim de ano dentro dos 20 passos


def passos_ate_fim_de_ano(ano: int) -> int:
    """Trimestres da origem até 31/12 de `ano` (2 para 30/06/2026 e 31/12/2026, 4 para 31/12/2025 e 31/12/2026)."""
    return ((ano * 12 + 12) - (ORIGEM.year * 12 + ORIGEM.month)) // 3


serie = []
for metodo in METODOS:
    pontos = {}
    for ano in ANOS_OBS:
        o = observadas[ano - 2009]
        pontos[ano] = {
            "parte": "observada",
            "ativos": o["ativos"],
            "baixo": o["ativos"],
            "alto": o["ativos"],
            "novatos": o["0-1"],
        }
    for ano in ANOS_PROJ:
        passo = passos_ate_fim_de_ano(ano)
        p, baixo, alto = faixa(metodo, passo)
        v = trajetoria_final[metodo][passo - 1]
        pontos[ano] = {
            "parte": "projetada",
            "ativos": p,
            "baixo": baixo,
            "alto": alto,
            "novatos": float(soma_em_faixas6(v, NB)[0]),
        }
    for ano in [*ANOS_OBS, *ANOS_PROJ]:
        x = pontos[ano]
        seguinte = pontos.get(ano + 1)
        saida_pct = (
            float("nan")
            if seguinte is None
            else 100 * (x["ativos"] + seguinte["novatos"] - seguinte["ativos"]) / x["ativos"]
        )
        parte_saida = (
            ""
            if seguinte is None
            else (
                "observada"
                if x["parte"] == "observada" and seguinte["parte"] == "observada"
                else "projetada"
            )
        )
        serie.append(
            {
                "metodo": metodo,
                "ano": ano,
                "parte": x["parte"],
                "ativos": x["ativos"],
                "ativos_baixo": x["baixo"],
                "ativos_alto": x["alto"],
                "novatos": x["novatos"],
                "entrada_pct": 100 * x["novatos"] / x["ativos"],
                "saida_pct": saida_pct,
                "parte_da_saida": parte_saida,
            }
        )
serie = pd.DataFrame(serie)
serie.to_csv(SAIDA / "serie_anual.csv", index=False, float_format="%.10g")

# 7. Tabela da população projetada
P = [
    "# População projetada de Clojure (Longo, não casuais), com a faixa de incerteza",
    "",
    f"Origem {ORIGEM.date()}; população da RQ3 (não casuais classificados só com o passado). Faixa de incerteza: previsão × (1 + p10) a previsão × (1 + p90), com p10 e p90 do erro (real − previsto) / previsto do horizonte (`erro_por_horizonte.md`). Observado na origem: {milhar(ativas[K0])} pessoas.",
    "",
    "## Horizontes de 1 a 5 anos a partir da origem",
    "",
    "| Método | "
    + " | ".join(f"{(ORIGEM + pd.offsets.QuarterEnd(4 * h)).date()} (+{h})" for h in range(1, 6))
    + " |",
    "|---|" + "---|" * 5,
]
tabela = []
for metodo in METODOS:
    celulas = []
    for h in range(1, 6):
        p, baixo, alto = faixa(metodo, NB * h)
        celulas.append(f"{milhar(p)} ({milhar(baixo)} a {milhar(alto)})")
        tabela.append(
            {
                "metodo": metodo,
                "tipo": "horizonte",
                "rotulo": f"+{h} anos",
                "data": str((ORIGEM + pd.offsets.QuarterEnd(NB * h)).date()),
                "passo": NB * h,
                "projecao": p,
                "baixo": baixo,
                "alto": alto,
            }
        )
    P.append(f"| {metodo} | " + " | ".join(celulas) + " |")
P += [
    "",
    "## Fins de ano (as barras da Figura B)",
    "",
    "| Método | " + " | ".join(str(a) for a in ANOS_PROJ) + " |",
    "|---|" + "---|" * len(ANOS_PROJ),
]
for metodo in METODOS:
    celulas = []
    for ano in ANOS_PROJ:
        passo = passos_ate_fim_de_ano(ano)
        p, baixo, alto = faixa(metodo, passo)
        celulas.append(f"{milhar(p)} ({milhar(baixo)} a {milhar(alto)})")
        tabela.append(
            {
                "metodo": metodo,
                "tipo": "fim_de_ano",
                "rotulo": str(ano),
                "data": f"{ano}-12-31",
                "passo": passo,
                "projecao": p,
                "baixo": baixo,
                "alto": alto,
            }
        )
    P.append(f"| {metodo} | " + " | ".join(celulas) + " |")
P.append("")
(SAIDA / "populacao_projetada.md").write_text("\n".join(P) + "\n", encoding="utf-8")
pd.DataFrame(tabela).to_csv(SAIDA / "populacao_projetada.csv", index=False, float_format="%.10g")

# 8. Teste de vazamento: origens de amostra (alvo de 1 ano) e a origem final
candidatas_teste = np.arange(K_INICIO, K_ULTIMA_4 + 1)
amostra = [
    int(candidatas_teste[p])
    for p in np.unique(np.round(np.linspace(0.1, 0.9, 5) * (len(candidatas_teste) - 1)).astype(int))
]
v = vazamento.testa(
    pessoas,
    eventos,
    3,
    "P1",
    est,
    hist,
    amostra,
    regras,
    POOL,
    ("B",),
    NB,
    OPCOES_ESTADO,
    {"ieice": False},
)
ok_amostra = (
    bool(v["estados_iguais"].all())
    and bool((v["maior_diferenca_relativa"] < 1e-9).all())
    and bool(v["controle_eventos_futuros_difere"].any())
    and bool(v["controle_promocoes_difere"].any())
)
t = np.datetime64(ORIGEM)
so_ate_t = {nome: x[eventos["dia"] <= t] for nome, x in eventos.items()}
estado_t = constroi_estado(pessoas, so_ate_t, 3, "P1", t, **OPCOES_ESTADO)
iguais_final = all(
    np.allclose(est[nome], estado_t[nome], rtol=1e-12, atol=1e-12, equal_nan=True)
    for nome in vazamento.SERIES_NO_TEMPO + vazamento.SERIES_DA_PARADA
)
previsao.DETALHE = None
p_tudo = preve_estado(est, hist, regras, POOL, ("B",), PASSOS, False)["previsto"]
p_t = preve_estado(estado_t, hist, regras, POOL, ("B",), PASSOS, False)["previsto"]
diferenca_final = vazamento.maior_diferenca(p_tudo, p_t)
comprimido = {nome: x.copy() for nome, x in eventos.items()}
comprimido["dia"] = np.minimum(comprimido["dia"], t)
p_futuro = preve_estado(
    constroi_estado(pessoas, comprimido, 3, "P1", t, **OPCOES_ESTADO),
    hist,
    regras,
    POOL,
    ("B",),
    PASSOS,
    False,
)["previsto"]
futuros_difere = vazamento.maior_diferenca(p_tudo, p_futuro) > 1e-9
promovidos = pessoas.copy()
segunda = promovidos["segunda"].to_numpy().astype("datetime64[D]")
futura = ~np.isnat(segunda) & (segunda > t)
segunda[futura] = vazamento.datas_primeira(3)
promovidos["segunda"] = segunda
p_prom = preve_estado(
    constroi_estado(promovidos, eventos, 3, "P1", t, **OPCOES_ESTADO),
    hist,
    regras,
    POOL,
    ("B",),
    PASSOS,
    False,
)["previsto"]
promocoes_difere = vazamento.maior_diferenca(p_tudo, p_prom) > 1e-9
V = [
    "# Teste de vazamento",
    "",
    f"- Origens de amostra (alvo de 1 ano): {', '.join(str(datas[k].date()) for k in amostra)}. Estados iguais: {bool(v['estados_iguais'].all())}; maior diferença relativa das previsões: {v['maior_diferenca_relativa'].max():.2e}; controle com eventos futuros difere em {int(v['controle_eventos_futuros_difere'].sum())} de {len(v)}; controle com promoções difere em {int(v['controle_promocoes_difere'].sum())} de {len(v)}.",
    f"- Origem final ({ORIGEM.date()}, 20 passos): estado só com eventos até a origem igual ao do cálculo completo: {iguais_final}; maior diferença relativa das previsões: {diferenca_final:.2e}; controle com eventos de {(ORIGEM + pd.Timedelta(days=1)).date()} a {fim_dados.date()} entrando na origem difere: {bool(futuros_difere)}; controle com promoções de residência depois da origem difere: {bool(promocoes_difere)}.",
    f"- {conferencia_s4k}",
    "- Os 4 primeiros passos da projeção de 20 são a projeção de 4 em todas as origens históricas e nos seis métodos (conferido).",
    "",
]
(SAIDA / "vazamento.md").write_text("\n".join(V) + "\n", encoding="utf-8")
if not (
    ok_amostra and iguais_final and diferenca_final < 1e-9 and futuros_difere and promocoes_difere
):
    sys.exit("o teste de vazamento falhou; ver vazamento.md")
print(f"origem {ORIGEM.date()}; início da sequência {datas[K_INICIO].date()}; K_2024={K_2024}")
print("\n".join(V))
print("\n".join(H[:14]))
print("\n".join(P[:14]))
