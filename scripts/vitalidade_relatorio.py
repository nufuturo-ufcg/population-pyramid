"""Escreve RELATORIO.md na raiz da pasta de resultados: tábua de vida e CCR/NCR das 5 linguagens.

    uv run python scripts/vitalidade_relatorio.py --saida ~/Documents/pyramid-vitalidade

Todo número do documento vem dos CSV de `geral-<população>/csv/vitalidade/`. As frases de leitura
ficam aqui e citam células da tabela, nunca um valor digitado.
"""

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import carga_fonte
import vitalidade as v


def num(valor: float, casas: int = 2) -> str:
    """Número com vírgula decimal."""
    return f"{valor:.{casas}f}".replace(".", ",")


def _so_inteiros(coluna: pd.Series) -> bool:
    """Coluna numérica cujos valores são todos inteiros (contagens)."""
    if not pd.api.types.is_numeric_dtype(coluna):
        return False
    valores = coluna.dropna()
    return len(valores) > 0 and bool((valores == valores.round()).all())


def tabela_md(t: pd.DataFrame, casas: int = 2) -> str:
    """Tabela em markdown, a primeira coluna é o índice. Coluna de contagens sai sem casas."""
    colunas = [t.index.name or ""] + [str(c) for c in t.columns]
    linhas = ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
    inteiras = [_so_inteiros(t[c]) for c in t.columns]
    for indice, linha in t.iterrows():
        celulas = [str(indice)]
        for valor, inteira in zip(linha, inteiras, strict=True):
            if pd.isna(valor):
                celulas.append("")
            elif isinstance(valor, str):
                celulas.append(valor)
            else:
                celulas.append(num(valor, 0 if inteira else casas))
        linhas.append("| " + " | ".join(celulas) + " |")
    return "\n".join(linhas)


def por_linguagem(t: pd.DataFrame, coluna: str, indice: str, ordem: list[str]) -> pd.DataFrame:
    """Uma coluna por linguagem, na ordem do yaml e com o nome de exibição."""
    p = t.pivot(index=indice, columns="linguagem", values=coluna)
    p = p[[slug for slug in ordem if slug in p.columns]]
    p = p.rename(columns={slug: carga_fonte.LINGUAGENS[slug].nome for slug in ordem})
    p.index.name = "x (anos)" if indice == "x" else indice
    return p


def _fracao_que_chega(q: pd.Series, ate: int) -> float:
    """Fração que chega a `ate` anos: o produto de (1 - q) nos anos antes."""
    chega = 1.0
    for x in range(ate):
        chega = chega * (1 - q[x])
    return chega


def _anos_ativos_esperados(q: pd.Series, horizonte: int) -> float:
    """Anos ativos esperados de cada pessoa nos `horizonte` primeiros anos de casa."""
    anos = 0.0
    chega = 1.0
    for x in range(horizonte):
        seguinte = chega * (1 - q[x])
        anos = anos + (chega + seguinte) / 2
        chega = seguinte
    return anos


def peso_de_cada_ano(q_a: pd.Series, q_b: pd.Series, nome_a: str, nome_b: str) -> tuple:
    """O que cada ano de casa explica da diferença entre duas linguagens.

    Para cada ano x, troca só a chance de sair em x da linguagem A pela da B e mede o ganho.
    Devolve a tabela e dois números de comparação: 5 pontos a menos de saída em x=0 e em x=4.
    """
    chega_a = _fracao_que_chega(q_a, 5)
    chega_b = _fracao_que_chega(q_b, 5)
    diferenca = math.log(chega_b) - math.log(chega_a)
    base = _anos_ativos_esperados(q_a, 8)
    linhas = []
    for x in range(8):
        parte = ""
        if x < 5:
            parte = 100 * (math.log(1 - q_b[x]) - math.log(1 - q_a[x])) / diferenca
        trocada = q_a.copy()
        trocada[x] = q_b[x]
        linhas.append(
            {
                "x (anos)": x,
                f"sai no ano, {nome_a} %": 100 * q_a[x],
                f"sai no ano, {nome_b} %": 100 * q_b[x],
                "parte da diferença da fração que chega a 5 anos %": parte,
                "ganho em anos ativos se só este ano fosse como o do outro": (
                    _anos_ativos_esperados(trocada, 8) - base
                ),
            }
        )
    tabela = pd.DataFrame(linhas).set_index("x (anos)")
    ganhos = []
    for x in (0, 4):
        menos = q_a.copy()
        menos[x] = menos[x] - 0.05
        ganhos.append(_anos_ativos_esperados(menos, 8) - base)
    return tabela, ganhos[0], ganhos[1]


def secao_tabua(pasta: Path, figuras: str, ordem: list[str]) -> str:
    t = pd.read_csv(pasta / "csv" / "vitalidade" / "tabua_comparada.csv")
    t["fica"] = 1 - t["q"]
    fica = por_linguagem(t, "fica", "x", ordem)
    chega = por_linguagem(t, "S", "x", ordem)
    resta = por_linguagem(t, "e", "x", ordem)
    risco = por_linguagem(t, "l", "x", ordem)
    exposicao = por_linguagem(t, "n_efetivo", "x", ordem)
    censurados = por_linguagem(t, "censurados", "x", ordem)
    saidas = por_linguagem(t, "d", "x", ordem)
    t["fica_inf"] = 1 - t["q_sup"]
    t["fica_sup"] = 1 - t["q_inf"]
    inferior = por_linguagem(t, "fica_inf", "x", ordem)
    superior = por_linguagem(t, "fica_sup", "x", ordem)
    intervalo = fica.copy().astype(object)
    for linguagem in fica.columns:
        for x in fica.index:
            intervalo.loc[x, linguagem] = (
                f"{num(fica.loc[x, linguagem])}, de {num(inferior.loc[x, linguagem])} "
                f"a {num(superior.loc[x, linguagem])}"
            )

    c = carga_fonte.LINGUAGENS["clojure"].nome
    py = carga_fonte.LINGUAGENS["python"].nome
    zig = carga_fonte.LINGUAGENS["zig"].nome

    diferenca_total = chega.loc[5, py] / chega.loc[5, c]
    diferenca_2_anos = chega.loc[2, py] / chega.loc[2, c]
    parcela = 100 * np.log(diferenca_2_anos) / np.log(diferenca_total)
    q_todas = por_linguagem(t, "q", "x", ordem)
    peso, ganho_x0, ganho_x4 = peso_de_cada_ano(q_todas[c], q_todas[py], c, py)
    peso_formatado = peso.copy()
    peso_formatado["parte da diferença da fração que chega a 5 anos %"] = pd.to_numeric(
        peso["parte da diferença da fração que chega a 5 anos %"], errors="coerce"
    )
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
        f"de x=0 a x=3, contra {num(sobe_c, 0)} em {c}. "
        "| Parcial: a curva de Python é mais plana e ainda sobe |",
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
        "e(x) cai nos x altos por construção: quanto mais velho o x, menos anos de coleta "
        "restam para somar.",
        "",
        f"**Por que {zig} tem 1,00 em x=8.** Chegaram a 8 anos {num(risco.loc[8, zig], 0)} "
        f"pessoas. {num(censurados.loc[8, zig], 0)} delas ainda estão ativas no fim da coleta, "
        "então não dá para saber se vão sair, e não entram como saída. As outras "
        f"{num(risco.loc[8, zig] - censurados.loc[8, zig], 0)} tiveram "
        f"{num(saidas.loc[8, zig], 0)} saídas. Contando metade das ainda ativas, são "
        f"{num(exposicao.loc[8, zig], 0)} pessoas observadas, e com tão poucas a margem de "
        f"erro vai de {num(inferior.loc[8, zig])} a {num(superior.loc[8, zig])}. "
        "O 1,00 vem de poucas pessoas observadas.",
        "",
        "**Por que o fim da tabela do Zig tem tão poucas pessoas.** Quem tem 8 anos de Zig "
        "entrou até 2017. Para essas pessoas, o ano x=8 cai nos últimos anos da coleta, e quem "
        "ainda contribui nesses anos não pode ter a saída confirmada.",
    ]
    linhas = [
        "## 1. Tábua de vida",
        "",
        "x é o tempo de casa em anos completos, contado da primeira contribuição.",
        "",
        "- **Chance de seguir mais 1 ano, tendo chegado a x**: 1 - q(x).",
        "- **Fração que chega a x**: S(x).",
        "- **Anos que ainda restam**: e(x). É um mínimo, porque não soma os anos depois do último "
        "observado.",
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
        "### Margem de erro da chance de seguir mais 1 ano",
        "",
        "Cada célula traz o valor da tabela e a faixa em que o valor verdadeiro provavelmente "
        "está (95% de confiança). A faixa depende só de quantas pessoas foram observadas no "
        "ano x: com poucas pessoas ela fica larga.",
        "",
        "- A chance de seguir mais 1 ano olha só o ano seguinte: é 1 menos a taxa de saída do "
        "ano x entre quem chegou a x.",
        "- A margem de erro não olha mais anos. Ela mede quanto essa taxa poderia mudar se "
        "tivéssemos observado outras pessoas parecidas, como a margem de erro de uma pesquisa "
        "eleitoral.",
        "- Conta: com n pessoas observadas e d saídas, a taxa é p = d / n. A faixa é "
        "(p + z² / 2n ± z · raiz(p(1-p)/n + z²/4n²)) / (1 + z² / n), com z = 1,96. "
        "É a fórmula de Wilson, que não passa de 0 nem de 1.",
        "- Pessoas observadas no ano x = pessoas que chegaram a x menos metade das que ainda "
        "estão ativas no fim da coleta, porque delas só se vê metade do ano em média.",
        "",
        tabela_md(intervalo),
        "",
        "### Pessoas observadas no ano x",
        "",
        tabela_md(exposicao, 0),
        "",
        "### Leitura",
        "",
        *leitura,
        "",
        "### O peso de cada ano de casa",
        "",
        "Sair nos primeiros anos custa mais do que sair nos últimos, porque quem sai cedo deixa "
        "de contar em todos os anos seguintes. A tabela troca, uma vez por linha, só a chance de "
        f"sair do ano x de {c} pela de {py} e mede o que muda.",
        "",
        tabela_md(peso_formatado, 2),
        "",
        f"- Mesma redução de 5 pontos na chance de sair: no ano 0 dá {num(ganho_x0)} ano ativo a "
        f"mais por pessoa nos 8 primeiros anos, no ano 4 dá {num(ganho_x4)}.",
        "- A coluna da fração que chega a 5 anos reparte a diferença entre os anos 0 a 4 e soma "
        "100%.",
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
    ultimo = pd.Timestamp(p.data_de_corte).year
    t = t[(t["ano"] >= 2015) & (t["ano"] <= ultimo)]
    natural = por_linguagem(t, "crescimento_natural_pct", "ano", ordem)
    variacao = por_linguagem(t, "variacao", "ano", ordem)
    linhas = [
        "## 4. Crescimento natural: base de cálculo",
        "",
        "O crescimento natural do ano Y **tem como base os ativos do próprio ano Y**. "
        "Ele é diferente da variação dos ativos sobre o ano anterior.",
        "",
        "- Crescimento natural(Y) = tudo que entra menos tudo que sai, dividido pelos ativos de Y: "
        "(novatos(Y) + voltas(Y) - saídas(Y) - pausas(Y)) / ativos(Y).",
        "- Entra quem chegou em Y, como novato ou como volta. Sai quem tem a última contribuição "
        "de um período de atividade em Y, como saída ou como pausa.",
        "- Variação dos ativos(Y) = ativos(Y) / ativos(Y-1) - 1. Essa usa o ano anterior como "
        "base, com as saídas e pausas de Y-1.",
        "- Os dois ficam parecidos quando a comunidade é estável e se separam quando ela "
        "muda de tamanho.",
        "",
        "### Crescimento natural do ano (%, base: ativos do mesmo ano)",
        "",
        tabela_md(natural, 1),
        "",
        "### Variação dos ativos sobre o ano anterior (%)",
        "",
        tabela_md(variacao, 1),
        "",
    ]
    return "\n".join(linhas)


def fim_do_acompanhamento(base: Path, p: v.Parametros, ordem: list[str]) -> pd.DataFrame:
    """Até quando cada linguagem foi acompanhada, lido dos resultados gravados."""
    linhas = []
    for slug in ordem:
        pasta = slug if p.populacao == "todos" else f"{slug}-{p.populacao}"
        meta = json.loads((base / pasta / "resultados" / "vitalidade" / "meta.json").read_text())
        data = pd.Timestamp(meta.get("fim_acompanhamento") or meta["fim"])
        linhas.append({"linguagem": carga_fonte.LINGUAGENS[slug].nome, "acompanhada até": data})
    quadro = pd.DataFrame(linhas).set_index("linguagem")
    quadro["acompanhada até"] = quadro["acompanhada até"].dt.strftime("%d/%m/%Y")
    return quadro


def secao_janela(base: Path, p: v.Parametros, ordem: list[str]) -> str:
    corte = pd.Timestamp(p.data_de_corte)
    quadro = fim_do_acompanhamento(base, p, ordem)
    linhas = [
        "## 5. Até onde vai a análise e por quê",
        "",
        f"- O estudo termina em **{corte.strftime('%d/%m/%Y')}**. Ativos, novatos, pirâmides e "
        "CCR/NCR vão até esse dia.",
        "- 2026 não é um ano do estudo: a coleta acaba antes do fim dele, e meio ano distorceria "
        "as taxas anuais.",
        "- Os eventos de 2026 servem para acompanhar quem já estava na população: dizem se a "
        "pessoa voltou, e com isso decidem quem saiu, quem pausou e quem pertence à população "
        "`passou_30_dias`.",
        "- A saída exige 12 meses sem contribuir depois da última contribuição (Avelino et al., "
        "ESEM 2019). A saída de 2025 aparece como as outras e pode estar um pouco alta: quem "
        "parou há menos de 12 meses do fim da coleta ainda pode voltar.",
        "- Até quando cada linguagem foi acompanhada (último evento coletado):",
        "",
        tabela_md(quadro),
        "",
        "- A taxa de saída por faixa de tempo de casa, a taxa padronizada, o SMR e os cenários "
        "usam só os anos com saída confirmada, até 2024.",
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
        secao_janela(base, p, ordem),
    ]
    destino = base / "RELATORIO.md"
    destino.write_text("\n".join(partes))
    print(f"relatório: {destino}")


if __name__ == "__main__":
    main()
