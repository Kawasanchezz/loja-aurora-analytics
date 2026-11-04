import numpy as np
import pandas as pd
import pytest

from aurora.analysis.cohorts import retention_matrix
from aurora.db import split_statements
from aurora.labels import brl, number_br, percent
from aurora.loader import batches, to_records
from aurora.queries import load_queries, parse_queries

NOMES_ESPERADOS = {
    "kpis", "order_status_summary", "customer_count", "monthly_performance", "category_performance",
    "abc_products", "rfm_base", "cohort_retention", "channel_performance", "coupon_impact",
    "coupon_summary", "payment_status", "state_revenue",
}


def test_arquivo_de_consultas_tem_todas_as_consultas():
    assert set(load_queries()) == NOMES_ESPERADOS


def test_consultas_nao_tem_ponto_e_virgula_final_nem_comentarios():
    for nome, sql in load_queries().items():
        assert not sql.endswith(";"), nome
        assert "--" not in sql, nome


def test_consultas_usam_cte_e_funcoes_de_janela():
    texto = "\n".join(load_queries().values())
    assert "WITH " in texto and "LAG(" in texto and "SUM(" in texto and "OVER (" in texto


def test_parser_rejeita_nome_duplicado_e_vazio():
    with pytest.raises(ValueError, match="duplicada"):
        parse_queries("-- name: a\nSELECT 1;\n-- name: a\nSELECT 2;")
    with pytest.raises(ValueError, match="vazia"):
        parse_queries("-- name: a\n-- so comentario\n-- name: b\nSELECT 1;")


def test_split_statements_ignora_comentarios():
    assert split_statements("-- c; ainda comentario\nSELECT 1;\nSELECT 2;") == ["SELECT 1", "SELECT 2"]


def test_to_records_converte_ausentes_em_none():
    df = pd.DataFrame({"id": [1, 2], "coupon_id": pd.array([3, pd.NA], dtype="Int64")})
    registros = to_records(df)
    assert registros[1]["coupon_id"] is None
    assert registros[0]["coupon_id"] == 3 and isinstance(registros[0]["id"], int)


def test_batches_cobre_todos_os_registros():
    registros = [{"i": i} for i in range(2500)]
    assert [len(lote) for lote in batches(registros, 1000)] == [1000, 1000, 500]


def test_formatacao_brasileira():
    assert number_br(1234567.891, 2) == "1.234.567,89"
    assert brl(1500) == "R$ 1.500,00"
    assert percent(12.345) == "12,3%"


def test_matriz_de_retencao_coluna_alem_do_maior_indice_registrado():
    # A coorte mais antiga não tem ninguém ativo no último mês: o mês continua observável (0%).
    linhas = pd.DataFrame({
        "cohort_month": pd.to_datetime(["2025-01-01", "2025-03-01", "2025-03-01"]),
        "month_index": [0, 0, 1],
        "active_customers": [10, 20, 5],
    })
    matriz = retention_matrix(linhas)
    assert matriz.loc[pd.Timestamp("2025-01-01"), 3] == 0
    assert matriz.loc[pd.Timestamp("2025-03-01"), 1] == 25
    assert np.isnan(matriz.loc[pd.Timestamp("2025-03-01"), 2])


def test_matriz_de_retencao():
    linhas = pd.DataFrame({
        "cohort_month": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-02-01"]),
        "month_index": [0, 2, 0],
        "active_customers": [10, 4, 20],
    })
    matriz = retention_matrix(linhas)
    assert matriz.loc[pd.Timestamp("2025-01-01"), 0] == 100
    assert matriz.loc[pd.Timestamp("2025-01-01"), 1] == 0          # mês observável sem ninguém ativo
    assert matriz.loc[pd.Timestamp("2025-01-01"), 2] == 40
    assert np.isnan(matriz.loc[pd.Timestamp("2025-02-01"), 2])      # mês ainda não ocorreu
