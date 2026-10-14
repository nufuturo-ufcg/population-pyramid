#!/usr/bin/env python
"""Métricas de vitalidade de uma linguagem (Plano de Experimento, RQ1 a RQ3).

Cada linha da tabela de variáveis dependentes do plano é uma função `metrica_*`
abaixo, com o que ela faz e a referência do cálculo. `main` roda as pedidas em
sequência: calcula, grava as tabelas (parquet e CSV) e só então desenha. Os
gráficos e o estilo deles ficam em `vitalidade_figuras.py` e `vitalidade_figuras.yaml`.

    uv run python scripts/vitalidade.py                              # todas, uma linguagem
    uv run python scripts/vitalidade.py --linguagem elixir
    uv run python scripts/vitalidade.py --metricas tamanho,cenarios  # só algumas
    uv run python scripts/vitalidade.py --comparativo                # as de várias linguagens
    uv run python scripts/vitalidade.py --set min_saidas=20          # troca um parâmetro
    uv run python scripts/vitalidade.py --so-figuras                 # redesenha do disco
    uv run python scripts/vitalidade.py --so-figuras --estilo tamanho.anual:titulo="Outro"
    uv run python scripts/vitalidade.py --lista                      # nomes e referências

Parâmetros do cálculo em `scripts/vitalidade.yaml`, estilo dos gráficos em
`scripts/vitalidade_figuras.yaml`. A régua (saída em 12 meses, faixas, passo anual)
mora em `src/pyramid/vitalidade.py`.

Carrega a coleta com `carga_compacta.py` (mesmos filtros de elegibilidade, bot e conta
apagada de `figuras_linguagem_bruta.py`, em pedaços). Grava, por linguagem, em
`~/Documents/pyramid-tmp/<linguagem>/` (`csv/`, `resultados/` e as figuras) e, no
comparativo, em `~/Documents/pyramid-tmp/geral/`. `resultados/` guarda as tabelas
de cada métrica em parquet: `--so-figuras` desenha a partir delas, sem reler os eventos.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import cached_property
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carga_compacta
import carga_fonte
import figuras_linguagem_bruta as fb
import vitalidade_figuras
import vitalidade_pacote
from pyramid import units, vitalidade
from vitalidade_figuras import FIGURAS, FIGURAS_PADRAO, carrega_estilo, desenha

PASTA = "vitalidade"
YAML = Path(__file__).parent / "vitalidade.yaml"


def _csv(df: pd.DataFrame, nome: str) -> None:
    caminho = fb._caminho_csv(f"{PASTA}/{nome}")
    df.to_csv(caminho, index=False)
    print(f"salvo: {caminho}")


# --- Registro de métricas e figuras ---------------------------------------------

Dados = dict[str, pd.DataFrame]
METRICAS: dict[str, Callable[[Any], Dados]] = {}
ESCOPO: dict[str, str] = {}
USA_PIPELINE: dict[str, bool] = {}
PADRAO: dict[str, bool] = {}


def metrica(
    nome: str, escopo: str = "linguagem", pipeline: bool = False, padrao: bool = True
) -> Callable[[Callable], Callable]:
    """Registra uma função como métrica do plano, pelo nome da linha da tabela.

    A função devolve as tabelas (nome -> DataFrame) que o runner grava em CSV.
    escopo    "linguagem" roda numa linguagem; "comparativo" compara `linguagens_rq2`
    pipeline  usa o pipeline trimestral do motor, que precisa dos eventos brutos
    padrao    falso tira a métrica da execução sem `--metricas`
    """

    def registra(funcao: Callable) -> Callable:
        METRICAS[nome] = funcao
        ESCOPO[nome] = escopo
        USA_PIPELINE[nome] = pipeline
        PADRAO[nome] = padrao
        FIGURAS.setdefault(nome, {})
        return funcao

    return registra


def _projecao_variante(
    ctx: Contexto, regra: vitalidade.RegraCenario, chave: str
) -> dict[str, pd.DataFrame]:
    """Backtest e projeção futura com uma regra de cenário. Devolve as tabelas, por nome."""
    pa, fim, p = ctx.pa, ctx.fim, ctx.p
    # O ano em que a coleta termina está pela metade: fica fora da projeção.
    ultimo = fim.year - 1
    partes = []
    futuros = []
    for teto in (False, True):
        partes.append(vitalidade.backtest(pa, fim, ultimo, teto, regra))
        f = vitalidade.projeta_futuro(pa, fim, ultimo, p.horizonte, teto, regra)
        f.insert(0, "teto", teto)
        futuros.append(f)
    bt = pd.concat(partes, ignore_index=True)
    futuro = pd.concat(futuros, ignore_index=True)
    resumo = vitalidade.resumo_backtest(bt)

    # O plano escolhe o mínimo de saídas olhando quantos anos válidos sobram por banda.
    saidas = vitalidade.saidas_por_banda(pa, fim)
    validos = pd.DataFrame({"banda": range(vitalidade.BANDAS)})
    for minimo in (10, 20):
        validos[f"anos_com_{minimo}_saidas"] = (saidas >= minimo).sum().to_numpy()
    pasta = f"cenarios-{chave}"
    return {
        f"{pasta}/projecao_anos_validos": validos,
        f"{pasta}/projecao_backtest": bt,
        f"{pasta}/projecao_resumo": resumo["abre"],
        f"{pasta}/projecao_wilcoxon": resumo["wilcoxon"],
        f"{pasta}/projecao_futuro": futuro,
    }


def _csv_geral(df: pd.DataFrame, nome: str) -> None:
    caminho = fb._caminho_geral(f"csv/{PASTA}/{nome}")
    df.to_csv(caminho, index=False)
    print(f"salvo: {caminho}")


# --- Parâmetros e contexto -----------------------------------------------------


@dataclass
class Parametros:
    """Os parâmetros do plano. Defaults em `vitalidade.yaml`, cada chave explicada lá."""

    min_saidas: int
    saidas_estavel: int
    teto: bool
    horizonte: int
    ano_pesos: int
    linguagens_rq2: list[str]
    anos_piramide: list[int]
    coortes_tabua: list[int]
    variantes: dict[str, list[Any]]
    motor: str
    limite_pandas_gb: float
    limite_bruto_gb: float
    memoria: str
    threads: int | None
    contar_linhas_brutas: bool
    processos: int
    populacao: str
    piramide_em_pct: bool
    piramide_lado: str
    ano_comparacao: int
    ano_base_indice: int
    carencia_anos: int
    rodadas_padronizacao: dict[str, list[str]]
    data_de_corte: str | None
    ccr_ncr_inatividade_meses: float
    ccr_ncr_novato_meses: float
    tabua_ate_anos: int


@dataclass
class Entrada:
    """De onde vêm os eventos desta execução e como usar o cache. Vale para `--linguagem`."""

    dados: str | None = None
    eventos: list[str] | None = None
    alvos: list[str] | None = None
    usar_cache: bool = True
    motor: str | None = None  # None usa `p.motor`


def carrega_parametros(sobrepostos: list[str]) -> Parametros:
    """Lê o yaml e aplica cada `chave=valor` de `--set` por cima."""
    valores = yaml.safe_load(YAML.read_text())
    for item in sobrepostos:
        chave, igual, texto = item.partition("=")
        if not igual or chave not in valores:
            raise SystemExit(f"--set {item!r}: use chave=valor, com chave de {YAML.name}.")
        valores[chave] = yaml.safe_load(texto)
    return Parametros(**valores)


# Sobe quando o filtro de eventos de `carrega_eventos` mudar: invalida todo cache.
VERSAO_CACHE = 3


def _selo_dos_dados(fonte: carga_fonte.Fonte, motor: str) -> dict[str, Any]:
    """Tamanho e data de cada arquivo de entrada. Mudou um byte, o cache perde a validade."""
    arquivos = {}
    for caminho in [a.caminho for a in fonte.eventos] + fonte.alvos:
        info = caminho.stat()
        arquivos[str(caminho)] = [info.st_size, info.st_mtime_ns]
    return {"versao": VERSAO_CACHE, "motor": motor, "arquivos": arquivos}


def escolhe_motor(p: Parametros, fonte: carga_fonte.Fonte, entrada: Entrada) -> str:
    """O motor pedido; em `auto`, pandas até `limite_pandas_gb` de eventos e duckdb acima."""
    motor = entrada.motor or p.motor
    if motor != "auto":
        return motor
    grande = fonte.bytes_de_eventos() > p.limite_pandas_gb * 1e9
    return "duckdb" if grande else "pandas"


def carrega_compactos(p: Parametros, fonte: carga_fonte.Fonte, entrada: Entrada) -> pd.DataFrame:
    """Eventos compactados da linguagem atual (`vitalidade.compacta`).

    Os CSV brutos têm GB e levam de minutos a horas para ler. O resultado compactado
    vai para `<saida>/cache/` e as execuções seguintes (outro `--set`, outra figura)
    leem dali, enquanto os arquivos de entrada não mudarem.
    """
    motor = escolhe_motor(p, fonte, entrada)
    pasta = Path(fb.TMP_BASE) / fb.LING.atual.slug / "cache"
    parquet = pasta / "vitalidade_eventos.parquet"
    arquivo_selo = pasta / "vitalidade_eventos.json"
    selo = _selo_dos_dados(fonte, motor)
    cache_valido = (
        entrada.usar_cache
        and parquet.exists()
        and arquivo_selo.exists()
        and json.loads(arquivo_selo.read_text()) == selo
    )
    if cache_valido:
        print(f"cache: {parquet}")
        return pd.read_parquet(parquet)
    print(
        f"carga: motor {motor}, {fonte.bytes_de_eventos() / 1e9:.1f} GB de eventos ({fonte.origem})"
    )
    eventos = carga_compacta.carrega(
        fonte,
        motor,
        trabalho=Path(fb.TMP_BASE) / fb.LING.atual.slug / "trabalho",
        memoria=p.memoria,
        threads=p.threads,
        contar_brutas=p.contar_linhas_brutas,
    )
    compactos = vitalidade.compacta(eventos)
    del eventos
    pasta.mkdir(parents=True, exist_ok=True)
    compactos.to_parquet(parquet, index=False)
    arquivo_selo.write_text(json.dumps(selo))
    return compactos


# A população não entra no título dos gráficos: ela já nomeia a pasta (`python-passou_30_dias`).
POPULACOES = ("todos", "codigo", "mais_de_um_dia")
PASSOU_DIAS = re.compile(r"passou_(\d+)_dias")


def rotulo_da_populacao(nome: str) -> str:
    """Texto que a população acrescenta ao título dos gráficos: nenhum. Valida o nome."""
    if nome not in POPULACOES and PASSOU_DIAS.fullmatch(nome) is None:
        raise SystemExit(f"populacao {nome!r}: use {list(POPULACOES)} ou passou_N_dias.")
    return ""


def fim_da_coleta(p: Parametros, ultimo_evento: pd.Timestamp) -> pd.Timestamp:
    """O fim do estudo: `data_de_corte`, que tem de ser fim de trimestre, ou o último evento."""
    if not p.data_de_corte:
        return ultimo_evento
    corte = pd.Timestamp(p.data_de_corte)
    if corte != corte + pd.offsets.QuarterEnd(0):
        raise SystemExit(f"data_de_corte {p.data_de_corte}: use o último dia de um trimestre.")
    return min(ultimo_evento, corte + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))


def aplica_populacao(p: Parametros) -> None:
    """Resultados e figuras de cada população ficam em pastas separadas: `python`, `python-codigo`.

    O cache dos eventos é um só (`<saída>/<linguagem>/cache`) e serve às duas.
    """
    rotulo = rotulo_da_populacao(p.populacao)
    sufixo = "" if p.populacao == "todos" else f"-{p.populacao}"
    fb.CFG.saida = fb.CFG.saida.with_name(f"{fb.LING.atual.slug}{sufixo}")
    fb.ESTADO_PASTA_GERAL.pasta = Path(fb.TMP_BASE) / f"geral{sufixo}"
    vitalidade_figuras.ESTADO.sufixo = rotulo


class Contexto:
    """Dados de uma linguagem, calculados uma vez e compartilhados pelas métricas.

    `bruto=True` guarda os eventos completos (com repositório), que o pipeline do
    motor exige. Sem ele só existem os eventos compactados, uma fração do tamanho.
    """

    def __init__(self, p: Parametros, slug: str, bruto: bool, entrada: Entrada):
        carga_fonte.aplica_linguagem(slug)
        fb.CFG.aplica(fb.RODADA)
        aplica_populacao(p)
        self.p = p
        self.eventos: pd.DataFrame | None = None
        fonte = carga_fonte.resolve_fonte(slug, entrada.dados, entrada.eventos, entrada.alvos)
        if bruto:
            if not fonte.cabe_no_carregador_original(p.limite_bruto_gb):
                raise SystemExit(
                    f"{slug}: {fonte.bytes_de_eventos() / 1e9:.0f} GB de eventos passam do "
                    f"limite de {p.limite_bruto_gb} GB do pipeline do motor (ccr_ncr, stickiness, "
                    "magnetismo), que lê tudo para a memória. Tire essas métricas ou aumente "
                    "limite_bruto_gb."
                )
            fb.CFG.dados = fonte.pasta_dados
            self.eventos = fb.carrega_eventos(fb.RODADA)
            self.compactos = vitalidade.compacta(self.eventos)
        else:
            self.compactos = carrega_compactos(p, fonte, entrada)
        # O corte vem antes da população: quem "voltou depois" só vale até o fim do estudo.
        self.fim = fim_da_coleta(p, self.compactos["timestamp"].max())
        self.compactos = vitalidade.ate_a_data(self.compactos, self.fim)
        achou = PASSOU_DIAS.fullmatch(p.populacao)
        if p.populacao == "codigo":
            self.compactos = vitalidade.so_quem_codou(self.compactos)
        elif p.populacao == "mais_de_um_dia":
            self.compactos = vitalidade.tira_pessoas_de_um_dia(self.compactos)
        elif achou is not None:
            self.compactos = vitalidade.so_quem_passou_de(self.compactos, int(achou.group(1)))
        pessoas = self.compactos["contributor_id"].nunique()
        print(
            f"{fb.LING.atual.nome}: {pessoas} pessoas, {len(self.compactos)} instantes "
            f"compactados, coleta até {self.fim.date()}"
        )
        self.pa = vitalidade.pessoa_ano(self.compactos, self.fim)
        self.anual = vitalidade.tabela_anual(self.pa, self.fim)
        self.dur = vitalidade.duracoes(self.compactos, self.fim)

    @cached_property
    def pipeline(self) -> SimpleNamespace:
        """Pipeline trimestral do motor (banda de 3 meses), montado só se alguém pedir."""
        if self.eventos is None:
            raise RuntimeError("pipeline exige Contexto(bruto=True).")
        return fb.roda_pipeline(self.eventos, band_months=3)


class ContextoComparativo:
    """Um `Contexto` por linguagem de `p.linguagens_rq2`."""

    def __init__(self, p: Parametros, bruto: bool, entrada: Entrada, principal: str):
        self.p = p
        self.por_lingua = {}
        for slug in p.linguagens_rq2:
            # `--dados` e `--eventos` valem para a linguagem principal; as outras vêm do yaml.
            da_linha = entrada if slug == principal else Entrada(usar_cache=entrada.usar_cache)
            da_linha.motor = entrada.motor
            self.por_lingua[slug] = Contexto(p, slug, bruto, da_linha)

    @cached_property
    def pipeline_conjunto(self) -> SimpleNamespace:
        """As linguagens numa fonte só, `idioma` dizendo a de cada linha (ver `monta_fonte`)."""
        partes = []
        for slug, lingua in self.por_lingua.items():
            ev = lingua.eventos.copy()
            ev["idioma"] = carga_fonte.LINGUAGENS[slug].nome
            partes.append(ev)
        return fb.roda_pipeline(pd.concat(partes, ignore_index=True), band_months=3)


# --- Resultados em disco e contexto leve ----------------------------------------

# Parâmetros que mudam as tabelas. Os outros (anos da pirâmide, `teto`, ...) só mudam o gráfico.
PARAMETROS_DO_CALCULO = (
    "min_saidas",
    "horizonte",
    "ano_pesos",
    "linguagens_rq2",
    "variantes",
    "carencia_anos",
    "rodadas_padronizacao",
    "data_de_corte",
    "tabua_ate_anos",
    "ano_base_indice",
    "ccr_ncr_inatividade_meses",
    "ccr_ncr_novato_meses",
)


def _raiz_resultados(escopo: str) -> Path:
    """Pasta das tabelas gravadas: por linguagem, ou a das comparações."""
    if escopo == "linguagem":
        raiz = fb.CFG.saida / "resultados" / PASTA
        raiz.mkdir(parents=True, exist_ok=True)
        return raiz
    return fb._caminho_geral(f"resultados/{PASTA}/meta.json").parent


def salva_tabelas(escopo: str, metrica_nome: str, dados: Dados) -> None:
    """Grava as tabelas da métrica em parquet, que guarda os tipos (período, categoria, data)."""
    pasta = _raiz_resultados(escopo) / metrica_nome
    for chave, tabela in dados.items():
        caminho = pasta / f"{chave}.parquet"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        tabela.to_parquet(caminho, index=False)
    print(f"resultados: {pasta}")


def carrega_tabelas(escopo: str, metrica_nome: str) -> Dados:
    pasta = _raiz_resultados(escopo) / metrica_nome
    arquivos = sorted(pasta.rglob("*.parquet"))
    if not arquivos:
        raise SystemExit(f"sem resultados de {metrica_nome!r} em {pasta}: rode sem --so-figuras.")
    dados = {}
    for arquivo in arquivos:
        chave = arquivo.relative_to(pasta).with_suffix("").as_posix()
        dados[chave] = pd.read_parquet(arquivo)
    return dados


def salva_meta(escopo: str, p: Parametros, fim: pd.Timestamp | None) -> None:
    """Grava o fim da coleta e os parâmetros que produziram as tabelas."""
    meta = {"fim": None if fim is None else str(fim), "parametros": asdict(p)}
    (_raiz_resultados(escopo) / "meta.json").write_text(json.dumps(meta, default=str))


class ContextoLeve:
    """O que os gráficos pedem do contexto, lido de `resultados/`: sem reler os eventos."""

    def __init__(self, p: Parametros, escopo: str, slug: str):
        carga_fonte.aplica_linguagem(slug)
        fb.CFG.aplica(fb.RODADA)
        aplica_populacao(p)
        self.p = p
        arquivo = _raiz_resultados(escopo) / "meta.json"
        if not arquivo.exists():
            raise SystemExit(f"sem resultados em {arquivo.parent}: rode sem --so-figuras.")
        meta = json.loads(arquivo.read_text())
        gravados = meta["parametros"]
        atuais = json.loads(json.dumps(asdict(p), default=str))
        diferem = [k for k in PARAMETROS_DO_CALCULO if gravados.get(k) != atuais[k]]
        if diferem:
            print(
                f"aviso: {diferem} mudaram desde que as tabelas foram gravadas; "
                "os gráficos usam as tabelas antigas. Rode sem --so-figuras para recalcular.",
                file=sys.stderr,
            )
        self.fim = pd.Timestamp(meta["fim"]) if meta["fim"] else None

    @cached_property
    def anual(self) -> pd.DataFrame:
        return carrega_tabelas("linguagem", "tamanho")["anual"]


# --- As métricas, na ordem da tabela de variáveis dependentes do plano ---------
# Cada uma devolve suas tabelas; o runner grava os CSV. Os gráficos de cada uma
# vêm logo depois, registrados com @figura e escolhidos com `--figuras`.


@metrica("tamanho")
def metrica_tamanho(ctx: Contexto) -> Dados:
    """Tamanho: crescimento natural por ano, natalidade e mortalidade. Responde RQ1.1.

    O que faz: (novatos - saídas) / ativos do ano, em %. Natalidade e mortalidade
    (nascimentos e óbitos sobre a população do período) saem por ano e por
    trimestre, com a mesma conta de fluxo.
    Referência: equação compensadora da demografia (IBGE, metodologia das
    projeções 1980-2050, https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf;
    PRB Population Handbook 2011). Novatos e saídas: Foucault et al., ESEC/FSE
    2015, https://doi.org/10.1145/2786805.2786870.
    """
    return {
        "anual": ctx.anual,
        "transicao_anual": vitalidade.fluxos(ctx.compactos, ctx.fim, "Y"),
        "transicao_trimestral": vitalidade.fluxos(ctx.compactos, ctx.fim, "Q"),
    }


@metrica("composicao")
def metrica_composicao(ctx: Contexto) -> Dados:
    """Composição: pirâmide por faixa de tempo de casa e índice de envelhecimento. Responde RQ1.2.

    O que faz: ativos por faixa (0-1, 1-2, 2-3, 3-5, 5-8, 8+ anos), com um lado
    para quem faz código e outro para quem só discute (moved é quem trocou de
    lado). Índice de envelhecimento = ativos com 5+ anos / ativos com 0-1 ano.
    Referência: pirâmide etária e índice de envelhecimento do IBGE
    (https://seriesestatisticas.ibge.gov.br/series.aspx?vcodigo=CD95);
    Hannemann e Klamma, OSS 2013, https://doi.org/10.1007/978-3-642-38928-3_6.
    """
    return {
        "composicao": vitalidade.composicao(ctx.pa),
        "composicao_trimestral": vitalidade.composicao_trimestral(ctx.pa),
        "indice_envelhecimento": vitalidade.indice_envelhecimento(ctx.pa),
    }


@metrica("retencao")
def metrica_retencao(ctx: Contexto) -> Dados:
    """Retenção: tábua de vida por coorte de entrada. Responde RQ1.3.

    O que faz: para cada coorte (ano de entrada) e cada ano de contribuição x,
    l(x) ainda ativos, d(x) saídas entre x e x+1, q(x) = d/l e e(x) tempo médio
    restante. Quem tem último evento a menos de 12 meses do fim da coleta é
    censurado (censura à direita).
    Referência: IBGE, Tábua Completa de Mortalidade 2023,
    https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf;
    Hannemann e Klamma, OSS 2013.
    """
    return {
        "tabua_coortes": vitalidade.tabuas_por_coorte(ctx.dur),
        "tabua_todas": vitalidade.tabua_de_vida(ctx.dur),
    }


@metrica("saida_por_faixa")
def metrica_saida_por_faixa(ctx: Contexto) -> Dados:
    """Saída por faixa: taxa de saída por faixa de tempo de casa. Responde RQ1.3.

    O que faz: saídas da faixa / ativos da faixa no ano, por (ano, faixa). O
    denominador é quem contribuiu no ano. Célula com menos de `saidas_estavel`
    saídas é marcada como instável. Ano sem 12 meses de coleta depois dele
    fica sem taxa.
    Referência: taxa de mortalidade por idade, o q(x) da tábua de vida (IBGE,
    https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf);
    mínimo de 20 óbitos do NCHS/CDC (CDC WONDER, Presentation Standards for
    Mortality Data, 2024).
    """
    return {"taxa_saida_faixa": vitalidade.taxa_saida_por_faixa(ctx.pa, ctx.fim)}


@metrica("cenarios")
def metrica_cenarios(ctx: Contexto) -> Dados:
    """Cenários futuros: projeção ingênua, coorte e cenários, com backtest. Responde RQ3.

    O que faz: pirâmide de T+1 em faixas de 1 ano (0 a 8+). Ingênuo repete a
    pirâmide de T. Coorte aplica a permanência do último par de anos e novatos
    igual à média dos dois últimos anos. Cenários usam o menor, o maior e a
    média dos dois da série histórica. Backtest de cada ano só com os anteriores,
    erro em ABRE, Wilcoxon entre métodos e cobertura do intervalo. Roda cada
    regra de `variantes` e as duas formas de teto.
    Referência: Onoue et al., IEICE16, https://doi.org/10.1587/transinf.2015EDP7363
    (ingênuo, coorte, ABRE, Wilcoxon); variantes de projeção da ONU (PRB,
    https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/)
    e do Ipea (Bonifácio e Guimarães, Texto para Discussão 2698, 2021).
    """
    tabelas = {}
    for chave, (_rotulo, janela, por_taxa) in ctx.p.variantes.items():
        regra = vitalidade.RegraCenario(ctx.p.min_saidas, janela, por_taxa)
        tabelas.update(_projecao_variante(ctx, regra, chave))
    return tabelas


def _ccr_ncr(p: Parametros, compactos: pd.DataFrame, fim: pd.Timestamp) -> pd.DataFrame:
    """CCR e NCR com a inatividade e o corte de novato do yaml, em meses."""
    return vitalidade.ccr_ncr_trimestral(
        compactos,
        inatividade_dias=p.ccr_ncr_inatividade_meses * vitalidade.DAYS_PER_MONTH,
        novato_dias=round(p.ccr_ncr_novato_meses * vitalidade.DAYS_PER_MONTH),
        fim=fim,
    )


@metrica("ccr_ncr")
def metrica_ccr_ncr(ctx: Contexto) -> Dados:
    """CCR e NCR: equilíbrio entre quem faz código e quem discute, novato e veterano. RQ1 e RQ2.

    O que faz: por trimestre, sobre quem contribuiu nos `ccr_ncr_inatividade_meses` (12, o limite
    de saída do Avelino) até o fim dele, CCR = (código - discussão) / o maior dos dois e NCR =
    (novatos - experientes) / o maior dos dois, ambos entre -1 e 1. Novato é quem tem até
    `ccr_ncr_novato_meses` (12, a janela da saída; o IEICE16 usa 3) de idade. O sinal dos dois
    classifica o trimestre nos tipos A a D. Mesma conta do motor, direto dos eventos compactados:
    roda no Python também. Com 3 e 3 reproduz o motor exatamente.
    Referência: Onoue et al., IEICE16, https://doi.org/10.1587/transinf.2015EDP7363.
    """
    return {"ccr_ncr": _ccr_ncr(ctx.p, ctx.compactos, ctx.fim)}


@metrica("ccr_ncr_comparado", escopo="comparativo")
def metrica_ccr_ncr_comparado(ctx: ContextoComparativo) -> Dados:
    """CCR e NCR das cinco linguagens no mesmo quadro. RQ1 e RQ2.

    O que faz: o `ccr_ncr` de cada linguagem de `linguagens_rq2`, empilhado, para os gráficos
    com todas juntas.
    Referência: Onoue et al., IEICE16, https://doi.org/10.1587/transinf.2015EDP7363.
    """
    partes = []
    for slug, lingua in ctx.por_lingua.items():
        t = _ccr_ncr(ctx.p, lingua.compactos, lingua.fim)
        t.insert(0, "slug", slug)
        partes.append(t)
    return {"ccr_ncr_comparado": pd.concat(partes, ignore_index=True)}


@metrica("stickiness", pipeline=True)
def metrica_stickiness(ctx: Contexto) -> Dados:
    """Stickiness: fração de quem contribuiu num ano e volta no ano seguinte. Responde RQ2.

    O que faz: stickiness por ano da linguagem. O magnetismo tem métrica própria
    (`magnetismo`), porque só tem sentido com as linguagens juntas. Usa o
    pipeline do motor (banda de 3 meses).
    Referência: Yamashita et al., MSR 2014, https://doi.org/10.1145/2597073.2597116;
    Ferreira, Silva e Valente, SBES 2020, https://doi.org/10.1145/3422392.3422433.
    """
    pl = ctx.pipeline
    pares, cobertura = pl.attractiveness.activity(scopes=[pl.sid])
    anual = pl.attractiveness.annual(pares, coverage_end=cobertura)
    return {"stickiness_ano": anual[anual["scope_id"] == pl.sid]}


@metrica("significancia", escopo="comparativo")
def metrica_significancia(ctx: ContextoComparativo) -> Dados:
    """Significância da diferença: Kaplan-Meier e log-rank entre linguagens. Responde RQ2.

    O que faz: curva de retenção S(t) por linguagem, com quem seguia ativo ao
    fim da coleta tratado como censura, e log-rank da primeira linguagem de
    `linguagens_rq2` contra cada uma das outras.
    Referência: Constantinou e Mens, Innovations in Systems and Software
    Engineering, 2017, https://doi.org/10.1007/s11334-017-0303-4.
    """
    curvas = []
    for slug, lingua in ctx.por_lingua.items():
        curvas.append(vitalidade.kaplan_meier(lingua.dur).assign(linguagem=slug))

    referencia = ctx.p.linguagens_rq2[0]
    testes = []
    for slug in ctx.p.linguagens_rq2[1:]:
        estatistica, p = vitalidade.logrank(
            ctx.por_lingua[referencia].dur, ctx.por_lingua[slug].dur
        )
        testes.append({"comparacao": f"{referencia} x {slug}", "estatistica": estatistica, "p": p})
    return {"kaplan_meier": pd.concat(curvas, ignore_index=True), "logrank": pd.DataFrame(testes)}


@metrica("tabua_comparada", escopo="comparativo")
def metrica_tabua_comparada(ctx: ContextoComparativo) -> Dados:
    """Tábua de vida de cada linguagem lado a lado, até `tabua_ate_anos`. Responde RQ1 e RQ2.

    O que faz: a tábua de vida de `retencao` (l, d, q, S, e) de todas as pessoas de cada linguagem,
    cortada em `tabua_ate_anos` de casa. e(x) é a vida restante de quem chegou a x. A chance de
    seguir mais t anos tendo chegado a x sai de l(x+t) / l(x), sem métrica à parte.
    Referência: IBGE, Tábua Completa de Mortalidade 2023,
    https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf.
    """
    tabelas = []
    for slug, lingua in ctx.por_lingua.items():
        t = vitalidade.tabua_de_vida(lingua.dur)
        t = t[t["x"] <= ctx.p.tabua_ate_anos].copy()
        t.insert(0, "linguagem", slug)
        tabelas.append(t)
    return {"tabua_comparada": pd.concat(tabelas, ignore_index=True)}


@metrica("comparacao_corrigida", escopo="comparativo")
def metrica_comparacao_corrigida(ctx: ContextoComparativo) -> Dados:
    """Comparação corrigida: taxa de saída padronizada por faixa e SMR. Responde RQ2.

    O que faz: taxa direta = soma de (taxa da faixa da linguagem x peso da faixa
    na população de referência). SMR = saídas reais / saídas esperadas, com as
    taxas da referência aplicadas à composição real. A referência de cada rodada
    de `rodadas_padronizacao` é a soma das linguagens dela em `ano_pesos`: uma rodada
    entre as de nicho (RQ2a) e outra do Clojure com o Python (RQ2b).
    Referência: Ahmad et al., Age Standardization of Rates: A New WHO Standard,
    OMS, 2001, https://cdn.who.int/media/docs/default-source/gho-documents/global-health-estimates/gpe_discussion_paper_series_paper31_2001_age_standardization_rates.pdf.
    """
    taxas = {}
    for slug, lingua in ctx.por_lingua.items():
        taxas[slug] = vitalidade.taxa_saida_por_faixa(lingua.pa, lingua.fim)
    rodadas = []
    for nome, linguagens in ctx.p.rodadas_padronizacao.items():
        da_rodada = {slug: taxas[slug] for slug in linguagens}
        rodadas.append(vitalidade.padronizacao(da_rodada, ctx.p.ano_pesos).assign(rodada=nome))
    return {"padronizacao": pd.concat(rodadas, ignore_index=True)}


@metrica("trajetoria", escopo="comparativo")
def metrica_trajetoria(ctx: ContextoComparativo) -> Dados:
    """Trajetória: tamanho, crescimento e composição de cada linguagem, lado a lado. Responde RQ2.

    O que faz: ativos por ano e o índice de ativos (100 em `ano_base_indice`), o crescimento
    líquido (novatos + voltas - saídas - pausas) / ativos, as taxas de saída e de volta em % dos
    ativos e a composição por faixa em % dos ativos do ano. O crescimento líquido do ano divide
    pelos ativos do próprio ano. Não é a variação sobre o ano anterior (ver `tabela_anual`).
    Linguagens de tamanhos muito diferentes (o Python tem mil vezes os ativos do Zig) só se
    comparam com o tamanho tirado: índice, taxas e composição em %.
    Referência: equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050,
    https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf);
    pirâmide etária em % da população (IBGE, https://seriesestatisticas.ibge.gov.br/series.aspx?vcodigo=CD95).
    """
    base = ctx.p.ano_base_indice
    trajetorias, composicoes = [], []
    for slug, lingua in ctx.por_lingua.items():
        t = lingua.anual.copy()
        t.insert(0, "slug", slug)
        t["saida_pct"] = 100 * t["saidas"] / t["ativos"]
        t["volta_pct"] = 100 * t["voltas"] / t["ativos"]
        t["novato_pct"] = 100 * t["novatos"] / t["ativos"]
        # Saída é definitiva, e quem parou há pouco ainda pode voltar: os últimos `carencia_anos`
        # anos são provisórios e saem tracejados.
        t["provisorio"] = t["ano"] > lingua.fim.year - ctx.p.carencia_anos
        ativos_na_base = t.set_index("ano")["ativos"].get(base)  # sem o ano base, sem índice
        t["indice"] = 100 * t["ativos"] / ativos_na_base if ativos_na_base else float("nan")
        trajetorias.append(t)
        c = vitalidade.composicao(lingua.pa)
        lados = vitalidade.LADOS
        total_do_ano = c[lados].sum(axis=1).groupby(c["ano"]).transform("sum")
        c[lados] = 100 * c[lados].div(total_do_ano, axis=0)
        c.insert(0, "slug", slug)
        composicoes.append(c)
    return {
        "trajetoria": pd.concat(trajetorias, ignore_index=True),
        "composicao_pct": pd.concat(composicoes, ignore_index=True),
    }


@metrica("magnetismo", escopo="comparativo", pipeline=True, padrao=False)
def metrica_magnetismo(ctx: ContextoComparativo) -> Dados:
    """Magnetismo: fração dos novatos do ano que escolheram cada linguagem. Responde RQ2.

    O que faz: novatos da linguagem no ano / novatos de todas as linguagens
    carregadas no ano, junto com a stickiness no mesmo quadro. O plano adia o
    uso: o denominador só representa o GitHub com todas as linguagens coletadas,
    e quem saiu para uma linguagem de fora da amostra não aparece. Por isso
    fica fora da execução padrão e roda só com `--metricas magnetismo`.
    Referência: Yamashita et al., MSR 2014, https://doi.org/10.1145/2597073.2597116;
    Ferreira, Silva e Valente, SBES 2020, https://doi.org/10.1145/3422392.3422433.
    """
    ids = {}
    for slug in ctx.p.linguagens_rq2:
        ids[units.id_da_linguagem(carga_fonte.LINGUAGENS[slug].nome)] = slug
    pl = ctx.pipeline_conjunto
    pares, cobertura = pl.attractiveness.activity(scopes=list(ids))
    anual = pl.attractiveness.annual(pares, coverage_end=cobertura)
    anual = anual[anual["scope_id"].isin(ids)].copy()
    anual.insert(0, "linguagem", anual["scope_id"].map(ids))
    colunas = ["linguagem", "year", "devs", "newcomers_here", "newcomers_total"]
    return {"magnetismo": anual[[*colunas, "magnetism", "stickiness"]]}


# --- Execução ------------------------------------------------------------------


def escolhe_figuras(pedido: str, nomes: list[str]) -> dict[str, list[str]]:
    """Traduz `--figuras` em {métrica: [figuras]}.

    `padrao` (as marcadas como padrão), `todas`, `nenhuma`, ou uma lista com
    `metrica` (todas as figuras dela) e `metrica.figura` (uma só).
    """
    escolha: dict[str, list[str]] = {nome: [] for nome in nomes}
    for item in pedido.split(","):
        nome_metrica, _, nome_figura = item.partition(".")
        if item not in ("padrao", "todas", "nenhuma"):
            existe = nome_metrica in FIGURAS and nome_figura in ("", *FIGURAS[nome_metrica])
            if not existe:
                raise SystemExit(f"--figuras {item!r}: veja as opções com --lista.")
        for nome in nomes:
            for fig in FIGURAS[nome]:
                if item == "todas":
                    quer = True
                elif item == "padrao":
                    quer = (nome, fig) in FIGURAS_PADRAO
                else:
                    quer = nome_metrica == nome and nome_figura in ("", fig)
                if quer and fig not in escolha[nome]:
                    escolha[nome].append(fig)
    return escolha


def _grava(escopo: str, chave: str, tabela: pd.DataFrame) -> None:
    if escopo == "linguagem":
        _csv(tabela, f"{chave}.csv")
    else:
        _csv_geral(tabela, f"{chave}.csv")


def _executa(
    nomes: list[str],
    ctx: Contexto | ContextoComparativo | ContextoLeve,
    escolha: dict,
    so_figuras: bool,
) -> None:
    """Para cada métrica: calcula, grava as tabelas e só então desenha as figuras escolhidas.

    Com `so_figuras`, lê as tabelas de `resultados/` em vez de calcular.
    """
    for nome in nomes:
        print(f"== {nome}")
        escopo = ESCOPO[nome]
        if so_figuras:
            dados = carrega_tabelas(escopo, nome)
        else:
            dados = METRICAS[nome](ctx)
            salva_tabelas(escopo, nome, dados)
            for chave, tabela in dados.items():
                _grava(escopo, chave, tabela)
        for fig in escolha[nome]:
            print(f"-- figura {nome}.{fig}")
            desenha(f"{nome}.{fig}", FIGURAS[nome][fig], ctx, dados)


def _sem_pipeline_se_grande(
    nomes: list[str], p: Parametros, slug: str, entrada: Entrada
) -> list[str]:
    """Tira da execução padrão o que exige `carrega_eventos` quando os eventos não cabem nele."""
    com_pipeline = [n for n in nomes if USA_PIPELINE[n] and ESCOPO[n] == "linguagem"]
    if not com_pipeline:
        return nomes
    fonte = carga_fonte.resolve_fonte(slug, entrada.dados, entrada.eventos, entrada.alvos)
    if fonte.cabe_no_carregador_original(p.limite_bruto_gb):
        return nomes
    print(
        f"aviso: {slug} tem {fonte.bytes_de_eventos() / 1e9:.0f} GB de eventos; "
        f"{com_pipeline} usam o pipeline do motor (tudo em memória) e ficam de fora. "
        "Peça com --metricas para forçar.",
        file=sys.stderr,
    )
    return [n for n in nomes if n not in com_pipeline]


def _so_com_resultados(nomes: list[str], slug: str, p: Parametros) -> list[str]:
    """Com `--so-figuras` e sem `--metricas`, desenha só o que tem resultado gravado."""
    carga_fonte.aplica_linguagem(slug)
    fb.CFG.aplica(fb.RODADA)
    aplica_populacao(p)
    com, sem = [], []
    for nome in nomes:
        tem = any((_raiz_resultados(ESCOPO[nome]) / nome).glob("*.parquet")) or any(
            (_raiz_resultados(ESCOPO[nome]) / nome).glob("*/*.parquet")
        )
        (com if tem else sem).append(nome)
    if sem:
        print(f"aviso: sem resultados gravados de {sem}; ficam de fora.", file=sys.stderr)
    return com


def roda(
    nomes: list[str],
    p: Parametros,
    slug: str,
    figuras: str,
    entrada: Entrada,
    so_figuras: bool,
) -> None:
    """Roda as métricas pedidas: as de uma linguagem primeiro, depois as comparativas."""
    escolha = escolhe_figuras(figuras, nomes)
    de_uma_linguagem = [n for n in nomes if ESCOPO[n] == "linguagem"]
    comparativas = [n for n in nomes if ESCOPO[n] == "comparativo"]

    if de_uma_linguagem:
        if so_figuras:
            ctx = ContextoLeve(p, "linguagem", slug)
        else:
            bruto = any(USA_PIPELINE[n] for n in de_uma_linguagem)
            ctx = Contexto(p, slug, bruto, entrada)
            salva_meta("linguagem", p, ctx.fim)
        _executa(de_uma_linguagem, ctx, escolha, so_figuras)
    if comparativas:
        if so_figuras:
            ctx_comparativo = ContextoLeve(p, "comparativo", slug)
        else:
            bruto = any(USA_PIPELINE[n] for n in comparativas)
            ctx_comparativo = ContextoComparativo(p, bruto, entrada, slug)
            salva_meta("comparativo", p, None)
        _executa(comparativas, ctx_comparativo, escolha, so_figuras)


def lista_metricas() -> None:
    for nome, funcao in METRICAS.items():
        padrao = "" if PADRAO[nome] else ", fora da execução padrão"
        print(f"{nome} ({ESCOPO[nome]}{padrao})\n{funcao.__doc__}")
        print("    figuras:")
        for fig, funcao_fig in FIGURAS[nome].items():
            marca = "*" if (nome, fig) in FIGURAS_PADRAO else " "
            print(f"    {marca} {nome}.{fig}: {funcao_fig.__doc__}")
        print()
    print("* = desenhada por padrão")


PADRAO_SAIDA = Path.home() / "Documents" / "pyramid-vitalidade"


def aplica_saida(base: Path) -> None:
    """Aponta as saídas de `figuras_linguagem_bruta` para `base`/<linguagem> e `base`/geral."""
    fb.TMP_BASE = base
    fb.PASTA_GERAL = base / "geral"
    fb.ESTADO_PASTA_GERAL.pasta = base / "geral"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--linguagem", default="clojure", choices=sorted(carga_fonte.LINGUAGENS))
    parser.add_argument(
        "--metricas", help=f"nomes separados por vírgula. Padrão: todas. Opções: {list(METRICAS)}"
    )
    parser.add_argument(
        "--figuras",
        default="padrao",
        help="padrao, todas, nenhuma, ou metrica / metrica.figura separados por vírgula",
    )
    parser.add_argument(
        "--comparativo",
        action="store_true",
        help="sem --metricas, roda as comparativas (várias linguagens) em vez das de uma",
    )
    parser.add_argument(
        "--set", dest="sobrepostos", action="append", default=[], metavar="CHAVE=VALOR"
    )
    entrada = parser.add_argument_group("entrada: de onde ler os eventos (nada é movido)")
    entrada.add_argument("--dados", help="pasta com os eventos e o alvo da linguagem")
    entrada.add_argument(
        "--eventos", action="append", help="arquivo de eventos (repetível); o papel vem do nome"
    )
    entrada.add_argument("--alvo", action="append", help="arquivo-alvo (repetível)")
    entrada.add_argument("--motor", help="pandas, duckdb ou auto (padrão do yaml)")
    entrada.add_argument("--sem-cache", action="store_true", help="relê os eventos brutos")
    saida = parser.add_argument_group("saída")
    saida.add_argument(
        "--saida",
        default=os.environ.get("PYRAMID_SAIDA", str(PADRAO_SAIDA)),
        help=f"pasta de resultados e figuras (padrão {PADRAO_SAIDA}; env PYRAMID_SAIDA)",
    )
    saida.add_argument(
        "--so-figuras",
        action="store_true",
        help="desenha a partir de resultados/, sem recalcular nem reler os eventos",
    )
    saida.add_argument(
        "--estilo",
        action="append",
        default=[],
        metavar="FIGURA:OPCAO=VALOR",
        help="sobrepõe uma opção de vitalidade_figuras.yaml (global:dpi=300)",
    )
    saida.add_argument(
        "--empacota",
        nargs="?",
        const="",
        metavar="ARQUIVO",
        help="junta os resultados num .tar.gz (padrão: dentro de --saida) e termina",
    )
    saida.add_argument("--importa", metavar="PACOTE", help="abre um .tar.gz em --saida e termina")
    parser.add_argument(
        "--lista", action="store_true", help="mostra métricas, figuras, referências"
    )
    args = parser.parse_args()
    if args.lista:
        lista_metricas()
        return
    base = Path(args.saida).expanduser()
    aplica_saida(base)
    if args.importa:
        vitalidade_pacote.importa(Path(args.importa).expanduser(), base)
        return
    if args.empacota is not None:
        destino = Path(args.empacota).expanduser() if args.empacota else None
        vitalidade_pacote.empacota(base, destino)
        return

    if args.metricas:
        nomes = args.metricas.split(",")
        desconhecidas = [n for n in nomes if n not in METRICAS]
        if desconhecidas:
            parser.error(f"métrica desconhecida: {desconhecidas}. Opções: {list(METRICAS)}")
    elif args.figuras not in ("padrao", "todas", "nenhuma"):
        # `--figuras tamanho.anual` sozinho pede só a métrica dona do gráfico.
        nomes = []
        for item in args.figuras.split(","):
            nome_metrica = item.partition(".")[0]
            if nome_metrica in METRICAS and nome_metrica not in nomes:
                nomes.append(nome_metrica)
    else:
        escopo = "comparativo" if args.comparativo else "linguagem"
        nomes = [n for n in METRICAS if ESCOPO[n] == escopo and PADRAO[n]]
    p = carrega_parametros(args.sobrepostos)
    carrega_estilo(args.estilo)
    de_entrada = Entrada(args.dados, args.eventos, args.alvo, not args.sem_cache, args.motor)
    if not args.metricas and not args.so_figuras:
        nomes = _sem_pipeline_se_grande(nomes, p, args.linguagem, de_entrada)
    if not args.metricas and args.so_figuras:
        nomes = _so_com_resultados(nomes, args.linguagem, p)
    roda(nomes, p, args.linguagem, args.figuras, de_entrada, args.so_figuras)


if __name__ == "__main__":
    main()
