"""Acesso ao MySQL: engine, aplicação do esquema e execução de consultas nomeadas."""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from aurora.config import SQL_DIR, Settings

logger = logging.getLogger(__name__)


def make_engine(settings: Settings) -> Engine:
    return create_engine(settings.url(), pool_pre_ping=True)


def strip_comments(sql: str) -> str:
    """Remove linhas inteiras de comentário (``-- ...``)."""
    return "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))


def split_statements(sql: str) -> list[str]:
    """Divide um script em comandos pelo ``;`` (o esquema não usa ``;`` em strings)."""
    return [part.strip() for part in strip_comments(sql).split(";") if part.strip()]


def apply_schema(engine: Engine, path: Path = SQL_DIR / "schema.sql") -> int:
    """Executa o esquema numa transação de conexão; devolve o número de comandos."""
    statements = split_statements(path.read_text(encoding="utf-8"))
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
    logger.info("Esquema aplicado: %d comandos", len(statements))
    return len(statements)


def run_query(engine: Engine, sql: str) -> pd.DataFrame:
    """Executa uma consulta analítica estática (sem parâmetros) e devolve um DataFrame."""
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)
