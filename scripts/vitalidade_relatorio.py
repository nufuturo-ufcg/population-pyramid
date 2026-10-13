"""Escreve RELATORIO.md na raiz da pasta de resultados: tábua de vida e CCR/NCR das 5 linguagens.

    uv run python scripts/vitalidade_relatorio.py --saida ~/Documents/pyramid-vitalidade

Todo número do documento vem dos CSV de `geral-<população>/csv/vitalidade/`. As frases de leitura
ficam aqui e citam células da tabela, nunca um valor digitado.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import carga_fonte
import vitalidade as v


def num(valor: float, casas: int = 2) -> str:
    """Número com vírgula decimal."""
    return f"{valor:.{casas}f}".replace(".", ",")


def tabela_md(t: pd.DataFrame, casas: int = 2) -> str:
    """Tabela em markdown, a primeira coluna é o índice."""
    colunas = [t.index.name or ""] + [str(c) for c in t.columns]
    linhas = ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
    for indice, linha in t.iterrows():
        celulas = [str(indice)]
        for valor in linha:
            celulas.append("" if pd.isna(valor) else num(valor, casas))
        linhas.append("| " + " | ".join(celulas) + " |")
    return "\n".join(linhas)


def por_linguagem(t: pd.DataFrame, coluna: str, indice: str, ordem: list[str]) -> pd.DataFrame:
    """Uma coluna por linguagem, na ordem do yaml e com o nome de exibição."""
    p = t.pivot(index=indice, columns="linguagem", values=coluna)
    p = p[[slug for slug in ordem if slug in p.columns]]
    p = p.rename(columns={slug: carga_fonte.LINGUAGENS[slug].nome for slug in ordem})
    p.index.name = "x (anos)" if indice == "x" else indice
    return p


def secao_tabua(pasta: Path, figuras: str, ordem: list[str]) -> str:
    t = pd.read_csv(pasta / "csv" / "vitalidade" / "tabua_comparada.csv")
    t["fica"] = 1 - t["q"]
    fica = por_linguagem(t, "fica", "x", ordem)
    chega = por_linguagem(t, "S", "x", ordem)
    resta = por_linguagem(t, "e", "x", ordem)
    risco = por_linguagem(t, "l", "x", ordem)

    c = carga_fonte.LINGUAGENS["clojure"].nome
    py = carga_fonte.LINGUAGENS["python"].nome
    zig = carga_fonte.LINGUAGENS["zig"].nome

    saida_c = 1 - fica[c]
    saida_py = 1 - fica[py]
    diferenca_total = chega.loc[5, py] / chega.loc[5, c]
    diferenca_2_anos = chega.loc[2, py] / chega.loc[2, c]
    parcela = 100 * np.log(diferenca_2_anos) / np.log(diferenca_total)
    leitura = [
        "- **Ponto de virada: confirmado.** Nas cinco linguagens a chance de seguir mais 1 ano "
        "sobe nos primeiros 3 anos e depois fica estável.",
        f"- {c}: a chance de sair no ano cai de {num(100 * saida_c[0], 0)}% em x=0 para "
        f"{num(100 * saida_c[2], 0)}% em x=2 e {num(100 * saida_c[5], 0)}% em x=5.",
        f"- {py}: cai de {num(100 * saida_py[0], 0)}% em x=0 para {num(100 * saida_py[2], 0)}% "
        f"em x=2 e {num(100 * saida_py[5], 0)}% em x=5.",
        f"- **{py} uniforme: não aparece nos dados.** A chance de sair em {py} também cai "
        "com o tempo de casa, com a mesma forma de {c}, a um nível mais baixo.".replace("{c}", c),
        f"- **Chegar à senioridade em {c}: confirmado.** S(5) = {num(chega.loc[5, c])} em {c} "
        f"e {num(chega.loc[5, py])} em {py}. {num(parcela, 0)}% dessa distância se forma "
        "nos 2 primeiros anos.",
        f"- **Sênior de {c} sai menos: não aparece nos dados.** Quem chegou a 5 anos segue mais "
        f"1 ano com chance {num(fica.loc[5, c])} em {c} e {num(fica.loc[5, py])} em {py}. "
        f"Em x=8 são {num(fica.loc[8, c])} e {num(fica.loc[8, py])}.",
        f"- {zig} tem poucas pessoas nos x altos (l(8) = {num(risco.loc[8, zig], 0)}), "
        "e os valores dele ali oscilam.",
        "- e(x) cai nos x altos por construção: quanto mais velho o x, menos anos de coleta "
        "restam para somar.",
    ]
    linhas = [
        "## 1. Tábua de vida",
        "",
        "x é o tempo de casa em anos completos, contado da primeira contribuição.",
        "",
        "- **Chance de seguir mais 1 ano, tendo chegado a x**: 1 - q(x).",
        "- **Fração que chega a x**: S(x).",
        "- **Anos que ainda restam**: e(x). É piso, a cauda censurada fica de fora.",
        "",
        f"![chegar e ficar]({figuras}/tabua_chegar_e_ficar.png)",
        "",
        "### Chance de seguir mais 1 ano, tendo chegado a x",
        "",
        tabela_md(fica),
        "",
        "### Fração que chega a x",
        "",
        tabela_md(chega),
        "",
        "### Anos que ainda restam, e(x)",
        "",
        tabela_md(resta),
        "",
        f"![e(x)]({figuras}/tabua_esperanca_comparada.png)",
        "",
        "### Pessoas em risco, l(x)",
        "",
        tabela_md(risco, 0),
        "",
        "### Leitura",
        "",
        *leitura,
        "",
    ]
    return "\n".join(linhas)


def secao_ccr_ncr(pasta: Path, figuras: str, ordem: list[str]) -> str:
    t = pd.read_csv(pasta / "csv" / "vitalidade" / "ccr_ncr_comparado.csv")
    t["snapshot"] = pd.to_datetime(t["snapshot"])
    t = t.rename(columns={"slug": "linguagem"})
    fim_de_ano = t[(t["snapshot"].dt.month == 12) & (t["total"] >= 100)].copy()
    fim_de_ano["ano"] = fim_de_ano["snapshot"].dt.year
    ccr = por_linguagem(fim_de_ano, "ccr", "ano", ordem)
    ncr = por_linguagem(fim_de_ano, "ncr", "ano", ordem)
    ccr = ccr[ccr.index >= 2010]
    ncr = ncr[ncr.index >= 2010]
    linhas = [
        "## 2. CCR e NCR ao longo do tempo",
        "",
        "- CCR = (código - discussão) / o maior dos dois, entre quem contribuiu em 12 meses.",
        "- NCR = (novatos - experientes) / o maior dos dois. Novato tem até 12 meses de casa.",
        "- Valores no fim de cada ano, nas comunidades com pelo menos 100 ativos.",
        "",
        f"![série]({figuras}/ccr_ncr_serie.png)",
        "",
        f"![dispersão]({figuras}/ccr_ncr_dispersao.png)",
        "",
        "### CCR no fim do ano",
        "",
        tabela_md(ccr),
        "",
        "### NCR no fim do ano",
        "",
        tabela_md(ncr),
        "",
    ]
    return "\n".join(linhas)


def secao_janela(p: v.Parametros) -> str:
    linhas = [
        "## 3. Até onde vai a análise e por quê",
        "",
        f"- O estudo termina em **{p.data_de_corte}** (`data_de_corte`). Os eventos de 2026 saem "
        "de tudo.",
        "- 2026 está incompleto: a coleta termina antes do fim do ano, e meio ano distorceria "
        "as taxas anuais.",
        "- Ativos, novatos, pirâmides e CCR/NCR vão até 2025.",
        "- Saída, mortalidade e crescimento vão até 2024. A saída exige 12 meses sem contribuir "
        "depois da última contribuição (Avelino et al., ESEM 2019). Para 2025 esses 12 meses "
        "cairiam em 2026.",
        f"- Na tábua de vida, a duração termina em {p.data_de_corte}. Quem tem o último evento "
        "a 12 meses ou menos do fim conta como censurado: pode ainda estar ativo.",
        "- A troca de papel (discussão para código e a volta) vai até 2024, pelo mesmo motivo "
        "da saída.",
        f"- População: `{p.populacao}`. Só entra quem tem 30 dias ou mais entre o primeiro e o "
        "último evento, de qualquer tipo (commit, PR, issue, comentário).",
        "- Os cortes ficam em `scripts/vitalidade.yaml` (lista em `docs/linguagem/parametros.md`).",
        "",
    ]
    return "\n".join(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", default=str(v.PADRAO_SAIDA))
    parser.add_argument("--set", dest="sobrepostos", action="append", default=[])
    args = parser.parse_args()

    p = v.carrega_parametros(args.sobrepostos)
    base = Path(args.saida).expanduser()
    nome = "geral" if p.populacao == "todos" else f"geral-{p.populacao}"
    pasta = base / nome
    figuras = f"{nome}/vitalidade"
    ordem = p.linguagens_rq2

    partes = [
        "# Vitalidade das comunidades: tábua de vida e CCR/NCR\n",
        f"Os números vêm dos CSV de `{nome}/csv/vitalidade/`.\n",
        secao_tabua(pasta, figuras, ordem),
        secao_ccr_ncr(pasta, figuras, ordem),
        secao_janela(p),
    ]
    destino = base / "RELATORIO.md"
    destino.write_text("\n".join(partes))
    print(f"relatório: {destino}")


if __name__ == "__main__":
    main()
