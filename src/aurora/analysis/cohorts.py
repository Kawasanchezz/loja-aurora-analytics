"""Matriz de retenção por coorte a partir da consulta cohort_retention."""
from __future__ import annotations

import numpy as np
import pandas as pd


def retention_matrix(cohort_rows: pd.DataFrame) -> pd.DataFrame:
    """Percentual de clientes da coorte ativos em cada mês desde o primeiro pedido.

    Linhas = mês da coorte; colunas = meses desde a coorte (0 = 100%).
    Células que ainda não aconteceram (depois do último mês dos dados) ficam NaN;
    meses observáveis sem nenhum cliente ativo ficam 0.
    """
    if cohort_rows.empty:
        return pd.DataFrame()
    rows = cohort_rows.copy()
    rows["cohort_month"] = pd.to_datetime(rows["cohort_month"])
    counts = rows.pivot(index="cohort_month", columns="month_index", values="active_customers")

    # Último mês observado nos dados = maior (mês da coorte + índice do mês).
    cohort_number = rows["cohort_month"].dt.year * 12 + rows["cohort_month"].dt.month
    last_number = int((cohort_number + rows["month_index"]).max())
    counts = counts.reindex(columns=range(last_number - int(cohort_number.min()) + 1))
    retention = pd.DataFrame(np.nan, index=counts.index, columns=counts.columns)
    for cohort in counts.index:
        observable = last_number - (cohort.year * 12 + cohort.month)
        base = counts.loc[cohort, 0]
        for month_index in range(observable + 1):
            active = counts.loc[cohort, month_index]
            retention.loc[cohort, month_index] = 0.0 if pd.isna(active) else 100 * active / base
    return retention
