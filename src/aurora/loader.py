"""Carga dos dados sintéticos no MySQL: lotes, parametrizada, numa única transação."""
from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

import pandas as pd
from sqlalchemy import Connection, Engine, MetaData, Table, delete, insert

from aurora.generator import SyntheticData

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


def to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Converte para tipos nativos do Python; valores ausentes viram None (NULL)."""
    clean = df.astype(object).where(df.notna(), None)
    return [{str(column): value for column, value in row.items()} for row in clean.to_dict("records")]


def batches(records: list[dict[str, Any]], size: int = BATCH_SIZE) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(records), size):
        yield records[start:start + size]


def _load_table(conn: Connection, table: Table, df: pd.DataFrame) -> int:
    records = to_records(df)
    for chunk in batches(records):
        conn.execute(insert(table), chunk)
    logger.info("%-12s %7d linhas", table.name, len(records))
    return len(records)


def load(engine: Engine, data: SyntheticData) -> dict[str, int]:
    """Substitui o conteúdo das tabelas pelos dados gerados, tudo em uma transação.

    Se qualquer lote falhar, nada é gravado (rollback).
    """
    metadata = MetaData()
    metadata.reflect(bind=engine)
    tables = data.tables()
    counts: dict[str, int] = {}
    with engine.begin() as conn:
        for name in reversed(list(tables)):  # filhos antes dos pais
            conn.execute(delete(metadata.tables[name]))
        for name, df in tables.items():
            counts[name] = _load_table(conn, metadata.tables[name], df)
    return counts
