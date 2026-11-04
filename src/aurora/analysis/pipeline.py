"""Executa as consultas analíticas e o scoring, devolvendo todos os resultados em um objeto."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
from sqlalchemy import Engine

from aurora.analysis.cohorts import retention_matrix
from aurora.analysis.rfm import score_rfm, summarize_segments
from aurora.db import run_query
from aurora.queries import load_queries

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisResults:
    kpis: pd.Series
    customers_total: int
    order_status: pd.DataFrame
    monthly: pd.DataFrame
    categories: pd.DataFrame
    abc: pd.DataFrame
    rfm_scored: pd.DataFrame
    rfm_segments: pd.DataFrame
    cohort_rows: pd.DataFrame
    retention: pd.DataFrame
    channels: pd.DataFrame
    coupons: pd.DataFrame
    coupon_summary: pd.DataFrame
    payments: pd.DataFrame
    states: pd.DataFrame


def run_analysis(engine: Engine) -> AnalysisResults:
    queries = load_queries()

    def fetch(name: str) -> pd.DataFrame:
        frame = run_query(engine, queries[name])
        logger.info("Consulta %-22s %5d linhas", name, len(frame))
        return frame

    kpis = fetch("kpis")
    if kpis.empty or int(kpis["completed_orders"].iloc[0]) == 0:
        raise RuntimeError("Não há pedidos concluídos no banco. Rode o comando seed antes do report.")

    monthly = fetch("monthly_performance")
    monthly["month"] = pd.to_datetime(monthly["month"])
    rfm_scored = score_rfm(fetch("rfm_base"))
    cohort_rows = fetch("cohort_retention")

    return AnalysisResults(
        kpis=kpis.iloc[0],
        customers_total=int(fetch("customer_count")["customers"].iloc[0]),
        order_status=fetch("order_status_summary"),
        monthly=monthly,
        categories=fetch("category_performance"),
        abc=fetch("abc_products"),
        rfm_scored=rfm_scored,
        rfm_segments=summarize_segments(rfm_scored),
        cohort_rows=cohort_rows,
        retention=retention_matrix(cohort_rows),
        channels=fetch("channel_performance"),
        coupons=fetch("coupon_impact"),
        coupon_summary=fetch("coupon_summary"),
        payments=fetch("payment_status"),
        states=fetch("state_revenue"),
    )
