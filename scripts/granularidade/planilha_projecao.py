"""Planilha da projeção da RQ3: uma aba por cenário (S1, S3h, S4, S5, S2), um CSV por aba e a aba "Leia-me".

Lê `<unidades>/<l>_<cenario>_detalhe.csv.gz` (gerado por `cenarios.py --detalhe`) e `_pares.csv.gz`. Cada linha é uma faixa de um método numa origem; a linha de total fecha a origem
(projeção, real e ABRE). Confere que a projeção por faixa soma o total previsto em `pares` e que o ABRE médio dos totais bate com `resumo_s1_a_s5.py`.

Origens: as mesmas das tabelas de ABRE (`tabelas_cenarios.origens`): S1, S3h e S5 em todo trimestre de 2017 em diante, S4 e S2 em dezembro.

Precisa de openpyxl (fora do `pyproject.toml`): `uv run --no-project --with pandas --with openpyxl --with scipy python scripts/granularidade/planilha_projecao.py <unidades> <saida>`
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tabelas_cenarios import LINGUAS, METODOS, carrega, origens

UNIDADES, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
CENARIOS = ["S1", "S3h", "S4", "S5", "S2"]
SO_DEZEMBRO = {"S1": False, "S3h": False, "S4": True, "S5": False, "S2": True}
# nome do método na planilha -> nome em `pares`
NOME_NOS_PARES = {
    "Ingênua": "ingenua",
    "Coorte": "coorte_R0",
    "Coorte^R": "coorte_R3",
    "Conservador^R": "conservador_R3",
    "Ingênua-Coorte^R": "C3_R3",
    "Pessimista sem repositórios": "pessimista_R0",
    "Otimista sem repositórios": "otimista_R0",
    "Pessimista com repositórios": "pessimista_nova_R3",
    "Otimista com repositórios": "otimista_nova_R3",
}


def previsto_dos_pares(cenario: str, lingua: str) -> pd.DataFrame:
    partes = [pd.read_csv(UNIDADES / f"{lingua}_{cenario}_pares.csv.gz")]
    for r in (1, 2, 3):
        partes.append(pd.read_csv(UNIDADES / f"{lingua}_{cenario}_R{r}_pares.csv.gz"))
    return pd.concat(partes, ignore_index=True)


def abre(real: float, previsto: float) -> float:
    if np.isnan(previsto) or real <= 0 or previsto <= 0:
        return np.nan
    return abs(previsto - real) / min(previsto, real)


abas = {}
conferencias = []
for cenario in CENARIOS:
    blocos = []
    for lingua in LINGUAS:
        arquivo = UNIDADES / f"{lingua}_{cenario}_detalhe.csv.gz"
        if not arquivo.exists():
            continue
        detalhe = pd.read_csv(arquivo)
        pares = previsto_dos_pares(cenario, lingua)
        # origens das tabelas de ABRE (o filtro depende dos cinco métodos principais)
        ab = carrega({cenario: UNIDADES.parent}, cenario, lingua)
        escolhidas = origens(ab, SO_DEZEMBRO[cenario])
        datas_ok = set(escolhidas["origem"].dt.strftime("%Y-%m-%d"))
        if cenario == "S5":
            todas_s5 = set(origens(ab, False)["origem"].dt.strftime("%Y-%m-%d"))
            datas_ok = todas_s5
        detalhe = detalhe[detalhe["origem"].isin(datas_ok)].copy()
        detalhe["origem_de_dezembro"] = pd.to_datetime(detalhe["origem"]).dt.month == 12

        chave = ["linguagem", "cenario", "origem", "data_projetada", "metodo", "origem_de_dezembro"]
        total = detalhe.groupby(chave, sort=False).agg(
            pessoas_na_faixa_origem=("pessoas_na_faixa_origem", "sum"),
            projecao_faixa=("projecao_faixa", lambda x: x.sum(skipna=False)),
            real_faixa=("real_faixa", "sum"),
        )
        total = total.reset_index()
        total["abre"] = [
            abre(r, p) for r, p in zip(total["real_faixa"], total["projecao_faixa"], strict=True)
        ]
        total["faixa"] = -1
        total["faixa_rotulo"] = "TOTAL"
        # confere contra `pares`
        pares["origem"] = pares["origem"].astype(str)
        pares_c = pares.set_index(["origem", "metodo"])
        maior = 0.0
        for _, x in total.iterrows():
            achado = pares_c.loc[(x["origem"], NOME_NOS_PARES[x["metodo"]])]
            esperado = float(
                achado["previsto"]
                if not isinstance(achado, pd.DataFrame)
                else achado["previsto"].iloc[0]
            )
            if np.isnan(esperado) and np.isnan(x["projecao_faixa"]):
                continue
            maior = max(maior, abs(esperado - x["projecao_faixa"]) / max(1.0, abs(esperado)))
        conferencias.append(
            {
                "cenario": cenario,
                "linguagem": lingua,
                "linhas_de_total": len(total),
                "maior_diferenca_relativa_contra_pares": maior,
            }
        )
        blocos.append(pd.concat([detalhe, total], ignore_index=True))
    aba = pd.concat(blocos, ignore_index=True)
    aba["_ordem_faixa"] = aba["faixa"].replace(-1, 10**6)
    aba = aba.sort_values(["linguagem", "origem", "metodo", "_ordem_faixa"], kind="stable").drop(
        columns="_ordem_faixa"
    )
    abas[cenario] = aba

conferencia = pd.DataFrame(conferencias)
conferencia.to_csv(SAIDA / "conferencia_totais.csv", index=False)
assert (conferencia["maior_diferenca_relativa_contra_pares"] < 1e-9).all(), (
    "a projeção por faixa não soma o total de `pares`"
)

# ABRE médio dos totais contra a tabela de ABRE
tabela = pd.read_csv(UNIDADES.parent / "resumo" / "abre_por_cenario.csv")
divergencias = []
for cenario, aba in abas.items():
    t = aba[aba["faixa_rotulo"] == "TOTAL"]
    for lingua in LINGUAS:
        for metodo in METODOS.values():
            valores = t[(t["linguagem"] == lingua) & (t["metodo"] == metodo)]
            conjuntos = [(cenario, valores)]
            if cenario == "S5":  # a tabela traz também só as origens de dezembro
                conjuntos.append(("S5 (dezembro)", valores[valores["origem_de_dezembro"]]))
            for nome_na_tabela, parte in conjuntos:
                esperado = tabela[
                    (tabela["linguagem"] == lingua)
                    & (tabela["metodo"] == metodo)
                    & (tabela["cenario"] == nome_na_tabela)
                ]
                if esperado.empty or parte.empty:
                    continue
                if abs(parte["abre"].mean() - esperado["abre_medio"].iloc[0]) > 1e-9:
                    divergencias.append(
                        (
                            nome_na_tabela,
                            lingua,
                            metodo,
                            parte["abre"].mean(),
                            esperado["abre_medio"].iloc[0],
                        )
                    )
(SAIDA / "conferencia_abre.txt").write_text(
    "ABRE médio dos totais da planilha contra a tabela de ABRE: "
    + (
        "tudo igual (diferença máxima 1e-9)"
        if not divergencias
        else f"{len(divergencias)} divergências: {divergencias[:5]}"
    )
    + "\n",
    encoding="utf-8",
)
assert not divergencias, divergencias[:5]

# Nome de cada cenário na planilha (aba, CSV e coluna `cenario`)
NOMES_DOS_CENARIOS = {
    "S1": "Curto e amplo",
    "S3h": "Longo e amplo",
    "S4": "Longo, não casuais",
    "S5": "Curto, não casuais",
    "S2": "Anual",
}
COLUNAS_SAIDA = [
    "linguagem", "cenario", "origem", "origem_de_dezembro", "data_projetada", "metodo", "faixa", "faixa_rotulo", "pessoas_na_faixa_origem", "taxa_permanencia",
    "origem_da_taxa", "saida_por_parada", "novatos_usados", "novatos_por_passo", "repos_novos", "repos_existentes_por_passo", "novatos_por_repo_novo",
    "novatos_por_repo_existente", "projecao_faixa", "real_faixa", "abre",
]  # fmt: skip
for cenario, aba in abas.items():
    aba["cenario"] = NOMES_DOS_CENARIOS[cenario]
    nome_do_arquivo = NOMES_DOS_CENARIOS[cenario].lower().replace(", ", "_").replace(" ", "_")
    aba[COLUNAS_SAIDA].to_csv(
        SAIDA / f"planilha_{nome_do_arquivo}.csv", index=False, float_format="%.10g"
    )

LEIA_ME = [
    ("Cenários", ""),
    (
        "S1",
        "Saída 3 meses, horizonte 3 meses, recortes de 3 meses. Todos os contribuidores. Idade: tempo desde a primeira contribuição, faixas de 3 meses. Ativo: contribuiu nos últimos 3 meses. Origens: todo trimestre de 2017 em diante.",
    ),
    (
        "S3h",
        "Saída 12 meses, horizonte 12 meses, recortes de 3 meses. Todos os contribuidores. Idade como no cenário Curto e amplo. Ativo: contribuiu nos últimos 12 meses. Origens: todo trimestre de 2017 em diante.",
    ),
    (
        "S4",
        "Saída 12 meses, horizonte 12 meses, recortes de 3 meses. Não casuais residentes pelo passado (segunda ocasião até a origem). Idade descontada (regra do S2) em faixas de 3 meses. Origens: dezembro de 2017 a 2023 (Elixir de 2020 a 2023).",
    ),
    (
        "S5",
        "Saída 12 meses, horizonte 3 meses, recortes de 3 meses. Mesma população e idade do cenário Longo, não casuais. Origens: todo trimestre de 2017 a 2024; a coluna origem_de_dezembro marca as de dezembro.",
    ),
    (
        "S2",
        "Saída 12 meses, horizonte 12 meses, recortes de 12 meses (31 de dezembro). Não casuais residentes pelo passado. Idade descontada, faixas de 1 ano. Origens de dezembro.",
    ),
    ("Métodos", ""),
    ("Ingênua", "A pirâmide da origem repetida no alvo (taxa 1, nenhum novato extra)."),
    (
        "Coorte",
        "Cada faixa sobe uma faixa por passo com a taxa de permanência do último recorte; a faixa 0 recebe a média dos novatos dos últimos 2 anos.",
    ),
    (
        "Coorte^R",
        "Coorte com previsão de repositórios: taxa do último recorte sem a saída por parada de repositório, multiplicada por (1 menos a saída por parada), e novatos = repositórios novos esperados x novatos por repositório novo + repositórios existentes esperados x novatos por repositório existente.",
    ),
    ("Conservador^R", "Como a Coorte^R, com a taxa média dos últimos 2 anos."),
    ("Ingênua-Coorte^R", "Média simples da Ingênua e da Coorte^R, faixa a faixa."),
    (
        "Pessimista/Otimista sem repositórios",
        "Taxa mínima (pessimista) ou máxima (otimista) dos últimos 5 anos em cada faixa e novatos mínimo ou máximo da janela de 2 anos (R0).",
    ),
    (
        "Pessimista/Otimista com repositórios",
        "Como os anteriores com a saída por parada e os novatos da regra nova (R3): mínimo (máximo) entre o extremo da janela e o valor projetado para repositórios novos e existentes.",
    ),
    ("Colunas", ""),
    ("origem", "Data do recorte em que a projeção é feita."),
    ("data_projetada", "Data do alvo (origem mais o horizonte)."),
    (
        "faixa, faixa_rotulo",
        "Faixa de idade na régua do cenário (3 meses nos quatro primeiros cenários; 1 ano no Anual). A última faixa é aberta (8 anos ou mais). A linha TOTAL soma as faixas.",
    ),
    ("pessoas_na_faixa_origem", "Pessoas ativas na faixa na data da origem."),
    (
        "taxa_permanencia",
        "Fração das pessoas da faixa que passa à faixa seguinte em um passo. Vazia onde a faixa não tinha gente em nenhum recorte do histórico.",
    ),
    ("origem_da_taxa", "Último recorte, média de 2 anos, mínimo de 5 anos ou máximo de 5 anos."),
    (
        "saida_por_parada",
        "Probabilidade de a pessoa da faixa ficar sem repositório ativo na origem (parada de repositório). Zero nos métodos sem previsão de repositórios.",
    ),
    (
        "novatos_usados",
        "Soma dos novatos que entram na faixa 0 em todos os passos até o alvo. novatos_por_passo traz o valor de cada passo, separado por ponto e vírgula.",
    ),
    (
        "repos_novos, repos_existentes_por_passo, novatos_por_repo_novo, novatos_por_repo_existente",
        "Componentes dos novatos da Coorte^R e da Conservador^R: repositórios novos esperados por recorte (média de 2 anos), repositórios existentes esperados em cada passo, e novatos por repositório novo e por existente (médias de 2 anos). Vazios nos demais métodos.",
    ),
    (
        "projecao_faixa, real_faixa",
        "Pessoas projetadas e pessoas reais na faixa na data projetada.",
    ),
    (
        "abre",
        "Só na linha TOTAL: erro relativo absoluto, |projeção menos real| dividido pelo menor dos dois.",
    ),
    (
        "Conferências",
        "A projeção por faixa soma o total previsto em `pares` (diferença relativa abaixo de 1e-9) e o ABRE médio dos totais é o da tabela de ABRE por cenário. Ver conferencia_totais.csv e conferencia_abre.txt.",
    ),
]
with pd.ExcelWriter(SAIDA / "projecao_rq3.xlsx", engine="openpyxl") as escritor:
    pd.DataFrame(LEIA_ME, columns=["Item", "Definição"]).to_excel(
        escritor, sheet_name="Leia-me", index=False
    )
    for cenario, aba in abas.items():
        aba[COLUNAS_SAIDA].to_excel(escritor, sheet_name=NOMES_DOS_CENARIOS[cenario], index=False)
    for nome, folha in escritor.sheets.items():
        folha.freeze_panes = "A2"
        if nome == "Leia-me":
            folha.column_dimensions["A"].width = 38
            folha.column_dimensions["B"].width = 140
print(conferencia.to_string())
print({c: len(a) for c, a in abas.items()})
