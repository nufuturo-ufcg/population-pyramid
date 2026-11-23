"""Junta em `comparacao-v3.md` o valor antigo e o novo de cada tabela refeita no item 4 de `correcao-elegibilidade`.

  - RQ2 (CSV da rodada oficial): log-rank, expectativa de vida, padronização, trajetória e CCR/NCR.
  - projecao-rq3 (Markdown): Parte 2, testes_s2, cobertura-v2 e investigação.
Cada célula mostra `antigo → novo`; célula igual aparece uma vez. Os CSV completos ficam em `comparacao-v3/`.
Não interpreta nenhum número.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/comparacao_v3.py <pyramid-vitalidade> <saida-dir>
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compara_csv import compara

RAIZ, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
CSVS = SAIDA / "comparacao-v3"
ANTIGA = RAIZ / "rodada-2026-11-14-0921" / "geral-mais_de_uma_ocasiao" / "csv" / "vitalidade"
NOVA = RAIZ / "rodada-oficial-v3" / "geral-mais_de_uma_ocasiao" / "csv" / "vitalidade"
LINGUAS = ["clojure", "elixir", "ocaml", "python", "zig"]

T = [
    "# Valores antigos e novos lado a lado",
    "",
    "Cada célula mostra `antigo → novo`. Célula igual aparece uma vez. Antigo: carga de 2026-11-14 (rodada oficial). Novo: carga `-v3`.",
    "Os CSV completos estão em `comparacao-v3/`, com a coluna `mudou`.",
    "",
    "# RQ2: comparação entre linguagens",
    "",
]

linhas, total, mudaram = compara(
    ANTIGA / "logrank.csv", NOVA / "logrank.csv", ["comparacao"], CSVS / "logrank.csv"
)
T += ["## Log-rank (todas as linhas)", "", *linhas, "", f"{mudaram} de {total} linhas mudam.", ""]

linhas, total, mudaram = compara(
    ANTIGA / "tabua_comparada.csv", NOVA / "tabua_comparada.csv", ["linguagem", "x"], CSVS / "tabua_comparada.csv",
    consulta="x in (0, 1, 2, 3, 5)", colunas=["l", "d", "q", "S", "e"],
)  # fmt: skip
T += [
    "## Tábua de vida comparada (idades 0, 1, 2, 3 e 5)",
    "",
    "`l` é o número de pessoas em risco, `d` as saídas, `q` a chance de sair, `S` a chance de seguir desde o início e `e` os anos esperados.",
    "",
    *linhas,
    "",
    f"{mudaram} de {total} linhas mudam (arquivo completo em `comparacao-v3/tabua_comparada.csv`).",
    "",
]

linhas, total, mudaram = compara(
    ANTIGA / "padronizacao.csv", NOVA / "padronizacao.csv", ["linguagem", "ano", "rodada"], CSVS / "padronizacao.csv",
    consulta="ano in (2014, 2018, 2022, 2024)", colunas=["ativos", "saidas", "taxa_bruta", "taxa_padronizada", "smr"],
)  # fmt: skip
T += [
    "## Padronização por faixa (2014, 2018, 2022 e 2024; `rodada` é a referência: nicho ou python)",
    "",
    *linhas,
    "",
    f"{mudaram} de {total} linhas mudam (arquivo completo em `comparacao-v3/padronizacao.csv`).",
    "",
]

linhas, total, mudaram = compara(
    ANTIGA / "trajetoria.csv", NOVA / "trajetoria.csv", ["slug", "ano"], CSVS / "trajetoria.csv",
    consulta="ano in (2014, 2018, 2022, 2024)",
    colunas=["ativos", "novatos", "saidas", "voltas", "natalidade_pct", "mortalidade_pct", "crescimento_natural_pct"],
)  # fmt: skip
T += [
    "## Trajetória anual (2014, 2018, 2022 e 2024)",
    "",
    *linhas,
    "",
    f"{mudaram} de {total} linhas mudam (arquivo completo em `comparacao-v3/trajetoria.csv`).",
    "",
]

linhas, total, mudaram = compara(
    ANTIGA / "ccr_ncr_comparado.csv", NOVA / "ccr_ncr_comparado.csv", ["slug", "snapshot"], CSVS / "ccr_ncr_comparado.csv",
    consulta="snapshot in ('2014-12-31', '2018-12-31', '2022-12-31', '2024-12-31')",
    colunas=["total", "new", "experienced", "ccr", "ncr", "type"],
)  # fmt: skip
T += [
    "## CCR e NCR (fim de 2014, 2018, 2022 e 2024)",
    "",
    *linhas,
    "",
    f"{mudaram} de {total} linhas mudam (arquivo completo em `comparacao-v3/ccr_ncr_comparado.csv`).",
    "",
]

linhas, total, mudaram = compara(
    ANTIGA / "composicao_pct.csv", NOVA / "composicao_pct.csv", ["slug", "ano", "faixa"], CSVS / "composicao_pct.csv",
    consulta="slug == 'clojure' and ano in (2014, 2018, 2022, 2024)", colunas=["non_coding", "coding"],
)  # fmt: skip
T += [
    "## Composição por faixa, em porcentagem (Clojure, 2014, 2018, 2022 e 2024)",
    "",
    *linhas,
    "",
    f"{mudaram} de {total} linhas mudam, em todas as linguagens e anos (arquivo completo em `comparacao-v3/composicao_pct.csv`).",
    "",
]
cabecalho = "\n".join(T)
(SAIDA / "comparacao-v3-rq2.md").write_text(cabecalho + "\n", encoding="utf-8")

# Tabelas em Markdown do rq3, lado a lado
RQ3, RQ3_V3 = RAIZ / "projecao-rq3", RAIZ / "projecao-rq3-v3"
pares = [
    ("Projeção RQ3, Parte 2: resumo", RQ3 / "resumo.md", RQ3_V3 / "resumo.md"),
    ("Projeção RQ3, Parte 2: tabelas", RQ3 / "tabelas.md", RQ3_V3 / "tabelas.md"),
    ("Projeção RQ3: testes do S2", RQ3 / "testes_s2.md", RQ3_V3 / "testes_s2.md"),
    (
        "Cobertura v2: resumo",
        RQ3 / "cobertura-v2" / "resumo.md",
        RQ3_V3 / "cobertura-v2-v3" / "resumo.md",
    ),
    (
        "Cobertura v2: tabelas",
        RQ3 / "cobertura-v2" / "tabelas.md",
        RQ3_V3 / "cobertura-v2-v3" / "tabelas.md",
    ),
    (
        "Investigação: tabelas",
        RQ3 / "investigacao" / "tabelas.md",
        RQ3_V3 / "investigacao-v3" / "tabelas.md",
    ),
]
argumentos = [
    sys.executable,
    str(Path(__file__).resolve().parent / "compara_tabelas.py"),
    str(SAIDA / "comparacao-v3-rq3.md"),
]
for titulo, antigo, novo in pares:
    argumentos += [titulo, str(antigo), str(novo)]
subprocess.run(argumentos, check=True)
print("comparação gravada em", SAIDA)
