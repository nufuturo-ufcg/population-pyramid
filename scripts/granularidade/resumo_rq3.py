"""Resumo da projecao-rq3: S1 com a coorte do IEICE16 (parte 1) e S2 com o Wilcoxon (parte 2). Ver `hipoteses.md`.

Lê `<saida>/unidades/` e `<saida>/diagnostico_origens_s2.txt`. Grava `pares.csv`, `testes.csv`, `tabelas.md` e `resumo.md` em `<saida>`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/resumo_rq3.py <saida>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from util_resumo import holm, num, pvalor

SAIDA = Path(sys.argv[1])
UNIDADES = SAIDA / "unidades"
LINGUAS = ["clojure", "elixir", "ocaml", "python"]
TODAS = [*LINGUAS, "zig"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "ocaml": "OCaml",
    "python": "Python",
    "zig": "Zig",
}
COMMIT = (SAIDA / "commit.txt").read_text(encoding="utf-8").strip()

ROTULO = {
    "ingenua": "Ingênua",
    "coorte_R0": "Coorte pura (V0, R0)",
    "coorte_R3": "Coorte em R3",
    "C3_R3": "C3 em R3",
    "conservador_R3": "Conservador em R3",
    "conservador_R0": "Conservador em R0",
}
PARTE1 = ["ingenua"]
for base, nome in [
    ("coorte_IEICE", "Coorte IEICE16"),
    ("conservador_IEICE", "Conservador IEICE16"),
    ("C3_IEICE", "C3 IEICE16"),
]:
    for r in range(4):
        PARTE1.append(f"{base}_R{r}")
        ROTULO[f"{base}_R{r}"] = f"{nome} em R{r}"
PARTE2 = ["ingenua", "coorte_R0", "coorte_R3", "C3_R3", "conservador_R3", "conservador_R0"]


def carrega(lingua: str, cenario: str) -> pd.DataFrame:
    partes = [pd.read_csv(UNIDADES / f"{lingua}_{cenario}_pares.csv.gz")]
    for r in (1, 2, 3):
        partes.append(pd.read_csv(UNIDADES / f"{lingua}_{cenario}_R{r}_pares.csv.gz"))
    return pd.concat(partes, ignore_index=True)


def teste_wilcoxon(a: np.ndarray, b: np.ndarray) -> tuple[float, float, int]:
    """Estatística, p exato e número de pares com diferença (zero fica de fora)."""
    diferenca = a - b
    n = int((diferenca != 0).sum())
    if n < 1:
        return np.nan, np.nan, 0
    r = wilcoxon(a, b, method="exact")
    return float(r.statistic), float(r.pvalue), n


def menor_p(n: int) -> float:
    return np.nan if n < 1 else 2.0 / 2.0**n


def num4(x: float) -> str:
    return num(x, 4)


def estatisticas(s: pd.Series) -> list[float]:
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    return [s.mean(), s.median(), s.std(ddof=1), q3 - q1, s.max()]


def alvo_do_pior(origens: pd.Series, s: pd.Series, meses: int) -> str:
    origem = pd.Timestamp(origens.loc[s.idxmax()])
    alvo = origem + pd.DateOffset(months=meses)
    return alvo.strftime("%Y") if meses == 12 else alvo.strftime("%Y-%m")


def analisa(cenario: str, metodos: list[str], meses: int, contra_r0: bool) -> dict:
    """Por linguagem: base comum de pares, medidas, Wilcoxon contra a ingênua (com Holm) e, na parte 1, de cada R contra o R0."""
    saida = {}
    for lingua in TODAS:
        t = carrega(lingua, cenario)
        abre = t.pivot(index="k", columns="metodo", values="abre").reindex(columns=metodos)
        origem = t[t["metodo"] == "ingenua"].set_index("k")["origem"]
        sozinhos = abre.notna().sum()
        base = abre.notna().all(axis=1)
        d = abre[base]
        linhas = []
        p_brutos = []
        for m in metodos:
            est = estatisticas(d[m]) if len(d) > 1 else [np.nan] * 5
            pior = alvo_do_pior(origem, d[m], meses) if len(d) else "n/d"
            if m == "ingenua" or len(d) < 2:
                estat, p, n = np.nan, np.nan, 0
            else:
                estat, p, n = teste_wilcoxon(d[m].to_numpy(), d["ingenua"].to_numpy())
            linhas.append({"linguagem": lingua, "cenario": cenario, "metodo": m, "pares": len(d), "pares_sozinho": int(sozinhos[m]),
                           "media": est[0], "mediana": est[1], "desvio": est[2], "iiq": est[3], "maximo": est[4], "pior_alvo": pior,
                           "estatistica": estat, "p_exato": p, "pares_com_diferenca": n, "menor_p": menor_p(n)})  # fmt: skip
            p_brutos.append(p)
        ajustado = holm(np.array(p_brutos, dtype=float))
        for i, linha in enumerate(linhas):
            linha["p_holm"] = ajustado[i]
        extras = []
        if contra_r0 and len(d) > 1:
            familias = ["coorte_IEICE", "conservador_IEICE", "C3_IEICE"]
            brutos = []
            for base_nome in familias:
                for r in (1, 2, 3):
                    estat, p, n = teste_wilcoxon(
                        d[f"{base_nome}_R{r}"].to_numpy(), d[f"{base_nome}_R0"].to_numpy()
                    )
                    extras.append({"linguagem": lingua, "metodo": base_nome, "r": f"R{r} contra R0", "pares": len(d), "estatistica": estat,
                                   "p_exato": p, "pares_com_diferenca": n, "menor_p": menor_p(n)})  # fmt: skip
                    brutos.append(p)
            ajustado = holm(np.array(brutos, dtype=float))
            for i, e in enumerate(extras):
                e["p_holm"] = ajustado[i]
        saida[lingua] = {
            "linhas": linhas,
            "extras": extras,
            "origens": origem[base.index[base]],
            "abre": d,
        }
    return saida


def celula_pares(linha: dict) -> str:
    if linha["pares_com_diferenca"] and linha["pares_com_diferenca"] != linha["pares"]:
        return f"{linha['pares']} ({linha['pares_com_diferenca']})"
    return str(linha["pares"])


def tabela_da_linguagem(lingua: str, bloco: dict, titulo: str) -> list[str]:
    linhas = bloco["linhas"]
    n = linhas[0]["pares"]
    saida = [f"### {titulo}, {NOMES[lingua]} ({n} pares)", ""]
    if n < 2:
        saida += [
            "Sem par suficiente na base (menos de 2 origens em que todos os métodos têm ABRE definido).",
            "",
        ]
        return saida
    saida.append(
        "| Método | Pares sozinho | Média | Mediana | Desvio padrão | IIQ | Máximo (alvo) | Estatística | p exato | Menor p | p Holm |"
    )
    saida.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for linha in linhas:
        teste = linha["metodo"] != "ingenua"
        saida.append(
            f"| {ROTULO[linha['metodo']]} | {linha['pares_sozinho']} | {num4(linha['media'])} | {num4(linha['mediana'])} | {num4(linha['desvio'])} | {num4(linha['iiq'])} | {num4(linha['maximo'])} ({linha['pior_alvo']}) "
            f"| {num(linha['estatistica'], 1) if teste else '-'} | {pvalor(linha['p_exato']) if teste else '-'} | {pvalor(linha['menor_p']) if teste else '-'} | {pvalor(linha['p_holm']) if teste else '-'} |"
        )
    saida.append("")
    return saida


def linha_da_linguagem(lingua: str, bloco: dict) -> str:
    linhas = [x for x in bloco["linhas"] if not np.isnan(x["media"])]
    if not linhas:
        return f"- {NOMES[lingua]}: sem par na base."
    melhor_media = min(linhas, key=lambda x: x["media"])
    melhor_mediana = min(linhas, key=lambda x: x["mediana"])
    return (
        f"- {NOMES[lingua]}: menor média {ROTULO[melhor_media['metodo']]} ({num4(melhor_media['media'])}); "
        f"menor mediana {ROTULO[melhor_mediana['metodo']]} ({num4(melhor_mediana['mediana'])})."
    )


def tabela_r_contra_r0(lingua: str, bloco: dict) -> list[str]:
    if not bloco["extras"]:
        return []
    saida = [f"### Parte 1, {NOMES[lingua]}: cada R contra o R0 do mesmo método", "",
             "| Método | Comparação | Pares | Estatística | p exato | Menor p | p Holm |", "|---|---|---:|---:|---:|---:|---:|"]  # fmt: skip
    for e in bloco["extras"]:
        nome = {
            "coorte_IEICE": "Coorte IEICE16",
            "conservador_IEICE": "Conservador IEICE16",
            "C3_IEICE": "C3 IEICE16",
        }[e["metodo"]]
        pares = (
            str(e["pares"])
            if e["pares_com_diferenca"] == e["pares"]
            else f"{e['pares']} ({e['pares_com_diferenca']})"
        )
        saida.append(f"| {nome} | {e['r']} | {pares} | {num(e['estatistica'], 1)} | {pvalor(e['p_exato'])} | {pvalor(e['menor_p'])} | {pvalor(e['p_holm'])} |")  # fmt: skip
    saida.append("")
    return saida


def tabela_origens_s2() -> list[str]:
    """Parte 2a: primeira e última origem de cada linguagem, e a faixa sem taxa na origem anterior à primeira."""
    texto = (SAIDA / "diagnostico_origens_s2.txt").read_text(encoding="utf-8").splitlines()
    por_lingua, atual = {}, None
    for linha in texto:
        if linha.startswith("== "):
            atual = linha[3:].split(":")[0]
            por_lingua[atual] = []
        elif linha.strip().startswith("origem "):
            por_lingua[atual].append(linha.strip())
    saida = ["| Linguagem | Primeiro recorte com ativos | Origens da ingênua | Origens dos 6 métodos | Primeira origem com todas as faixas com taxa | Faixa sem taxa na origem anterior |", "|---|---|---|---|---|---|"]  # fmt: skip
    for lingua in TODAS:
        t = carrega(lingua, "S2")
        p = t.pivot(index="origem", columns="metodo", values="previsto")
        ing = p["ingenua"].dropna().index
        seis = p[PARTE2].notna().all(axis=1)
        seis = seis[seis].index
        primeiro_ativo = ing[0]
        ano_primeiro = str(int(primeiro_ativo[:4]) - 1) + "-12-31"
        origens = por_lingua[lingua]
        primeira_livre, bloqueio_anterior = "nenhuma até 2024", "-"
        anterior = None
        for o in origens:
            data = o.split(":")[0].replace("origem ", "")
            trecho = o.split("sem taxa (coorte) ")[1].split("]")[0] + "]"
            if trecho == "[]":
                primeira_livre = data
                bloqueio_anterior = anterior or "-"
                break
            anterior = trecho
        else:
            bloqueio_anterior = anterior or "-"
        intervalo_ing = f"{ing[0]} a {ing[-1]} ({len(ing)})"
        intervalo_seis = f"{seis[0]} a {seis[-1]} ({len(seis)})" if len(seis) else "nenhuma (0)"
        saida.append(
            f"| {NOMES[lingua]} | {ano_primeiro} | {intervalo_ing} | {intervalo_seis} | {primeira_livre} | {bloqueio_anterior} |"
        )
    saida.append("")
    return saida


def resumo_vazamento() -> list[str]:
    saida = ["| Unidade | Origens testadas | Estados iguais | Maior diferença | Controle de eventos futuros difere | Controle de promoções difere |", "|---|---:|---|---:|---:|---:|"]  # fmt: skip
    for cenario in ["S1", "S2"]:
        for lingua in TODAS:
            v = pd.read_csv(UNIDADES / f"{lingua}_{cenario}_vazamento.csv")
            promocoes = (
                f"{int(v['controle_promocoes_difere'].sum())} de {len(v)}"
                if "controle_promocoes_difere" in v
                else "n/a (P2)"
            )
            saida.append(f"| {lingua} {cenario} | {len(v)} | {'sim' if bool(v['estados_iguais'].all()) else 'NÃO'} | {v['maior_diferenca_relativa'].max():.1e} | {int(v['controle_eventos_futuros_difere'].sum())} de {len(v)} | {promocoes} |")  # fmt: skip
    saida.append("")
    return saida


p1 = analisa("S1", PARTE1, 3, True)
p2 = analisa("S2", PARTE2, 12, False)

todas = []
testes = []
for cenario, bloco in [("S1", p1), ("S2", p2)]:
    for lingua in TODAS:
        todas.extend(bloco[lingua]["linhas"])
        for e in bloco[lingua]["extras"]:
            testes.append({"cenario": cenario, **e})
pd.DataFrame(todas).to_csv(SAIDA / "pares.csv", index=False, float_format="%.10g")
pd.DataFrame(testes).to_csv(SAIDA / "testes.csv", index=False, float_format="%.10g")

T = [
    "# Tabelas da projecao-rq3",
    "",
    "ABRE = |previsto - real| / min(previsto, real). Desvio padrão com divisor n - 1. Quartis por interpolação linear. IIQ = Q3 menos Q1. Máximo com o alvo do pior caso (trimestre em S1, ano em S2). "
    "Wilcoxon pareado bicaudal exato contra a ingênua, com Holm dentro de cada linguagem. Menor p = 2 sobre 2 elevado ao número de pares com diferença. "
    "Pares entre parênteses: quando há pares sem diferença, o teste usa só os que diferem. Pares sozinho: origens em que o método tem ABRE definido sem exigir os outros.",
    "",
]
T += [
    "## Parte 1: S1 com a coorte do IEICE16",
    "",
    "Base: origens em que os 13 métodos têm ABRE definido. Com os novatos da V2 (R1 e R3) a coorte e o conservador do IEICE16 coincidem com os da V2.",
    "",
]
for lingua in TODAS:
    T += tabela_da_linguagem(lingua, p1[lingua], "S1")
for lingua in LINGUAS:
    T += tabela_r_contra_r0(lingua, p1[lingua])
T += [
    "## Parte 2: S2 (nossa pirâmide, origens de dezembro)",
    "",
    "Base: origens em que os 6 métodos têm ABRE definido. A coorte pura é a coorte V0 (R0) e o conservador em R0 é o conservador V0.",
    "",
]
for lingua in TODAS:
    T += tabela_da_linguagem(lingua, p2[lingua], "S2")
(SAIDA / "tabelas.md").write_text("\n".join(T), encoding="utf-8")

R = [
    "# projecao-rq3",
    "",
    f"Commit do código: `{COMMIT}`. Protocolo em `hipoteses.md`. Tabelas completas em `tabelas.md` (por linguagem), números em `pares.csv` e `testes.csv`.",
    "",
    "## Vazamento",
    "",
    "Mesma função protegida e mesmo teste das pastas de cenários: estado cortado em t, asserts de série sem dado depois da origem e alvo calculado fora da função de previsão. O teste só vale onde o controle difere.",
    "",
]
R += resumo_vazamento()
R += ["## Parte 1: menor média e menor mediana por linguagem (S1, 13 métodos)", ""]
for lingua in LINGUAS:
    R.append(linha_da_linguagem(lingua, p1[lingua]))
R += [
    "",
    "## Parte 2a: por que o S2 tem tão poucas origens",
    "",
    "Origens de dezembro. A origem que abre a série é a primeira em que toda faixa com gente tem taxa de permanência. Detalhe por origem em `diagnostico_origens_s2.txt`.",
    "",
]
R += tabela_origens_s2()
R += ["## Parte 2c: menor média e menor mediana por linguagem (S2, 6 métodos)", ""]
for lingua in LINGUAS:
    R.append(linha_da_linguagem(lingua, p2[lingua]))
R.append("")
(SAIDA / "resumo.md").write_text("\n".join(R), encoding="utf-8")
print("\n".join(R))
