"""Travas de segurança para operações destrutivas (apagam tabelas e dados)."""
from __future__ import annotations

import sys
from collections.abc import Callable

from aurora.config import Settings

TEST_DATABASE_SUFFIX = "_test"


def confirm_destructive(settings: Settings, assume_yes: bool = False, *,
                        input_fn: Callable[[str], str] | None = None,
                        interactive: bool | None = None) -> bool:
    """Pede confirmação antes de apagar dados.

    O usuário precisa digitar o nome exato do banco, o que evita apagar o banco errado por
    descuido. ``--yes`` (assume_yes) dispensa a pergunta; sem terminal interativo e sem
    ``--yes``, a operação é recusada.
    """
    if assume_yes:
        return True
    ask = input_fn or input  # resolvido na chamada (permite trocar o input nos testes)
    if interactive is None:
        interactive = sys.stdin.isatty()
    if not interactive:
        return False
    prompt = (f"ATENÇÃO: isto APAGA as tabelas e os dados do banco '{settings.database}' "
              f"em {settings.host}:{settings.port}.\nDigite o nome do banco para continuar: ")
    try:
        return ask(prompt).strip() == settings.database
    except (EOFError, KeyboardInterrupt):  # entrada fechada (ex.: NUL no Windows) ou Ctrl+C
        return False


def is_safe_test_database(name: str, main_database: str | None = None) -> bool:
    """Um banco só pode ser usado nos testes de integração se o nome terminar em ``_test``
    e for diferente do banco principal da aplicação."""
    return name.endswith(TEST_DATABASE_SUFFIX) and name != main_database
