"""Resumo da cobertura v2 do S2 (RQ3.3): regra antiga e regra nova do pessimista e do otimista de R1 e R3 lado a lado. Ver `hipoteses.md`.

Lê `<saida>/unidades/` (S2 com `pessimista_R0..R3`, `otimista_R0..R3` e `pessimista_nova_R1/R3`, `otimista_nova_R1/R3`) e `<saida>/diagnostico_otimista.csv`.
Confere que as previsões de `projecao-rq3/unidades/` e de `projecao-rq3/cobertura/unidades/` saem iguais, e R0 e R1 antigos contra `intervalos.csv` da granularidade; para se algo diferir.
Grava `por_origem.csv`, `tabelas.md` e `resumo.md` em `<saida>`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/resumo_cobertura_v2.py <saida> <projecao-rq3> <cobertura> <projecao-granularidade>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from util_resumo import num

SAIDA = Path(sys.argv[1])
RQ3 = Path(sys.argv[2])
COBERTURA = Path(sys.argv[3])
GRAN = Path(sys.argv[4])
UNIDADES = SAIDA / "unidades"
LINGUAS = ["clojure", "elixir", "ocaml", "python"]
NOMES = {"clojure": "Clojure", "elixir": "Elixir", "ocaml": "OCaml", "python": "Python"}
COMMIT = (SAIDA / "commit.txt").read_text(encoding="utf-8").strip()
PARTE2 = ["ingenua", "coorte_R0", "coorte_R3", "C3_R3", "conservador_R3", "conservador_R0"]
# (rótulo, nome do pessimista, nome do otimista)
INTERVALOS = [
    ("R0", "pessimista_R0", "otimista_R0"),
    ("R1 regra antiga", "pessimista_R1", "otimista_R1"),
    ("R1 regra nova", "pessimista_nova_R1", "otimista_nova_R1"),
    ("R2", "pessimista_R2", "otimista_R2"),
    ("R3 regra antiga", "pessimista_R3", "otimista_R3"),
    ("R3 regra nova", "pessimista_nova_R3", "otimista_nova_R3"),
]
# pontos: (rótulo, método, R do intervalo)
PONTOS = [
    ("Coorte R0", "coorte_R0", "R0"),
    ("Coorte^R (R3)", "coorte_R3", "R3"),
    ("Conservador^R (R3)", "conservador_R3", "R3"),
]


def carrega(pasta: Path, lingua: str) -> pd.DataFrame:
    partes = [pd.read_csv(pasta / "unidades" / f"{lingua}_S2_pares.csv.gz")]
    for r in (1, 2, 3):
        partes.append(pd.read_csv(pasta / "unidades" / f"{lingua}_S2_R{r}_pares.csv.gz"))
    return pd.concat(partes, ignore_index=True)


def posicao(valor: float, pess: float, otim: float) -> str:
    if np.isnan(valor) or np.isnan(pess) or np.isnan(otim):
        return "indefinido"
    if valor < pess:
        return "abaixo"
    if valor > otim:
        return "acima"
    return "dentro"


def inteiro(x: float) -> str:
    return "n/d" if pd.isna(x) else f"{x:.0f}"


def pct(x: float) -> str:
    return f"{100 * x:.1f}".replace(".", ",") + "%"


def compara_previsoes(novo: pd.DataFrame, velho: pd.DataFrame) -> tuple[int, int]:
    """Quantas previsões em comum e quantas diferem (tolerância relativa de 1e-9)."""
    comparados, diferentes = 0, 0
    for m in velho.columns:
        if m not in novo.columns:
            continue
        for k in velho.index:
            a, b = velho.loc[k, m], novo.loc[k, m]
            comparados += 1
            if np.isnan(a) and np.isnan(b):
                continue
            if np.isnan(a) != np.isnan(b) or abs(a - b) > 1e-9 * max(1.0, abs(a)):
                diferentes += 1
    return comparados, diferentes


linhas = []
conferencia = []
vazamento = []
origens_usadas = {}
for lingua in LINGUAS:
    nova = carrega(SAIDA, lingua)
    previsto = nova.pivot(index="k", columns="metodo", values="previsto")
    abre = nova.pivot(index="k", columns="metodo", values="abre")
    origem = nova[nova["metodo"] == "ingenua"].set_index("k")["origem"]
    real = nova[nova["metodo"] == "ingenua"].set_index("k")["real"]

    # 1. nada do que existia mudou
    for rotulo, pasta in [("projecao-rq3", RQ3), ("projecao-rq3/cobertura", COBERTURA)]:
        velho = carrega(pasta, lingua).pivot(index="k", columns="metodo", values="previsto")
        comparados, diferentes = compara_previsoes(previsto, velho)
        conferencia.append(
            f"- {NOMES[lingua]}: {comparados} previsões de {rotulo} comparadas com esta rodada, {diferentes} diferentes."
        )
        if diferentes:
            sys.exit(f"{lingua}: previsões de {rotulo} mudaram ({diferentes}). Parei.")

    # 2. origens da Parte 2
    base = abre[PARTE2].notna().all(axis=1)
    ks = list(abre.index[base])
    origens_usadas[lingua] = f"{origem[ks[0]]} a {origem[ks[-1]]} ({len(ks)})"

    # 3. intervalos, largura e posição dos pontos
    for rotulo, nome_pess, nome_otim in INTERVALOS:
        r_do_intervalo = rotulo.split()[0]
        for k in ks:
            pess, otim = previsto.loc[k, nome_pess], previsto.loc[k, nome_otim]
            definido = not (np.isnan(pess) or np.isnan(otim))
            linha = {
                "linguagem": lingua,
                "origem": origem[k],
                "intervalo": rotulo,
                "ingenua": previsto.loc[k, "ingenua"],
                "real": real[k],
                "pessimista": pess,
                "otimista": otim,
                "definido": definido,
                "real_dentro": bool(pess <= real[k] <= otim) if definido else False,
                "real_abaixo": bool(real[k] < pess) if definido else False,
                "real_acima": bool(real[k] > otim) if definido else False,
                "largura_relativa": (otim - pess) / previsto.loc[k, "ingenua"]
                if definido
                else np.nan,
            }
            for _rotulo_ponto, metodo, r_ponto in PONTOS:
                if r_ponto == r_do_intervalo:
                    linha[f"{metodo}"] = previsto.loc[k, metodo]
                    linha[f"{metodo}_posicao"] = posicao(previsto.loc[k, metodo], pess, otim)
            linhas.append(linha)

    # 4. a regra nova cerca a antiga e o ponto central (por construção, conferido aqui)
    for r in ("R1", "R3"):
        for k in ks:
            antigo = (previsto.loc[k, f"pessimista_{r}"], previsto.loc[k, f"otimista_{r}"])
            novo = (previsto.loc[k, f"pessimista_nova_{r}"], previsto.loc[k, f"otimista_nova_{r}"])
            if novo[0] > antigo[0] + 1e-6 or novo[1] < antigo[1] - 1e-6:
                sys.exit(f"{lingua} {origem[k]} {r}: o intervalo novo não cerca o antigo. Parei.")

    # 5. vazamento
    v = pd.read_csv(UNIDADES / f"{lingua}_S2_vazamento.csv")
    assert v["estados_iguais"].all() and (v["maior_diferenca_relativa"] < 1e-9).all()
    assert v["controle_eventos_futuros_difere"].any() and v["controle_promocoes_difere"].any()
    vazamento.append(
        f"- {NOMES[lingua]}: {len(v)} origens testadas, estados iguais {bool(v['estados_iguais'].all())}, maior diferença das previsões {v['maior_diferenca_relativa'].max():.1e}, controle de eventos futuros difere em {int(v['controle_eventos_futuros_difere'].sum())} de {len(v)}, controle de promoções difere em {int(v['controle_promocoes_difere'].sum())} de {len(v)}."
    )

tudo = pd.DataFrame(linhas)
tudo.to_csv(SAIDA / "por_origem.csv", index=False, float_format="%.10g")


def mede(lingua: str, rotulo: str) -> tuple[int, int, float, float]:
    d = tudo[(tudo["linguagem"] == lingua) & (tudo["intervalo"] == rotulo) & tudo["definido"]]
    return (
        len(d),
        int(d["real_dentro"].sum()),
        float(d["real_dentro"].mean()),
        float(d["largura_relativa"].median()),
    )


# conferência de R0 e R1 (regra antiga) contra intervalos.csv da granularidade
conf_gran = [
    "- Conferência contra `intervalos.csv` pulada: não há `intervalos.csv` na pasta de granularidade informada."
]
if (GRAN / "intervalos.csv").exists():
    antigos = pd.read_csv(GRAN / "intervalos.csv")
    antigos = antigos[(antigos["populacao"] == "P1") & (antigos["passo_meses"] == 12)]
    conf_gran = ["| Linguagem | Intervalo | Pares | Cobertura (esta rodada) | Cobertura (intervalos.csv) | Largura mediana (esta rodada) | Largura mediana (intervalos.csv) |", "|---|---|---|---|---|---|---|"]  # fmt: skip
    for lingua in LINGUAS:
        for rotulo, variante in [("R0", "V0"), ("R1 regra antiga", "V2")]:
            n, dentro, fracao, largura = mede(lingua, rotulo)
            ref = antigos[
                (antigos["linguagem"] == lingua) & (antigos["variante"] == variante)
            ].iloc[0]
            conf_gran.append(
                f"| {NOMES[lingua]} | {rotulo} contra {variante} | {n} de {int(ref['pares'])} | {dentro} de {n} ({num(fracao, 4)}) | {num(ref['cobertura'], 4)} | {num(largura, 4)} | {num(ref['largura_relativa_mediana'], 4)} |"
            )
            if (
                n != int(ref["pares"])
                or abs(fracao - ref["cobertura"]) > 1e-5
                or abs(largura - ref["largura_relativa_mediana"]) > 1e-5
            ):
                sys.exit(f"{lingua} {rotulo}: não reproduz intervalos.csv. Parei.")

# diagnóstico (causa)
diag = pd.read_csv(SAIDA / "diagnostico_otimista.csv")
diag = diag[(diag["linguagem"] != "elixir") | (diag["origem"] >= "2020-12-31")]

T = [
    "# Tabelas da cobertura v2 do S2",
    "",
    f"Código: commit `{COMMIT}`. Totais de ativos arredondados para inteiro. Regra antiga e regra nova lado a lado em R1 e R3. R0 e R2 não mudam.",
    "",
]
T += ["## Diagnóstico da causa (antes da mudança)", "", "Origens da Parte 2. `E` é o número de repositórios existentes, `R0` o de repositórios novos. Novatos do ponto central (V2) contra os do otimista antigo e o do otimista da regra nova. Total do ponto central e dos otimistas de R3 (Coorte^R e Conservador^R).", ""]  # fmt: skip
T += ["| Linguagem | Origem | E projetado | Máximo de E (5 anos) | R0 projetado | Máximo de R0 (5 anos) | Novatos centrais | Novatos do otimista antigo | Novatos do otimista novo | Coorte^R | Conservador^R | Otimista R3 antigo | Otimista R3 novo |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
for _, x in diag.iterrows():
    T.append(
        f"| {NOMES[x['linguagem']]} | {x['origem']} | {inteiro(x['E_projetado'])} | {inteiro(x['E_max_janela'])} | {inteiro(x['R0_projetado'])} | {inteiro(x['R0_max_janela'])} | {inteiro(x['novatos_central'])} | {inteiro(x['novatos_otimista'])} | {inteiro(x['novatos_otimista_novo'])} | {inteiro(x['coorte_R3'])} | {inteiro(x['conservador_R3'])} | {inteiro(x['otimista_R3'])} | {inteiro(x['otimista_R3_novo'])} |"
    )
T.append("")

L = [
    "# Cobertura v2 do S2: otimista e pessimista coerentes no R1 e no R3 (RQ3.3)",
    "",
    f"Código: commit `{COMMIT}` (regra nova, previsão e teste de vazamento). Protocolo em `hipoteses.md`, escrito antes de rodar. Tabelas em `tabelas.md`, uma linha por origem em `por_origem.csv`.",
    "",
    "## Origens",
    "",
]
for lingua in LINGUAS:
    L.append(f"- {NOMES[lingua]}: {origens_usadas[lingua]}.")
L += [
    "",
    "## Vazamento",
    "",
    *vazamento,
    "",
    "## Conferência",
    "",
    "Previsões que já existiam:",
    "",
    *conferencia,
    "",
]
L += [
    "R0 e R1 (regra antiga) contra `projecao-granularidade/intervalos.csv` (P1, 12 meses, V0 e V2):",
    "",
    *conf_gran,
    "",
]
# diagnóstico em frases: o que mostra a causa
fora = diag[
    (diag["coorte_R3"] > diag["otimista_R3"])
    | (diag["conservador_R3"] > diag["otimista_R3"])
    | (diag["coorte_R3"] < diag["pessimista_R3"])
    | (diag["conservador_R3"] < diag["pessimista_R3"])
]
novato_maior = fora[fora["novatos_central"] > fora["novatos_otimista"]]
dentro_depois = fora[
    (fora["coorte_R3"] <= fora["otimista_R3_novo"])
    & (fora["conservador_R3"] <= fora["otimista_R3_novo"])
    & (fora["coorte_R3"] >= fora["pessimista_R3_novo"])
    & (fora["conservador_R3"] >= fora["pessimista_R3_novo"])
]
e_acima = diag[diag["E_projetado"] > diag["E_max_janela"]]
r0_acima = diag[diag["R0_projetado"] > diag["R0_max_janela"]]
L += ["## Diagnóstico da causa", ""]
L += [
    f"- Origens da Parte 2 com a Coorte^R ou o Conservador^R fora do intervalo antigo de R3: {len(fora)} de {len(diag)} ({', '.join(f'{NOMES[x.linguagem]} {x.origem[:4]}' for x in fora.itertuples())}).",
    f"- Nessas {len(fora)} origens, os novatos do ponto central passam dos novatos do otimista antigo em {len(novato_maior)}.",
    f"- Com o novato trocado pelo da regra nova (e as mesmas taxas), os dois pontos ficam dentro em {len(dentro_depois)} das {len(fora)}.",
    f"- Repositórios existentes projetados acima do máximo dos últimos 5 anos: {len(e_acima)} das {len(diag)} origens. Repositórios novos projetados acima do máximo: {len(r0_acima)}.",
    "- Os valores por origem estão em `tabelas.md` (seção Diagnóstico) e `diagnostico_otimista.csv`.",
    "",
]
L += ["## Cobertura e largura mediana por linguagem", ""]

for lingua in LINGUAS:
    d = tudo[tudo["linguagem"] == lingua]
    ks_ordem = list(dict.fromkeys(d["origem"]))
    T += [
        f"## {NOMES[lingua]}",
        "",
        f"Origens: {origens_usadas[lingua]}.",
        "",
        "### Cobertura por intervalo",
        "",
    ]
    T += ["| Intervalo | Origens | Real dentro | Cobertura | Real abaixo do pessimista | Real acima do otimista | Largura relativa mediana | Largura relativa máxima |", "|---|---|---|---|---|---|---|---|"]  # fmt: skip
    partes_resumo = []
    for rotulo, _, _ in INTERVALOS:
        g = d[d["intervalo"] == rotulo]
        gd = g[g["definido"]]
        n = len(gd)
        dentro = int(gd["real_dentro"].sum())
        T.append(
            f"| {rotulo} | {n} | {dentro} de {n} | {pct(dentro / n) if n else 'n/d'} | {int(gd['real_abaixo'].sum())} | {int(gd['real_acima'].sum())} | {num(gd['largura_relativa'].median(), 4)} | {num(gd['largura_relativa'].max(), 4)} |"
        )
        partes_resumo.append(
            f"{rotulo} {dentro} de {n} ({num(gd['largura_relativa'].median(), 3)})"
        )
    L.append(
        f"- {NOMES[lingua]}: cobertura (largura relativa mediana) em "
        + ", ".join(partes_resumo)
        + "."
    )

    T += ["", "### Pontos centrais dentro do intervalo do mesmo R", "", "| Método | Intervalo | Origens | Dentro | Abaixo do pessimista | Acima do otimista | Dentro em todas as origens |", "|---|---|---|---|---|---|---|"]  # fmt: skip
    for rotulo_ponto, metodo, r_ponto in PONTOS:
        for rotulo, _, _ in INTERVALOS:
            if rotulo.split()[0] != r_ponto:
                continue
            g = d[(d["intervalo"] == rotulo) & d["definido"]]
            pos = g[f"{metodo}_posicao"]
            dentro = int((pos == "dentro").sum())
            T.append(
                f"| {rotulo_ponto} | {rotulo} | {len(g)} | {dentro} | {int((pos == 'abaixo').sum())} | {int((pos == 'acima').sum())} | {'sim' if dentro == len(g) else 'não'} |"
            )
    T.append("")

    for r in ("R0", "R1", "R2", "R3"):
        rotulos = [i[0] for i in INTERVALOS if i[0].split()[0] == r]
        cab = ["Origem"]
        for rotulo in rotulos:
            sufixo = "" if len(rotulos) == 1 else f" ({rotulo.split(' ', 1)[1]})"
            cab += [f"Pessimista{sufixo}", f"Otimista{sufixo}"]
        cab.append("Real")
        for rotulo in rotulos:
            sufixo = "" if len(rotulos) == 1 else f" ({rotulo.split(' ', 1)[1]})"
            cab.append(f"Posição do real{sufixo}")
        for rotulo_ponto, _metodo, r_ponto in PONTOS:
            if r_ponto == r:
                cab.append(rotulo_ponto)
                for rotulo in rotulos:
                    sufixo = "" if len(rotulos) == 1 else f" ({rotulo.split(' ', 1)[1]})"
                    cab.append(f"{rotulo_ponto}: posição{sufixo}")
        T += [
            f"### Intervalo {r}, por origem",
            "",
            "| " + " | ".join(cab) + " |",
            "|" + "---|" * len(cab),
        ]
        for o in ks_ordem:
            celulas = [o]
            linhas_o = {
                rotulo: d[(d["origem"] == o) & (d["intervalo"] == rotulo)].iloc[0]
                for rotulo in rotulos
            }
            primeiro = linhas_o[rotulos[0]]
            for rotulo in rotulos:
                x = linhas_o[rotulo]
                celulas += [inteiro(x["pessimista"]), inteiro(x["otimista"])]
            celulas.append(inteiro(primeiro["real"]))
            for rotulo in rotulos:
                x = linhas_o[rotulo]
                if x["definido"]:
                    celulas.append(
                        "dentro"
                        if x["real_dentro"]
                        else ("abaixo" if x["real_abaixo"] else "acima")
                    )
                else:
                    celulas.append("sem intervalo")
            for _rotulo_ponto, metodo, r_ponto in PONTOS:
                if r_ponto == r:
                    celulas.append(inteiro(primeiro[metodo]))
                    for rotulo in rotulos:
                        celulas.append(linhas_o[rotulo][f"{metodo}_posicao"])
            T.append("| " + " | ".join(celulas) + " |")
        T.append("")

(SAIDA / "tabelas.md").write_text("\n".join(T) + "\n", encoding="utf-8")
(SAIDA / "resumo.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
