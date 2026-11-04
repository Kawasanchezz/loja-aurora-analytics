"""Teste de integração com MySQL real. Só roda se AURORA_TEST_DATABASE estiver definida.

Usa um banco dedicado de teste (init-db apaga as tabelas do banco configurado).
"""
import os
from dataclasses import replace

import pytest
from sqlalchemy import text

from aurora.analysis.pipeline import run_analysis
from aurora.config import load_settings
from aurora.db import apply_schema, make_engine
from aurora.generator import GeneratorConfig, generate
from aurora.loader import load
from aurora.safety import is_safe_test_database

pytestmark = pytest.mark.mysql


@pytest.fixture(scope="module")
def engine():
    banco = os.environ.get("AURORA_TEST_DATABASE")
    if not banco:
        pytest.skip("defina AURORA_TEST_DATABASE para rodar os testes com MySQL")
    try:
        configuracao = load_settings()
    except RuntimeError as erro:
        pytest.skip(f"configuração ausente: {erro}")
    # Trava: o init-db apaga as tabelas; só aceita banco de teste (termina em _test).
    if not is_safe_test_database(banco, configuracao.database):
        pytest.fail(f"AURORA_TEST_DATABASE={banco!r} recusado: use um banco dedicado cujo nome termine em "
                    f"'_test' e seja diferente de {configuracao.database!r}.")
    try:
        engine = make_engine(replace(configuracao, database=banco))
        apply_schema(engine)
    except Exception as erro:  # sem servidor ou sem permissão
        pytest.skip(f"MySQL indisponível: {erro}")
    return engine


@pytest.fixture(scope="module")
def small_data():
    return generate(GeneratorConfig(seed=42, n_customers=800, n_orders=1500))


@pytest.fixture(scope="module")
def loaded(engine, small_data):
    return load(engine, small_data)


def test_carga_em_lotes_insere_todas_as_linhas(loaded, small_data):
    assert loaded == {nome: len(tabela) for nome, tabela in small_data.tables().items()}


def test_carga_e_idempotente(engine, small_data, loaded):
    assert load(engine, small_data) == loaded


def test_carga_e_atomica_rollback_em_erro(engine, small_data, loaded):
    quebrado = replace(small_data, order_items=small_data.order_items.assign(product_id=999_999))
    with pytest.raises(Exception):
        load(engine, quebrado)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM orders")).scalar_one() == len(small_data.orders)


def test_view_exclui_cancelados_e_devolvidos(engine, small_data, loaded):
    with engine.connect() as conn:
        na_view = conn.execute(text("SELECT COUNT(*) FROM vw_order_net_revenue")).scalar_one()
    assert na_view == int((small_data.orders["status"] == "completed").sum())


def test_receita_liquida_do_sql_bate_com_pandas(engine, small_data, loaded):
    itens = small_data.order_items.merge(small_data.orders, left_on="order_id", right_on="id", suffixes=("", "_o"))
    itens = itens[itens["status"] == "completed"].merge(
        small_data.coupons, left_on="coupon_id", right_on="id", how="left", suffixes=("", "_c"))
    bruto = itens["quantity"] * itens["unit_price"]
    desconto = (bruto * itens["discount_pct"].fillna(0) / 100).round(2)
    esperado = float((bruto - desconto).sum())
    with engine.connect() as conn:
        obtido = float(conn.execute(text("SELECT SUM(net_revenue) FROM vw_order_net_revenue")).scalar_one())
    assert obtido == pytest.approx(esperado, abs=1.0)


def test_analise_completa_roda_e_e_consistente(engine, loaded):
    resultados = run_analysis(engine)
    receita = float(resultados.kpis["revenue"])
    assert resultados.monthly["revenue"].sum() == pytest.approx(receita, abs=1.0)
    assert resultados.categories["revenue"].sum() == pytest.approx(receita, abs=1.0)
    assert resultados.abc["cum_share_pct"].iloc[-1] == pytest.approx(100, abs=0.1)
    assert resultados.states["share_pct"].sum() == pytest.approx(100, abs=0.1)
    assert len(resultados.rfm_scored) == int(resultados.kpis["buyers"])
