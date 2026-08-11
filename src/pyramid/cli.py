"""CLI: um subcomando por estágio, na ordem em que rodam.

Cada estágio é retomável: sem `--force`, unidades já registradas como ok no
manifesto (`output/<estágio>/_manifest.json`) são puladas.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import typer

from . import logging_config as runlog
from .config import settings

if TYPE_CHECKING:
    from collections.abc import Callable

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Pirâmides de população de projetos OSS, replicação Onoue et al.",
)
log = logging.getLogger(__name__)

# Ordem canônica dos estágios de escrita. `validate` e `plot` leem, não escrevem.
STAGE_ORDER = [
    "extract",
    "classify",
    "snapshots",
    "metrics",
    "attractiveness",
    "projection",
    "plots",
]


def _module(stage: str) -> ModuleType:
    from importlib import import_module

    return import_module(f".{stage}", __package__)


def _resolve(project: str, nomes: dict[int, str]) -> int:
    """Resolve id ou sufixo do nome. Nome ambíguo aborta com a lista de candidatos."""
    if project.isdigit():
        pid = int(project)
        if pid not in nomes:
            raise typer.BadParameter(f"projeto {pid} não está no escopo de {len(nomes)} raízes")
        return pid

    hits = [s for s, n in nomes.items() if n.lower().endswith(project.lower())]
    if not hits:
        raise typer.BadParameter(f"nenhum projeto casa com {project!r}")
    if len(hits) > 1:
        lista = ", ".join(f"{s}={nomes[s]}" for s in sorted(hits))
        raise typer.BadParameter(f"{project!r} é ambíguo: {lista}. Use o ID.")
    return hits[0]


def _scopes(project: str | None, project_all: bool) -> list[int] | None:
    """Escopo de um estágio de escrita: resolve contra o banco, que é a fonte."""
    if project_all or project is None:
        return None
    from .extract import source

    src = source()
    ids = src.list_scopes()
    return [_resolve(project, {s: src.scope_label(s) for s in ids})]


@app.callback()
def main(log_level: str = typer.Option("INFO", "--log-level")) -> None:
    """Pipeline de replicação das pirâmides de população (IEICE16 e ESEM14)."""
    p = runlog.setup(log_level)
    log.debug("log desta execução: %s", p)


def _stage_command(stage: str, help_text: str) -> Callable[..., None]:
    @app.command(stage.replace("_", "-"), help=help_text)
    def _cmd(
        project: str = typer.Option(None, "--project", help="id ou nome de um projeto só"),
        project_all: bool = typer.Option(False, "--project-all", help="todos os projetos"),
        force: bool = typer.Option(False, "--force", help="ignora o manifesto e reprocessa"),
        fail_fast: bool = typer.Option(False, "--fail-fast", help="aborta no primeiro erro"),
    ) -> None:
        _module(stage).run(_scopes(project, project_all), force=force, fail_fast=fail_fast)

    return _cmd


_stage_command("extract", "Estágio 1: eventos crus por projeto/contribuidor.")
_stage_command("classify", "Estágio 2: init_c/init_d, spans de atividade.")
_stage_command("snapshots", "Estágio 3: pirâmides trimestrais (banda de 3 meses).")
_stage_command("metrics", "Estágio 4: CCR, NCR e Tipos A-D.")
_stage_command("attractiveness", "Estágio 5: magnetismo e stickiness anuais (seção 3.1).")
_stage_command("projection", "Estágio 6: projeção coorte-componente (IEICE16 seção 4).")


@app.command("run-all")
def run_all(
    from_stage: str = typer.Option(None, "--from-stage", help="retoma a partir deste estágio"),
    force: bool = typer.Option(False, "--force"),
    fail_fast: bool = typer.Option(False, "--fail-fast"),
) -> None:
    """Pipeline inteiro, na ordem, parando no primeiro estágio que falhar."""
    start = STAGE_ORDER.index(from_stage) if from_stage else 0
    for stage in STAGE_ORDER[start:]:
        log.info("=== %s ===", stage)
        man = _module(stage).run(None, force=force, fail_fast=fail_fast)
        if man.get("failed"):
            raise typer.Exit(1)


@app.command("types")
def types(
    snapshot: str = typer.Option(None, "--snapshot", help="default: o da classificação"),
) -> None:
    """Tabela dos Tipos A-D num snapshot: o equivalente da Fig.5 do IEICE16."""
    from .metrics import table

    t = snapshot or settings()["snapshots"]["classification_snapshot"]
    df = table(t)
    if df.empty:
        typer.echo(f"sem métricas em {t}; rode `pyramid metrics` antes.")
        raise typer.Exit(1)

    counts = df["type"].value_counts(dropna=False).to_dict()
    for _, r in df.iterrows():
        typer.echo(
            f"{r['type'] or '-':>2}  {r['project']:<34} "
            f"CCR {r['ccr']:+.3f}  NCR {r['ncr']:+.3f}  "
            f"cod {r['coding']:>4} / non {r['non_coding']:>4}  "
            f"new {r['new']:>4} / exp {r['experienced']:>4}"
        )
    resumo = "  ".join(f"{k}={counts.get(k, 0)}" for k in ["A", "B", "C", "D"])
    typer.echo(f"\n{t}: {resumo}  total={len(df)}")


def _plot_list() -> None:
    """Imprime o catálogo de figuras com a primeira linha do docstring de cada."""
    from . import plots

    for nome, fn in plots.FIGURES.items():
        typer.echo(f"{nome:<28} {(fn.__doc__ or '').splitlines()[0]}")
    typer.echo(f"{plots.SINGLE:<28} Pirâmide avulsa de um projeto (exige --project).")


def _plot_kwargs(
    figure: str, year: int | None, highlight: str | None, snapshot: str | None
) -> dict:
    """Traduz as opções da CLI para os argumentos da figura pedida.

    Opção que não vale para a figura escolhida aborta com mensagem. Passar
    `--highlight` numa figura sem anel seria um pedido que a saída ignora em
    silêncio, e o usuário só descobriria olhando o PNG.
    """
    from . import plots

    kw: dict = {}
    if figure == "magnet-sticky" and year:
        kw["year"] = year
    if highlight is not None:
        if figure not in ("magnet-sticky", "type-scatter"):
            raise typer.BadParameter(
                "--highlight só vale para --figure magnet-sticky ou type-scatter"
            )
        # Mesmo `_resolve` do resto da CLI: aceita nome de projeto e aborta em
        # nome ambíguo. Anelar o escopo errado calado seria pior.
        lbl = plots.labels()
        kw["highlight"] = [_resolve(p.strip(), lbl) for p in highlight.split(",") if p.strip()]
    if figure == "type-scatter" and snapshot:
        kw["snapshot"] = snapshot
    return kw


@app.command("plot")
def plot(
    figure: str = typer.Option("all", "--figure", help="nome da figura, ou 'all'"),
    project: str = typer.Option(None, "--project", help="só para --figure pyramid-single"),
    snapshot: str = typer.Option(None, "--snapshot", help="data; default: o da classificação"),
    year: int = typer.Option(None, "--year", help="só para --figure magnet-sticky"),
    highlight: str = typer.Option(
        None,
        "--highlight",
        help="só para --figure magnet-sticky ou type-scatter: projetos a anelar "
        "(nome ou id, separados por vírgula); default vem de "
        "checkpoints.figures",
    ),
    listar: bool = typer.Option(False, "--list", help="lista as figuras e sai"),
) -> None:
    """Figuras dos artigos. Lê apenas os parquets já gerados pelo pipeline."""
    from . import plots

    if listar:
        _plot_list()
        return

    if figure == plots.SINGLE:
        if not project:
            raise typer.BadParameter(f"--figure {plots.SINGLE} exige --project")
        sid = _resolve(project, plots.labels())
        typer.echo(plots.figure_pyramid(sid, snapshot))
        return

    if figure != "all" and figure not in plots.FIGURES:
        raise typer.BadParameter(
            f"figura desconhecida: {figure}. Use --list para ver as disponíveis."
        )

    kw = _plot_kwargs(figure, year, highlight, snapshot)
    if figure != "all" and kw:
        try:
            typer.echo(plots.FIGURES[figure](**kw))
        except ValueError as e:
            # Projeto que existe nas 90 raízes e não é elegível no ano pedido
            # configura erro de uso. Mensagem curta serve melhor que traceback.
            raise typer.BadParameter(str(e)) from e
        return

    man = plots.run(figures=None if figure == "all" else [figure])
    for nome, arq in man["ok"].items():
        typer.echo(f"{nome:<28} {arq}")
    for nome, err in man["failed"].items():
        typer.echo(f"{nome:<28} FALHOU: {err}")
    if man["failed"]:
        raise typer.Exit(1)


@app.command("magnetism")
def magnetism(
    year: int = typer.Option(None, "--year", help="default: o ano do snapshot de classificação"),
) -> None:
    """Quadrantes magnetismo × stickiness de um ano: a Fig.3 em texto."""
    from . import attractiveness as attr

    y = year or attr.year_of(settings()["snapshots"]["classification_snapshot"])
    df = attr.table(y)
    if df.empty:
        typer.echo(f"sem attractiveness em {y}; rode `pyramid attractiveness` antes.")
        raise typer.Exit(1)

    elegiveis = df[df["eligible"]]
    if elegiveis.empty:
        typer.echo(f"{y}: nenhum projeto passou do corte de devs ativos.")
        raise typer.Exit(1)

    for _, r in elegiveis.sort_values("magnetism", ascending=False).iterrows():
        typer.echo(
            f"{r['quadrant']:<12} {r['project']:<34} "
            f"mag {r['magnetism']:.4f}  stk {r['stickiness']:.4f}  "
            f"ativos {r['devs']:>4}  novos {r['newcomers_here']:>4}"
        )

    counts = elegiveis["quadrant"].value_counts().to_dict()
    resumo = "  ".join(
        f"{q}={counts.get(q, 0)}" for q in ["attractive", "floating", "stagnant", "terminal"]
    )
    fora = len(df) - len(elegiveis)
    typer.echo(f"\n{y}: {resumo}  elegíveis={len(elegiveis)}  fora do corte={fora}")


@app.command("validate")
def validate(
    group: str = typer.Option(None, "--group", help="types | attractiveness | projection"),
    verbose: bool = typer.Option(
        False, "--verbose", help="mostra também os checks informativos que batem"
    ),
    report: Path = typer.Option(None, "--report", help="grava o relatório completo em markdown"),
) -> None:
    """Confere a replicação inteira contra config/checkpoints.yaml.

    Sai com código 1 se houver divergência não declarada em `known_divergences:`,
    ou divergência declarada que voltou a bater, porque nesse caso é
    docs/replicacao/discrepancias.md que está mentindo.
    """
    from . import validate as v

    try:
        rep = v.run([group] if group else None)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from e

    largura = max((len(c.key) for c in rep.checks), default=10)
    grupo_atual = None
    for c in rep.checks:
        if not verbose and c.status == "ok" and not c.gate:
            continue
        if c.grupo != grupo_atual:
            grupo_atual = c.grupo
            typer.echo(f"\n--- {grupo_atual} ---")
        marca = {v.OK: " ", v.CONHECIDA: "~", v.FALHA: "!", v.OBSOLETA: "?", v.INDISPONIVEL: "-"}
        linha = (
            f"{marca.get(c.status, ' ')} {c.key:<{largura}}  {c.fonte:<7} "
            f"esperado {v._fmt(c.esperado):>18}  obtido {v._fmt(c.obtido):>18}  {c.status}"
        )
        extra = "  ".join(x for x in (c.nota, c.ref) if x)
        typer.echo(linha + (f"\n{' ' * (largura + 4)}{extra}" if extra else ""))

    if report:
        # Antes do Exit(1): o relatório vale mais quando algo falhou, seria
        # perverso só gerá-lo no caminho feliz.
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(rep.markdown())
        typer.echo(f"\nrelatório: {report}")

    cont = rep.contagem()
    resumo = "  ".join(f"{k}={n}" for k, n in sorted(cont.items()))
    informativos = sum(1 for c in rep.checks if not c.gate)
    typer.echo(
        f"\n{len(rep.checks)} checks ({len(rep.checks) - informativos} gate, "
        f"{informativos} informativos):  {resumo}"
    )
    if rep.falhas:
        typer.echo(
            "\nDivergência não declarada (!) ou obsoleta (?). Analise, corrija ou "
            "declare em `known_divergences:` apontando a seção de docs/replicacao/discrepancias.md."
        )
        raise typer.Exit(1)
    typer.echo("\nO repositório está no estado que a documentação descreve.")
