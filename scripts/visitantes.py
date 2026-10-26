"""Visitantes: quem participou da linguagem numa ocasião só. Uma análise olhando para eles.

Ocasião é uma conversa (issue ou PR), um commit comentado ou um dia de commits num repositório
(`carga_duckdb._ocasiao`). Visitante é quem tem uma ocasião só na vida; residente, quem tem duas ou
mais (a população `mais_de_uma_ocasiao`).

    uv run python scripts/visitantes.py --saida ~/pyramid-vitalidade-saida \\
        --linguagens clojure elixir ocaml zig python

Lê `<saída>/<linguagem>/origem/` (de `scripts/origem_dos_novatos.py`) e grava em
`<saída>/geral-visitantes/`:

  - `visitantes_por_ano.csv`: chegadas, visitantes e % de visitantes por ano de chegada;
  - `visitantes_por_tipo.csv`: o mesmo pelo tipo do primeiro evento;
  - `portas_de_entrada.csv`: os repositórios por onde mais chegam visitantes;
  - `visitantes_por_ano.png` e `visitantes_por_tipo.png`;
  - com `--evento clojure=2020-07-23`: `onda_do_evento.csv` e `chegadas_por_mes_<linguagem>.png`.

A onda de novatos segue Pinto et al. (EMSE 2018): chegadas por mês e quantas não voltam em quatro
janelas em volta do evento (do começo até 6 meses antes, 6 meses antes, 6 meses depois e o resto).

Quem chegou nos 12 meses antes do fim da coleta ainda pode voltar, então só entram anos de
chegada inteiros com 12 meses de folga, a mesma regra da saída.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import carga_fonte
from pyramid import plots

COLUNAS = ["primeiro", "ultimo", "codigo_do_primeiro", "tipo_do_primeiro", "codou", "ocasioes"]
MINIMO_DE_CHEGADAS = 100
TIPOS = ["issues", "issue_comments", "issue_events", "pull_requests", "commits"]
ROTULO_TIPO = {
    "issues": "abriu issue",
    "issue_comments": "comentou issue",
    "issue_events": "ação em issue",
    "pull_requests": "abriu PR",
    "commits": "commit",
}


def ultimo_ano_com_folga(pessoas: pd.DataFrame) -> int:
    """Último ano de chegada em que todos tiveram 12 meses para voltar."""
    fim = pessoas["ultimo"].max()
    return (fim - pd.Timedelta(days=365)).year - 1


def marca_visitantes(pessoas: pd.DataFrame) -> pd.DataFrame:
    """Ano de chegada e se a pessoa é visitante, só nos anos com folga."""
    ano_max = ultimo_ano_com_folga(pessoas)
    p = pessoas.assign(ano=pessoas["primeiro"].dt.year, visitante=pessoas["ocasioes"] == 1)
    return p[p["ano"] <= ano_max]


def por_ano(p: pd.DataFrame) -> pd.DataFrame:
    """Chegadas, visitantes e visitantes que só discutiram, por ano de chegada."""
    linhas = []
    for ano, grupo in p.groupby("ano"):
        visitantes = grupo[grupo["visitante"]]
        linhas.append(
            {
                "ano": ano,
                "chegadas": len(grupo),
                "visitantes": len(visitantes),
                "visitantes_so_discussao": int((~visitantes["codou"]).sum()),
                "pct_visitantes": 100 * len(visitantes) / len(grupo),
            }
        )
    return pd.DataFrame(linhas)


def por_tipo(p: pd.DataFrame) -> pd.DataFrame:
    """Chegadas e % de visitantes pelo tipo do primeiro evento."""
    linhas = []
    for tipo, grupo in p.groupby("tipo_do_primeiro"):
        linhas.append(
            {
                "tipo_do_primeiro": tipo,
                "chegadas": len(grupo),
                "visitantes": int(grupo["visitante"].sum()),
                "pct_visitantes": 100 * grupo["visitante"].mean(),
            }
        )
    return pd.DataFrame(linhas)


def portas_de_entrada(p: pd.DataFrame, repos: pd.DataFrame, quantos: int = 10) -> pd.DataFrame:
    """Os repositórios que mais recebem visitantes, com a parte deles no total da linguagem."""
    total_visitantes = int(p["visitante"].sum())
    linhas = []
    for codigo, grupo in p.groupby("codigo_do_primeiro"):
        visitantes = int(grupo["visitante"].sum())
        linhas.append(
            {
                "codigo": codigo,
                "chegadas": len(grupo),
                "visitantes": visitantes,
                "pct_dos_visitantes_da_linguagem": 100 * visitantes / total_visitantes,
                "pct_visitantes_no_repo": 100 * visitantes / len(grupo),
            }
        )
    tabela = pd.DataFrame(linhas).sort_values("visitantes", ascending=False).head(quantos)
    nomes = repos[["codigo", "repo_name"]]
    return tabela.merge(nomes, on="codigo", how="left")


def janelas_do_evento(p: pd.DataFrame, data: pd.Timestamp) -> pd.DataFrame:
    """Chegadas por mês e % de visitantes nas quatro janelas de Pinto et al. em volta do evento."""
    seis_meses = pd.DateOffset(months=6)
    fim = pd.Timestamp(year=int(p["ano"].max()) + 1, month=1, day=1)
    janelas = [
        ("do começo até 6 meses antes", p["primeiro"].min().normalize(), data - seis_meses),
        ("6 meses antes", data - seis_meses, data),
        ("6 meses depois", data, data + seis_meses),
        ("depois disso", data + seis_meses, fim),
    ]
    linhas = []
    for nome, inicio, fim_da_janela in janelas:
        grupo = p[(p["primeiro"] >= inicio) & (p["primeiro"] < fim_da_janela)]
        meses = (fim_da_janela - inicio) / pd.Timedelta(days=365.25 / 12)
        linhas.append(
            {
                "janela": nome,
                "inicio": inicio.date(),
                "fim": fim_da_janela.date(),
                "chegadas": len(grupo),
                "chegadas_por_mes": len(grupo) / meses,
                "pct_visitantes": 100 * grupo["visitante"].mean(),
            }
        )
    return pd.DataFrame(linhas)


def figura_por_mes(p: pd.DataFrame, slug: str, data: pd.Timestamp, pasta: Path) -> None:
    p = p[p["ano"] >= 2012]
    por_mes = p.groupby(p["primeiro"].dt.to_period("M"))["visitante"].agg(["size", "sum"])
    meses = por_mes.index.to_timestamp()
    fig, ax = plt.subplots(figsize=(12, 5.4))
    plots._theme(ax)
    cor = carga_fonte.cor_da_linguagem(slug)
    ax.plot(meses, por_mes["size"], color=cor, linewidth=2.5, label="chegadas")
    ax.plot(
        meses,
        por_mes["sum"],
        color=cor,
        linewidth=2.5,
        linestyle="--",
        label="das quais visitantes",
    )
    ax.axvline(data, color="#222222", linestyle=":", linewidth=1.5)
    ax.text(data, por_mes["size"].max(), f" evento ({data.date()})", fontsize=12, va="top")
    ax.set_ylim(bottom=0)
    ax.tick_params(labelsize=12)
    ax.set_ylabel("pessoas por mês", fontsize=13)
    ax.set_title(
        f"{carga_fonte.LINGUAGENS[slug].nome}: quem chega na linguagem a cada mês", fontsize=16
    )
    ax.legend(frameon=False, fontsize=12, loc="upper left")
    fig.tight_layout()
    fig.savefig(pasta / f"chegadas_por_mes_{slug}.png", dpi=200)
    plt.close(fig)


def figura_por_ano(tabelas: dict[str, pd.DataFrame], pasta: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.4))
    plots._theme(ax)
    for slug, tabela in tabelas.items():
        # Ano com poucas chegadas vira ruído na porcentagem (Zig tem 2 chegadas em 2015).
        t = tabela[(tabela["ano"] >= 2012) & (tabela["chegadas"] >= MINIMO_DE_CHEGADAS)]
        ax.plot(
            t["ano"],
            t["pct_visitantes"],
            color=carga_fonte.cor_da_linguagem(slug),
            linewidth=3,
            marker="o",
            markersize=5,
            label=carga_fonte.LINGUAGENS[slug].nome,
        )
    ax.set_ylim(0, 100)
    ax.tick_params(labelsize=12)
    ax.set_ylabel("% das chegadas do ano", fontsize=13)
    ax.set_title(
        "Quem chega e participa numa ocasião só (visitantes), anos com 100 chegadas ou mais",
        fontsize=15,
    )
    ax.legend(frameon=False, fontsize=12, ncol=5, loc="lower center")
    fig.tight_layout()
    fig.savefig(pasta / "visitantes_por_ano.png", dpi=200)
    plt.close(fig)


def figura_por_tipo(tabelas: dict[str, pd.DataFrame], pasta: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 5.4))
    plots._theme(ax)
    largura = 0.8 / len(tabelas)
    for i, (slug, tabela) in enumerate(tabelas.items()):
        t = tabela.set_index("tipo_do_primeiro").reindex(TIPOS)
        posicoes = []
        for j in range(len(TIPOS)):
            posicoes.append(j + i * largura - 0.4 + largura / 2)
        ax.bar(
            posicoes,
            t["pct_visitantes"],
            width=largura,
            color=carga_fonte.cor_da_linguagem(slug),
            label=carga_fonte.LINGUAGENS[slug].nome,
        )
    rotulos = []
    for tipo in TIPOS:
        rotulos.append(ROTULO_TIPO[tipo])
    ax.set_xticks(range(len(TIPOS)))
    ax.set_xticklabels(rotulos, fontsize=12)
    ax.set_ylim(0, 100)
    ax.tick_params(axis="y", labelsize=12)
    ax.set_ylabel("% que não voltou", fontsize=13)
    ax.set_title("Visitantes pela primeira coisa que a pessoa fez na linguagem", fontsize=16)
    ax.legend(frameon=False, fontsize=12, ncol=5, loc="upper center")
    fig.tight_layout()
    fig.savefig(pasta / "visitantes_por_tipo.png", dpi=200)
    plt.close(fig)


def main() -> None:
    """Lê a origem de cada linguagem e grava as tabelas e as figuras dos visitantes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", required=True, type=Path)
    parser.add_argument(
        "--linguagens", nargs="+", required=True, choices=sorted(carga_fonte.LINGUAGENS)
    )
    parser.add_argument("--evento", nargs="*", default=[], help="linguagem=AAAA-MM-DD")
    args = parser.parse_args()
    eventos = {}
    for texto in args.evento:
        slug, data = texto.split("=")
        if slug not in args.linguagens:
            parser.error(f"--evento {texto}: {slug} não está em --linguagens")
        eventos[slug] = pd.Timestamp(data)
    saida = args.saida.expanduser()
    pasta = saida / "geral-visitantes"
    pasta.mkdir(parents=True, exist_ok=True)

    anos = {}
    tipos = {}
    portas = []
    ondas = []
    for slug in args.linguagens:
        origem = saida / slug / "origem"
        pessoas = pd.read_parquet(origem / "pessoas.parquet", columns=COLUNAS)
        p = marca_visitantes(pessoas)
        anos[slug] = por_ano(p)
        tipos[slug] = por_tipo(p)
        repos = pd.read_parquet(origem / "repos.parquet")
        portas.append(portas_de_entrada(p, repos).assign(linguagem=slug))
        if slug in eventos:
            data = eventos[slug]
            ondas.append(janelas_do_evento(p, data).assign(linguagem=slug, evento=data.date()))
            figura_por_mes(p, slug, data, pasta)

    linhas_ano = []
    linhas_tipo = []
    for slug in args.linguagens:
        linhas_ano.append(anos[slug].assign(linguagem=slug))
        linhas_tipo.append(tipos[slug].assign(linguagem=slug))
    pd.concat(linhas_ano).to_csv(pasta / "visitantes_por_ano.csv", index=False)
    pd.concat(linhas_tipo).to_csv(pasta / "visitantes_por_tipo.csv", index=False)
    pd.concat(portas).to_csv(pasta / "portas_de_entrada.csv", index=False)
    if ondas:
        pd.concat(ondas).to_csv(pasta / "onda_do_evento.csv", index=False)
    figura_por_ano(anos, pasta)
    figura_por_tipo(tipos, pasta)
    print(pasta)


if __name__ == "__main__":
    main()
