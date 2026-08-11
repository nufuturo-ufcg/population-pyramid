"""Testes dos hooks do repositório.

Os hooks são a única barreira automática contra duas regras que já custaram
caro: SQL fora de `adapters/` e de `src/pyramid/sources/`, e commit assinado
por assistente.
Hook sem teste é hook que ninguém percebe quando para de pegar.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[1]
HOOKS = RAIZ / "scripts" / "hooks"


def _carrega(nome: str) -> ModuleType:
    """Importa um hook pelo caminho. `scripts/hooks` não é pacote instalável."""
    spec = importlib.util.spec_from_file_location(nome, HOOKS / f"{nome}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nome] = mod
    spec.loader.exec_module(mod)
    return mod


sql_hook = _carrega("sql_so_em_sources")
msg_hook = _carrega("mensagem_de_commit")


# --- SQL só em src/pyramid/sources/ -------------------------------------------


@pytest.mark.parametrize(
    "corpo",
    [
        'q = "SELECT id FROM projects"',
        'q = """\n    SELECT c.id\n    FROM commits c\n"""',
        'cx.execute("delete from users where id = 1")',
        'cx.execute("INSERT INTO cache VALUES (1)")',
        'cx.execute("UPDATE projects SET name = 1")',
    ],
)
def test_sql_fora_de_sources_e_barrado(tmp_path: Path, corpo: str) -> None:
    """Qualquer comando SQL fora da pasta de fontes derruba o hook."""
    alvo = tmp_path / "motor.py"
    alvo.write_text(corpo, encoding="utf-8")
    assert sql_hook.main([str(alvo)]) == 1


def test_sql_dentro_de_adapters_passa() -> None:
    """A fonte real do MSR14 é cheia de SELECT e tem que passar."""
    fonte = RAIZ / "adapters" / "msr14" / "source.py"
    assert fonte.exists()
    assert sql_hook.main([str(fonte)]) == 0


def test_sql_dentro_do_registro_de_fontes_passa() -> None:
    """`src/pyramid/sources/` guarda contrato e loader, e também pode ter SQL."""
    pasta = RAIZ / "src" / "pyramid" / "sources"
    assert (pasta / "base.py").exists()
    alvo = pasta / "_exemplo_do_teste.py"
    alvo.write_text('q = "SELECT id FROM projects"', encoding="utf-8")
    try:
        assert sql_hook.main([str(alvo)]) == 0
    finally:
        alvo.unlink()


def test_adaptador_novo_em_qualquer_pasta_de_adapters_passa() -> None:
    """A permissão vale para `adapters/` inteiro, não só para o msr14."""
    alvo = RAIZ / "adapters" / "_exemplo_do_teste.py"
    alvo.write_text('q = "SELECT id FROM projects"', encoding="utf-8")
    try:
        assert sql_hook.main([str(alvo)]) == 0
    finally:
        alvo.unlink()


def test_palavra_select_em_prosa_nao_e_sql(tmp_path: Path) -> None:
    """`select` solto em comentário ou nome de método não pode dar falso positivo."""
    alvo = tmp_path / "prosa.py"
    alvo.write_text(
        '# escolhe (select) as colunas\nsub = df.select_dtypes("number")\n',
        encoding="utf-8",
    )
    assert sql_hook.main([str(alvo)]) == 0


def test_table_rows_barrado_ate_dentro_de_sources(tmp_path: Path) -> None:
    """`information_schema.table_rows` é estimativa e cai em qualquer pasta."""
    pasta = tmp_path / "src" / "pyramid" / "sources"
    pasta.mkdir(parents=True)
    alvo = pasta / "outra.py"
    alvo.write_text('q = "SELECT table_rows FROM information_schema.TABLE_ROWS"', encoding="utf-8")
    saida = sql_hook._violacoes(alvo)
    assert any("COUNT(*)" in s for s in saida)


def test_hook_ignora_arquivo_que_nao_e_python(tmp_path: Path) -> None:
    """O hook roda em todo o commit; markdown com SQL de exemplo não é violação."""
    alvo = tmp_path / "doc.md"
    alvo.write_text("`SELECT * FROM commits` roda na fonte.", encoding="utf-8")
    assert sql_hook.main([str(alvo)]) == 0


def test_o_proprio_hook_nao_se_acusa() -> None:
    """`scripts/hooks/` carrega os padrões que procura e fica isento."""
    assert sql_hook.main([str(HOOKS / "sql_so_em_sources.py")]) == 0


def test_este_arquivo_de_teste_e_isento() -> None:
    """Este teste guarda SQL de exemplo. Sem a isenção, o commit dele falharia."""
    assert sql_hook.main([str(Path(__file__))]) == 0
    assert sql_hook.main(["tests/test_hooks.py"]) == 0


def test_caminho_absoluto_e_relativo_dao_o_mesmo_veredito() -> None:
    """O prek passa caminho relativo, `git commit` à mão passa absoluto."""
    fonte = RAIZ / "adapters" / "msr14" / "source.py"
    assert sql_hook.main([str(fonte)]) == sql_hook.main(["adapters/msr14/source.py"]) == 0


# --- mensagem de commit -------------------------------------------------------


@pytest.mark.parametrize(
    "msg",
    [
        "titulo\n\nCo-authored-by: Claude <noreply@anthropic.com>\n",
        "titulo\n\nco-authored-by: claude <x@y.z>\n",
        "titulo\n\n🤖 Generated with Claude Code\n",
        "titulo\n\nGenerated with Cursor\n",
    ],
)
def test_assinatura_de_assistente_e_recusada(msg: str) -> None:
    """Nenhum commit deste repo leva coautoria nem propaganda de ferramenta."""
    assert msg_hook.problemas(msg)


def test_coautoria_humana_passa() -> None:
    """A regra é sobre assistente. Coautoria de pessoa continua valendo."""
    msg = "corrige o corte do limiar\n\nCo-authored-by: Alguem <alguem@exemplo.org>\n"
    assert msg_hook.problemas(msg) == []


def test_assunto_longo_e_recusado() -> None:
    """O limite mantém `git log --oneline` legível."""
    achados = msg_hook.problemas("x" * (msg_hook.LIMITE_ASSUNTO + 1))
    assert any("limite" in a for a in achados)


def test_assunto_no_limite_passa() -> None:
    """O corte é `>`. Exatamente no limite ainda entra."""
    assert msg_hook.problemas("x" * msg_hook.LIMITE_ASSUNTO) == []


def test_corpo_colado_no_assunto_e_recusado() -> None:
    """Falta de linha em branco entre assunto e corpo derruba."""
    achados = msg_hook.problemas("assunto\ncorpo colado\n")
    assert any("linha em branco" in a for a in achados)


def test_mensagem_vazia_e_recusada() -> None:
    """Só comentário do git conta como mensagem vazia."""
    achados = msg_hook.problemas("# comentario do git\n#\n")
    assert achados == ["mensagem sem assunto."]


def test_comentario_do_git_nao_vira_assunto() -> None:
    """As linhas `#` que o git anexa não podem contar como corpo nem assunto."""
    msg = "titulo curto\n\ncorpo\n# Please enter the commit message\n"
    assert msg_hook.problemas(msg) == []


def test_main_le_o_arquivo_que_o_git_passa(tmp_path: Path) -> None:
    """O git entrega o caminho de `.git/COMMIT_EDITMSG`, não o texto."""
    alvo = tmp_path / "COMMIT_EDITMSG"
    alvo.write_text("titulo bom\n\ncorpo\n", encoding="utf-8")
    assert msg_hook.main([str(alvo)]) == 0
    alvo.write_text("titulo\n\nCo-authored-by: Claude <noreply@anthropic.com>\n", encoding="utf-8")
    assert msg_hook.main([str(alvo)]) == 1


def test_main_sem_argumento_devolve_erro_de_uso() -> None:
    """Chamada errada do hook não pode passar por commit aprovado."""
    assert msg_hook.main([]) == 2
