"""Leitura das consultas nomeadas de sql/analytics_queries.sql."""
from __future__ import annotations

import re
from pathlib import Path

from aurora.config import SQL_DIR
from aurora.db import strip_comments

_NAME = re.compile(r"^--\s*name:\s*(\w+)\s*$", re.MULTILINE)


def parse_queries(sql: str) -> dict[str, str]:
    """Separa o script em ``{nome: consulta}``. Texto antes do primeiro ``-- name:`` é ignorado."""
    matches = list(_NAME.finditer(sql))
    queries: dict[str, str] = {}
    for current, following in zip(matches, matches[1:] + [None]):
        end = following.start() if following else len(sql)
        name = current.group(1)
        if name in queries:
            raise ValueError(f"Consulta duplicada: {name}")
        body = strip_comments(sql[current.end():end]).strip().rstrip(";").strip()
        if not body:
            raise ValueError(f"Consulta vazia: {name}")
        queries[name] = body
    return queries


def load_queries(path: Path = SQL_DIR / "analytics_queries.sql") -> dict[str, str]:
    return parse_queries(path.read_text(encoding="utf-8"))
