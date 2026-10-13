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

    diferenca_total = chega.loc[5, py] / chega.loc[5, c]
    diferenca_2_anos = chega.loc[2, py] / chega.loc[2, c]
    parcela = 100 * np.log(diferenca_2_anos) / np.log(diferenca_total)
    menor_s5 = chega.loc[5].idxmin() == c
    sobe_c = 100 * (fica.loc[3, c] - fica.loc[0, c])
    sobe_py = 100 * (fica.loc[3, py] - fica.loc[0, py])
    leitura = [
        "| Sua afirmação | Tabela | Como a tabela mostra | Resultado |",
        "|---|---|---|---|",
        "| Existe um ponto de virada em 2 a 3 anos | Chance de seguir mais 1 ano | "
        f"Coluna {c}: x=0 {num(fica.loc[0, c])}, x=2 {num(fica.loc[2, c])}, "
        f"x=3 {num(fica.loc[3, c])}, x=5 {num(fica.loc[5, c])}. Sobe até x=3 e quase para. "
        "As outras quatro colunas têm o mesmo formato. | Confirmada |",
        f"| Em {py} essa chance fica uniforme | Chance de seguir mais 1 ano | "
        f"Coluna {py}: x=0 {num(fica.loc[0, py])}, x=2 {num(fica.loc[2, py])}, "
        f"x=3 {num(fica.loc[3, py])}, x=5 {num(fica.loc[5, py])}. Sobe {num(sobe_py, 0)} pontos "
        f"de x=0 a x=3, contra {num(sobe_c, 0)} em {c}. | Parcial: mais plana, não uniforme |",
        f"| {c} tem dificuldade de chegar à senioridade | Fração que chega a x | "
        f"S(5) = {num(chega.loc[5, c])} em {c} e {num(chega.loc[5, py])} em {py}"
        + (", o menor das cinco" if menor_s5 else "")
        + f". S(2) = {num(chega.loc[2, c])} contra {num(chega.loc[2, py])}: "
        f"{num(parcela, 0)}% da distância em S(5) já existe em x=2. | Confirmada |",
        f"| O sênior de {c} sai menos | Chance de seguir mais 1 ano, linhas x=5 a x=8 | "
        f"x=5: {num(fica.loc[5, c])} em {c} e {num(fica.loc[5, py])} em {py}. "
        f"x=8: {num(fica.loc[8, c])} e {num(fica.loc[8, py])}. {c} fica igual ou abaixo. "
        "| Não aparece |",
        "",
        f"{zig} tem poucas pessoas nos x altos (l(8) = {num(risco.loc[8, zig], 0)}), "
        "e os valores dele ali oscilam. e(x) cai nos x altos por construção: quanto mais "
        "velho o x, menos anos de coleta restam para somar.",
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


def secao_piramides(figuras: str) -> str:
    linhas = [
        "## 3. Pirâmides ao longo do tempo",
        "",
        "Uma linha por linguagem, uma coluna por ano. Cada pirâmide soma 100% dos ativos do "
        "ano. Esquerda: discussão. Direita: código. Pirâmide com menos de 100 ativos fica vazia.",
        "",
        f"![pirâmides]({figuras}/trajetoria_linha_do_tempo.png)",
        "",
    ]
    return "\n".join(linhas)


def secao_crescimento(base: Path, p: v.Parametros, ordem: list[str]) -> str:
    quadros = []
    for slug in ordem:
        pasta = slug if p.populacao == "todos" else f"{slug}-{p.populacao}"
        a = pd.read_csv(base / pasta / "csv" / "vitalidade" / "anual.csv").set_index("ano")
        a["variacao"] = 100 * (a["ativos"] / a["ativos"].shift(1) - 1)
        a["linguagem"] = slug
        quadros.append(a.reset_index())
    t = pd.concat(quadros, ignore_index=True)
    ultimo = pd.Timestamp(p.data_de_corte).year - 1
    t = t[(t["ano"] >= 2015) & (t["ano"] <= ultimo)]
    liquido = por_linguagem(t, "crescimento_liquido_pct", "ano", ordem)
    variacao = por_linguagem(t, "variacao", "ano", ordem)
    linhas = [
        "## 4. Crescimento líquido: base de cálculo",
        "",
        "O crescimento líquido do ano Y **tem como base os ativos do próprio ano Y**. "
        "Ele não é a variação sobre o ano anterior.",
        "",
        "- Crescimento líquido(Y) = (novatos(Y) + voltas(Y) - saídas(Y) - pausas(Y)) / ativos(Y).",
        "- Novatos e voltas de Y são quem entrou em Y. Saídas e pausas de Y são quem tem a "
        "última contribuição em Y (a saída só se confirma 12 meses depois).",
        "- Variação dos ativos(Y) = ativos(Y) / ativos(Y-1) - 1. Essa sim usa o ano anterior "
        "como base, com as saídas e pausas de Y-1.",
        "- Os dois ficam parecidos quando a comunidade é estável e se separam quando ela "
        "muda de tamanho.",
        "",
        "### Crescimento líquido do ano (%, base: ativos do mesmo ano)",
        "",
        tabela_md(liquido, 1),
        "",
        "### Variação dos ativos sobre o ano anterior (%)",
        "",
        tabela_md(variacao, 1),
        "",
    ]
    return "\n".join(linhas)


def secao_janela(p: v.Parametros) -> str:
    linhas = [
        "## 5. Até onde vai a análise e por quê",
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
        "# Vitalidade das comunidades\n",
        f"Os números vêm dos CSV de `{nome}/csv/vitalidade/`.\n",
        secao_tabua(pasta, figuras, ordem),
        secao_ccr_ncr(pasta, figuras, ordem),
        secao_piramides(figuras),
        secao_crescimento(base, p, ordem),
        secao_janela(p),
    ]
    destino = base / "RELATORIO.md"
    destino.write_text("\n".join(partes))
    print(f"relatório: {destino}")


if __name__ == "__main__":
    main()
