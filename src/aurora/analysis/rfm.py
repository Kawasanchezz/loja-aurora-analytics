"""Segmentação RFM (Recência, Frequência, Valor): scoring em pandas sobre a base agregada no SQL.

Regras:
  * Recência e Valor: notas de 1 a 5 por quintis (5 = melhor). Empates são desempatados
    pela ordem de aparição (``rank(method="first")``) para manter cinco grupos de tamanho similar.
  * Frequência: notas por faixas fixas de pedidos (1, 2, 3, 4, 5 ou mais), porque a maioria dos
    clientes tem poucos pedidos e quintis ficariam arbitrários.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {"customer_id", "last_order_date", "frequency", "monetary"}
SEGMENT_ORDER = ["Campeões", "Fiéis", "Promissores", "Precisam de atenção", "Em risco", "Hibernando"]


def _quintile_score(values: pd.Series) -> pd.Series:
    """Nota 1..5 por quintil; o maior valor recebe 5."""
    ranked = values.rank(method="first")
    return pd.qcut(ranked, 5, labels=[1, 2, 3, 4, 5]).astype(int)


def frequency_score(frequency: pd.Series) -> pd.Series:
    return frequency.clip(lower=1, upper=5).astype(int)


def assign_segment(r: pd.Series, f: pd.Series) -> pd.Series:
    """Mapeia as notas R e F para um segmento de negócio."""
    conditions = [
        (r >= 4) & (f >= 4),
        (r >= 3) & (f >= 3),
        (r >= 4) & (f <= 2),
        (r == 3) & (f <= 2),
        (r <= 2) & (f >= 3),
    ]
    labels = ["Campeões", "Fiéis", "Promissores", "Precisam de atenção", "Em risco"]
    return pd.Series(np.select(conditions, labels, default="Hibernando"), index=r.index)


def score_rfm(base: pd.DataFrame, reference_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Devolve a base com recency_days, notas R/F/M e o segmento.

    reference_date: data de referência da recência; padrão = dia seguinte ao último pedido da base.
    """
    missing = REQUIRED_COLUMNS - set(base.columns)
    if missing:
        raise ValueError(f"Colunas ausentes na base RFM: {sorted(missing)}")
    if len(base) < 5:
        raise ValueError("São necessários ao menos 5 clientes para formar quintis")

    scored = base.copy()
    scored["last_order_date"] = pd.to_datetime(scored["last_order_date"])
    if reference_date is None:
        reference_date = scored["last_order_date"].max().normalize() + pd.Timedelta(days=1)
    scored["recency_days"] = (reference_date - scored["last_order_date"]).dt.total_seconds() / 86400

    scored["r_score"] = _quintile_score(-scored["recency_days"])  # menos dias = nota maior
    scored["f_score"] = frequency_score(scored["frequency"])
    scored["m_score"] = _quintile_score(scored["monetary"])
    scored["segment"] = assign_segment(scored["r_score"], scored["f_score"])
    return scored


def summarize_segments(scored: pd.DataFrame) -> pd.DataFrame:
    """Clientes, receita e ticket médio por segmento, na ordem de negócio."""
    summary = (scored.groupby("segment")
               .agg(customers=("customer_id", "count"),
                    revenue=("monetary", "sum"),
                    avg_orders=("frequency", "mean"),
                    avg_recency_days=("recency_days", "mean"))
               .reindex([s for s in SEGMENT_ORDER if s in set(scored["segment"])]))
    summary["customer_share_pct"] = 100 * summary["customers"] / summary["customers"].sum()
    summary["revenue_share_pct"] = 100 * summary["revenue"] / summary["revenue"].sum()
    return summary.reset_index()
