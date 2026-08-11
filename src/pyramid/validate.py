"""Estágio final: confere a replicação inteira contra `config/checkpoints.yaml`.

Cada checkpoint vira uma linha: de onde vem o número esperado (artigo ou trava
da replicação), o valor esperado, o obtido e o veredito.

A regra que dá sentido ao comando: **divergência precisa estar declarada**. O
bloco `known_divergences:` do yaml mapeia a chave do check para a seção de
`docs/discrepancias.md` que a explica. Daí saem os dois vereditos que importam:

* divergência não declarada é **FALHA**: apareceu algo que ninguém analisou;
* divergência declarada que voltou a bater é **OBSOLETA**: o documento
  descreve um problema que não existe mais, e ficar assim é pior do que a
  divergência original, porque a próxima pessoa lê uma explicação falsa.

Uma chave terminada em `.*` declara um *grupo* (as 40 células da Tabela 3, por
exemplo): vale para todo check com aquele prefixo. Grupo só fica obsoleto
quando **todas** as suas células voltam a bater. Enquanto uma diverge, a
seção de docs ainda descreve algo real.

Nenhum dos dois é silenciado. `validate` sai com código 1 se qualquer um
aparecer, e com 0 quando o estado do repositório é exatamente o estado que a
documentação descreve.

Sobre o que é *gate* e o que é *informativo*: as 40 células da Tabela 3 e os 20
p-valores da Tabela 4 entram como informativos por decisão documentada, a
política que `docs/discrepancias.md`, seção 12.5, já fixou depois da
comparação célula a célula. Casar uma mediana de coorte em 0.5000 com um
dataset diferente é o resultado mais provável por acaso naquele regime; tomar
isso como evidência de replicação seria um erro de interpretação.
O que trava é o predicado agregado da seção 4, a direção dos pares e a
contagem de células dentro da tolerância: essas três travam contra números
da *replicação*, declarados como tal na coluna `fonte`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from .config import checkpoints

log = logging.getLogger(__name__)

STAGE = "validate"

OK = "ok"
CONHECIDA = "conhecida"
FALHA = "FALHA"
OBSOLETA = "OBSOLETA"
INDISPONIVEL = "n/d"

ARTIGO = "artigo"
REPLICA = "replicação"

#: O yaml transcreve o rótulo do PDF ("All"); `projection.tables()` usa o rótulo
#: interno ("All types"). Traduzir aqui, e não em nenhum dos dois lados, mantém
#: o yaml fiel ao papel impresso.
LINHA_TABELA = {"All": "All types"}

#: Vereditos que fazem o comando sair com código 1.
FATAIS = {FALHA, OBSOLETA, INDISPONIVEL}


@dataclass
class Check:
    """Uma comparação. `key` é o que aparece em `known_divergences:`."""

    key: str
    grupo: str
    fonte: str
    esperado: object
    obtido: object
    bate: bool
    gate: bool = True
    nota: str = ""
    ref: str = ""
    indisponivel: bool = False
    # `ref` veio de uma declaração de grupo (`chave.*`). Nesse caso a célula
    # sozinha não decide obsolescência: quem decide é o grupo inteiro bater.
    ref_grupo: bool = False

    @property
    def status(self) -> str:
        """Símbolo do check: OK, FALHA, CONHECIDA, OBSOLETA, INDISPONIVEL ou `~`."""
        if self.indisponivel:
            return INDISPONIVEL
        if not self.gate:
            return OK if self.bate else CONHECIDA if self.ref else "~"
        if self.bate:
            return OBSOLETA if self.ref and not self.ref_grupo else OK
        return CONHECIDA if self.ref else FALHA


@dataclass
class Report:
    """Conjunto de checks de uma rodada de validação."""

    checks: list[Check] = field(default_factory=list)

    @property
    def falhas(self) -> list[Check]:
        """Checks com status fatal, os que derrubam o exit code."""
        return [c for c in self.checks if c.status in FATAIS]

    @property
    def ok(self) -> bool:
        """True quando nenhum check fatal falhou."""
        return not self.falhas

    def contagem(self) -> dict[str, int]:
        """Quantidade de checks por status."""
        out: dict[str, int] = {}
        for c in self.checks:
            out[c.status] = out.get(c.status, 0) + 1
        return out

    def markdown(self) -> str:
        """Relatório para anexar ao trabalho final (seção 10, "Definição de pronto").

        Difere do stdout em dois pontos deliberados: **lista todos os checks**,
        inclusive os informativos que batem (o terminal os esconde para caber na
        tela; um relatório que omite acertos não é auditável), e nomeia a seção
        de `discrepancias.md` em cada linha declarada: quem lê isto sem ter
        rodado nada precisa saber para onde ir. É justamente o desvio
        conhecido que exige explicação; o acerto se explica sozinho.
        """
        cont = self.contagem()
        informativos = sum(1 for c in self.checks if not c.gate)
        veredito = (
            "Sem divergência não declarada."
            if self.ok
            else f"**{len(self.falhas)} divergência(s) a resolver.**"
        )

        out = [
            "# Relatório de validação",
            "",
            f"Gerado por `pyramid validate --report` em "
            f"{pd.Timestamp.now():%Y-%m-%d %H:%M}, contra `config/checkpoints.yaml`.",
            "",
            f"{len(self.checks)} checks ({len(self.checks) - informativos} gate, "
            f"{informativos} informativos): "
            + ", ".join(f"`{k}`={n}" for k, n in sorted(cont.items()))
            + f". {veredito}",
            "",
            "Legenda: `ok` bate · `conhecida` diverge e está analisada em "
            "`docs/discrepancias.md` · `~` informativo que diverge · `FALHA` "
            "diverge sem explicação · `OBSOLETA` declarada como divergente mas "
            "voltou a bater · `n/d` artefato não gerado.",
            "",
        ]

        grupo = None
        for c in self.checks:
            if c.grupo != grupo:
                grupo = c.grupo
                out += [
                    "",
                    f"## {grupo}",
                    "",
                    "| check | fonte | esperado | obtido | status | referência |",
                    "|---|---|---|---|---|---|",
                ]
            nota = "  ".join(x for x in (c.ref, c.nota) if x) or "-"
            out.append(
                f"| `{c.key}` | {c.fonte} | {_fmt(c.esperado)} | {_fmt(c.obtido)} "
                f"| {c.status} | {nota} |"
            )
        out.append("")
        return "\n".join(out)


# ---------------------------------------------------------------------------
# comparação
# ---------------------------------------------------------------------------


def _perto(a: float, b: float, tol_rel: float) -> bool:
    """Igualdade relativa, com o zero tratado no absoluto.

    `abs(a - b) <= tol * abs(b)` some quando o esperado é 0.0000, e a Tabela 3
    tem uma célula assim (D/non_coding/baseline). Ali o critério vira a própria
    tolerância no absoluto, senão só o zero exato passaria.
    """
    a, b = float(a), float(b)
    if pd.isna(a) or pd.isna(b):
        return False
    if b == 0.0:
        return abs(a) <= tol_rel
    return abs(a - b) <= tol_rel * abs(b)


def _fmt(v: object) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return "nan" if pd.isna(v) else f"{v:.4f}"
    if isinstance(v, bool):
        return "sim" if v else "não"
    return str(v)


# ---------------------------------------------------------------------------
# grupos de checagem
# ---------------------------------------------------------------------------


def _tipos(cfg: dict) -> list[Check]:
    """IEICE16 Fig.5: contagem por tipo e os 8 projetos nomeados."""
    from . import metrics
    from .extract import source

    c = cfg["types"]
    snap = c["snapshot"]
    mk = lambda **kw: Check(grupo="types", fonte=ARTIGO, **kw)  # noqa: E731

    try:
        tab = metrics.table(snap)
    except FileNotFoundError as e:
        log.warning("métricas ausentes: %s", e)
        return [
            mk(
                key="types",
                esperado="Fig.5",
                obtido="rode `pyramid metrics`",
                bate=False,
                indisponivel=True,
            )
        ]

    out: list[Check] = []
    vistos = tab["type"].value_counts(dropna=False).to_dict()
    for tipo, n in c["counts"].items():
        out.append(
            mk(
                key=f"types.counts.{tipo}",
                esperado=n,
                obtido=int(vistos.get(tipo, 0)),
                bate=int(vistos.get(tipo, 0)) == n,
            )
        )

    classificados = int(tab["type"].notna().sum())
    total = len(source().list_scopes())
    out.append(
        mk(
            key="types.total_classified",
            esperado=c["total_classified"],
            obtido=classificados,
            bate=classificados == c["total_classified"],
        )
    )
    out.append(
        mk(
            key="types.total_projects",
            esperado=c["total_projects"],
            obtido=total,
            bate=total == c["total_projects"],
        )
    )
    sem = total - classificados
    out.append(
        mk(
            key="types.unclassified",
            esperado=c["unclassified"],
            obtido=sem,
            bate=sem == c["unclassified"],
        )
    )

    por_id = tab.set_index("scope_id")
    for sid, esperado in c["examples"].items():
        got = por_id["type"].get(sid)
        got = None if got is None or pd.isna(got) else str(got)
        nome = por_id["project"].get(sid, "?")
        out.append(
            mk(
                key=f"types.examples.{sid}",
                esperado=esperado,
                obtido=got,
                bate=got == esperado,
                nota=str(nome),
            )
        )
    return out


def _atratividade(cfg: dict) -> list[Check]:
    """ESEM14 Fig.2 (quadrantes de dez/2011) e a regra de 2013 da seção 11.1."""
    from . import attractiveness as at

    c = cfg["attractiveness"]
    mk = lambda **kw: Check(grupo="attractiveness", **kw)  # noqa: E731

    try:
        df = at.load()
    except FileNotFoundError as e:
        log.warning("atratividade ausente: %s", e)
        return [
            mk(
                key="attractiveness",
                fonte=ARTIGO,
                esperado="Fig.2",
                obtido="rode `pyramid attractiveness`",
                bate=False,
                indisponivel=True,
            )
        ]

    out: list[Check] = []
    for chave, alvos in c.items():
        if not isinstance(alvos, dict) or chave in {"transitions"}:
            continue
        ano = at.year_of(chave)
        corte = at.table(ano).set_index("scope_id")
        for sid, esperado in alvos.items():
            got = corte["quadrant"].get(sid)
            got = None if got is None or pd.isna(got) else str(got)
            out.append(
                mk(
                    key=f"attractiveness.{ano}.{sid}",
                    fonte=ARTIGO,
                    esperado=esperado,
                    obtido=got,
                    bate=got == esperado,
                    nota=str(corte["project"].get(sid, "?")),
                )
            )

    # seção 11.1: 2013 é renderizado mas não classificado. O artigo usa linguagem
    # condicional para o jekyll em 2013 justamente porque o dataset dele tem o
    # mesmo corte em out/2013; atribuir quadrante ali seria inventar sinal que
    # nem os autores tinham.
    for ano in c.get("shape_only_years", []):
        sub = df[df["year"] == ano]
        com_quadrante = int(sub["quadrant"].notna().sum())
        out.append(
            mk(
                key=f"attractiveness.shape_only.{ano}",
                fonte=REPLICA,
                esperado=0,
                obtido=com_quadrante,
                bate=com_quadrante == 0,
                nota=f"{len(sub)} projetos com forma, nenhum com quadrante (seção 11.1)",
            )
        )

    # A única categoria formal que o artigo crava para o jekyll é 2011.
    for sid, spec in (c.get("transitions") or {}).items():
        if not isinstance(spec, dict):
            continue
        for ano, esperado in (spec.get("classified") or {}).items():
            corte = at.table(int(ano)).set_index("scope_id")
            got = corte["quadrant"].get(sid)
            got = None if got is None or pd.isna(got) else str(got)
            out.append(
                mk(
                    key=f"attractiveness.{ano}.{sid}",
                    fonte=ARTIGO,
                    esperado=esperado,
                    obtido=got,
                    bate=got == esperado,
                    nota=str(corte["project"].get(sid, "?")),
                )
            )
    return out


def _msr14_tab2(cfg: dict) -> list[Check]:
    """MSR14 Tabela 2: histórico de quadrantes de 12 projetos, 2004-2011.

    Grade larga sobre o mesmo estágio que o ESEM14 só testa em um snapshot.
    Além do quadrante, testa a estrutura: "-" (projeto sem atividade no ano) e
    "*" (ativo, mas devs <= 10, fora do filtro) são afirmações do artigo sobre
    a elegibilidade, e a replicação tem de reproduzi-las.
    """
    from . import attractiveness as at

    c = cfg.get("msr14_tab2") or {}
    if not c:
        return []
    mk = lambda **kw: Check(grupo="msr14/tab2", fonte=ARTIGO, **kw)  # noqa: E731
    letra = {"A": "attractive", "F": "floating", "S": "stagnant", "T": "terminal"}

    try:
        df = at.table()  # com a coluna `project` (rótulo do escopo)
    except FileNotFoundError as e:
        log.warning("atratividade ausente: %s", e)
        return [
            mk(
                key="msr14.tab2",
                esperado="Tabela 2",
                obtido="rode `pyramid attractiveness`",
                bate=False,
                indisponivel=True,
            )
        ]

    anos = list(c["years"])
    por_nome = {
        str(p): sid
        for sid, p in df[["scope_id", "project"]].drop_duplicates().itertuples(index=False)
    }
    celula: dict[tuple[int, int], str] = {}
    for r in df.itertuples():
        q = r.quadrant
        celula[(int(r.scope_id), int(r.year))] = (
            "*" if not bool(r.eligible) or q is None or pd.isna(q) else str(q)
        )

    out: list[Check] = []
    estrut_ok = estrut_n = 0
    for nome, linha in c["grid"].items():
        sid = por_nome.get(nome)
        esperados = str(linha).split()
        if len(esperados) != len(anos):
            raise ValueError(
                f"msr14_tab2.grid['{nome}'] tem {len(esperados)} células para "
                f"{len(anos)} anos declarados em `years`."
            )
        for ano, esp in zip(anos, esperados, strict=True):
            got = "-" if sid is None else celula.get((int(sid), ano), "-")
            if esp in {"-", "*"}:
                # Estrutura: agregada em um check só, para não afogar o relatório.
                estrut_n += 1
                estrut_ok += got == esp
                continue
            alvo = letra[esp]
            obtido = letra.get(got, got)  # "-"/"*" passam cru: são a divergência
            out.append(
                mk(
                    key=f"msr14.tab2.{ano}.{nome}",
                    esperado=alvo,
                    obtido=obtido,
                    bate=obtido == alvo,
                )
            )
    bate_n = sum(1 for k in out if k.bate)
    out.append(
        mk(
            key="msr14.tab2.estrutura",
            esperado=f"{estrut_n}/{estrut_n}",
            obtido=f"{estrut_ok}/{estrut_n}",
            bate=estrut_ok == estrut_n,
            nota='células "-" (sem atividade) e "*" (devs <= 10) do artigo',
        )
    )
    out.append(
        Check(
            grupo="msr14/tab2",
            fonte=REPLICA,
            key="msr14.tab2.concordancia",
            esperado=f">= {c.get('min_agreement', 0.80):.0%}",
            obtido=f"{bate_n}/{len(out) - 1} ({bate_n / max(len(out) - 1, 1):.0%})",
            bate=bate_n / max(len(out) - 1, 1) >= float(c.get("min_agreement", 0.80)),
            nota="quadrantes reais; travar aqui evita regressão silenciosa no estágio",
        )
    )
    return out


def _projecao(cfg: dict) -> list[Check]:
    """IEICE16 seção 4: Tabelas 3 e 4, curto vs. longo prazo."""
    from . import projection as pj

    abre_cfg = cfg["projection_abre"]
    wil_cfg = cfg["projection_wilcoxon"]
    term_cfg = cfg["projection_term"]
    travas = cfg.get("replica_locks", {})
    tol = float(abre_cfg["tolerance_rel"])

    try:
        df = pj.load()
    except FileNotFoundError as e:
        log.warning("projeção ausente: %s", e)
        return [
            Check(
                key="projection",
                grupo="projection",
                fonte=ARTIGO,
                esperado="Tabelas 3 e 4",
                obtido="rode `pyramid projection`",
                bate=False,
                indisponivel=True,
            )
        ]

    tabs = pj.tables(df)
    med = tabs["abre"].set_index("type")
    pval = tabs["wilcoxon"].set_index("type")
    out: list[Check] = []

    n_proj = int(med.loc["All types", "projects"])
    out.append(
        Check(
            key="projection.n_projects",
            grupo="projection",
            fonte=ARTIGO,
            esperado=abre_cfg["n_projects"],
            obtido=n_proj,
            bate=n_proj == abre_cfg["n_projects"],
            nota=(
                f"> {abre_cfg['min_contributors']} contribuidores ativos "
                f"em {abre_cfg['base_snapshots'][0]}"
            ),
        )
    )

    # --- 40 células, informativas (seção 12.5) -------------------------------
    dentro = 0
    concorda = 0
    for tipo, cats in abre_cfg["table"].items():
        linha = LINHA_TABELA.get(tipo, tipo)
        for cat, (art_c, art_b) in cats.items():
            got_c = float(med.loc[linha, f"{cat}_cohort"])
            got_b = float(med.loc[linha, f"{cat}_baseline"])
            for rotulo, art, got in (("cohort", art_c, got_c), ("baseline", art_b, got_b)):
                bate = _perto(got, art, tol)
                dentro += bate
                out.append(
                    Check(
                        key=f"projection.abre.{tipo}.{cat}.{rotulo}",
                        grupo="projection/tab3",
                        fonte=ARTIGO,
                        esperado=float(art),
                        obtido=got,
                        bate=bate,
                        gate=False,
                    )
                )
            # Direção: o achado da Tabela 3 é "cohort erra menos que baseline".
            # Empate exato não conta como concordância nem como inversão: é
            # resolução insuficiente (seção 12.5), e vai anotado.
            art_dir = art_c < art_b
            got_dir = got_c < got_b
            empate = got_c == got_b
            concorda += (not empate) and (art_dir == got_dir)
            out.append(
                Check(
                    key=f"projection.direcao.{tipo}.{cat}",
                    grupo="projection/tab3",
                    fonte=ARTIGO,
                    esperado="cohort<baseline" if art_dir else "cohort>baseline",
                    obtido="empate"
                    if empate
                    else ("cohort<baseline" if got_dir else "cohort>baseline"),
                    bate=(not empate) and (art_dir == got_dir),
                    gate=False,
                )
            )

    # --- 20 p-valores, informativos ----------------------------------------
    # O p-valor é estatística de amostra: com 34 projetos e coortes diferentes
    # ele não tem por que casar a 2%, e exigir isso seria inventar um critério
    # que o artigo não sustenta. O que se compara é a *decisão* de significância.
    for tipo, cats in wil_cfg["table"].items():
        linha = LINHA_TABELA.get(tipo, tipo)
        for cat, (art_p, art_sig) in cats.items():
            got_p = float(pval.loc[linha, cat])
            got_sig = bool(got_p < 0.05) if not pd.isna(got_p) else False
            out.append(
                Check(
                    key=f"projection.wilcoxon.{tipo}.{cat}",
                    grupo="projection/tab4",
                    fonte=ARTIGO,
                    esperado=bool(art_sig),
                    obtido=got_sig,
                    bate=got_sig == bool(art_sig),
                    gate=False,
                    nota=f"p artigo {art_p:.4f} / replicação {got_p:.4f}",
                )
            )

    # --- travas da replicação --------------------------------------------------
    for chave, obtido, total in (
        ("projection_celulas_2pct", dentro, 40),
        ("projection_direcao_pares", concorda, 20),
    ):
        if chave not in travas:
            continue
        out.append(
            Check(
                key=f"replica_locks.{chave}",
                grupo="projection",
                fonte=REPLICA,
                esperado=f"{travas[chave]}/{total}",
                obtido=f"{obtido}/{total}",
                bate=obtido == travas[chave],
                nota="seção 12.5: trava de deriva do processo de replicação",
            )
        )

    # Predicado agregado da seção 4: é o que a replicação sustenta.
    agg = travas.get("projection_agregado")
    if agg:
        got_c = float(med.loc["All types", "all_cohort"])
        got_b = float(med.loc["All types", "all_baseline"])
        got_p = float(pval.loc["All types", "all"])
        for rotulo, esperado, valor in (
            ("cohort", agg["cohort"], got_c),
            ("baseline", agg["baseline"], got_b),
            ("p", agg["p"], got_p),
        ):
            out.append(
                Check(
                    key=f"replica_locks.projection_agregado.{rotulo}",
                    grupo="projection",
                    fonte=REPLICA,
                    esperado=float(esperado),
                    obtido=valor,
                    bate=_perto(valor, esperado, tol),
                    nota="seção 12.2: predicado que se sustenta",
                )
            )
        out.append(
            Check(
                key="replica_locks.projection_agregado.direcao",
                grupo="projection",
                fonte=ARTIGO,
                esperado="cohort<baseline e significativo",
                obtido=f"cohort{'<' if got_c < got_b else '>'}baseline e "
                f"{'significativo' if got_p < 0.05 else 'não significativo'}",
                bate=bool(got_c < got_b and got_p < 0.05),
                nota="o achado central da seção 4",
            )
        )

    # --- curto vs. longo prazo ---------------------------------------------
    term = pj.term_split(df)
    art_dir = term_cfg["short_term_abre_median"] > term_cfg["long_term_abre_median"]
    got_dir = term["short_term_abre_median"] > term["long_term_abre_median"]
    out.append(
        Check(
            key="projection.term.direcao",
            grupo="projection",
            fonte=ARTIGO,
            esperado="short>long" if art_dir else "short<long",
            obtido="short>long" if got_dir else "short<long",
            bate=art_dir == got_dir,
            nota=(
                f"artigo {term_cfg['short_term_abre_median']:.4f}"
                f"/{term_cfg['long_term_abre_median']:.4f}"
                f" · replicação {term['short_term_abre_median']:.4f}"
                f"/{term['long_term_abre_median']:.4f}"
                f" (n={term['short_n']}/{term['long_n']})"
            ),
        )
    )
    got_sig = term["wilcoxon_p"] < 0.05
    out.append(
        Check(
            key="projection.term.significancia",
            grupo="projection",
            fonte=ARTIGO,
            esperado=bool(term_cfg["significant"]),
            obtido=bool(got_sig),
            bate=bool(got_sig) == bool(term_cfg["significant"]),
            nota=f"p artigo {term_cfg['wilcoxon_p']:.4f} / replicação {term['wilcoxon_p']:.4f}",
        )
    )
    return out


GRUPOS = {
    "types": _tipos,
    "attractiveness": _atratividade,
    "msr14/tab2": _msr14_tab2,
    "projection": _projecao,
}


# ---------------------------------------------------------------------------
# execução
# ---------------------------------------------------------------------------


def _resolvedor(declaradas: dict[str, str]) -> Callable[[str], tuple[str, bool]]:
    """Devolve a função que casa a chave de um check com uma divergência declarada.

    O segundo elemento do retorno diz se o casamento veio de uma declaração de
    grupo (`chave.*`), informação que o status do check usa para não marcar
    OBSOLETA uma célula isolada que voltou a bater.
    """
    prefixos = {k[:-1]: v for k, v in declaradas.items() if k.endswith(".*")}

    def referencia(key: str) -> tuple[str, bool]:
        if key in declaradas:
            return declaradas[key], False
        for p, ref in prefixos.items():
            if key.startswith(p):
                return ref, True
        return "", False

    return referencia


def _orfa(key: str, nota: str) -> Check:
    return Check(
        key=key,
        grupo="known_divergences",
        fonte=REPLICA,
        esperado="check existente",
        obtido="chave órfã no yaml",
        bate=False,
        nota=nota,
    )


def _grupo_reproduzido(key: str, ref: str, n: int) -> Check:
    return Check(
        key=key,
        grupo="known_divergences",
        fonte=REPLICA,
        esperado="ao menos uma célula divergente",
        obtido=f"{n}/{n} batem",
        bate=True,  # -> OBSOLETA: o grupo inteiro reproduz
        ref=ref,
    )


def _auditar_declaracoes(rep: Report, declaradas: dict[str, str]) -> list[Check]:
    """Checks sobre o próprio `known_divergences`.

    Uma declaração sem check correspondente é lixo acumulado: aponta para uma
    chave que não existe mais, então não protege nada e engana quem lê. E um
    grupo cujas células *todas* voltaram a bater é a mesma mentira que a
    OBSOLETA individual pega, espalhada por várias linhas.
    """
    chaves = {c.key for c in rep.checks}
    out: list[Check] = []
    for k, ref in declaradas.items():
        if k.endswith(".*"):
            membros = [c for c in rep.checks if c.key.startswith(k[:-1])]
            if membros and all(c.bate for c in membros):
                out.append(_grupo_reproduzido(k, ref, len(membros)))
            if membros:
                continue
        elif k in chaves:
            continue
        out.append(_orfa(k, ref))
    return out


def run(grupos: list[str] | None = None) -> Report:
    """Roda os grupos de checks pedidos, ou todos, e devolve o relatório.

    A auditoria de `known_divergences` só entra na rodada completa: com um
    subconjunto de grupos, toda declaração dos grupos de fora pareceria órfã.
    """
    cfg = checkpoints()
    declaradas = cfg.get("known_divergences") or {}
    alvo = grupos or list(GRUPOS)
    desconhecido = [g for g in alvo if g not in GRUPOS]
    if desconhecido:
        raise ValueError(f"grupo desconhecido: {desconhecido}. Disponíveis: {sorted(GRUPOS)}")

    referencia = _resolvedor(declaradas)
    rep = Report()
    for nome in alvo:
        for c in GRUPOS[nome](cfg):
            c.ref, c.ref_grupo = referencia(c.key)
            rep.checks.append(c)

    if grupos is None:
        rep.checks.extend(_auditar_declaracoes(rep, declaradas))
    return rep
