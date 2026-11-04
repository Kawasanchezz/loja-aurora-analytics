import pandas as pd

from aurora.generator import GeneratorConfig, black_friday, generate


def test_mesma_seed_gera_mesmos_dados(data):
    outra = generate(GeneratorConfig(seed=42))
    for nome, tabela in data.tables().items():
        pd.testing.assert_frame_equal(tabela, outra.tables()[nome])


def test_seed_diferente_muda_os_dados(data):
    outra = generate(GeneratorConfig(seed=7, n_customers=500, n_orders=800))
    assert not outra.orders["customer_id"].head(50).equals(data.orders["customer_id"].head(50))


def test_volumes_minimos(data):
    assert len(data.customers) == 5000
    assert len(data.products) == 120
    assert len(data.categories) == 8
    assert len(data.orders) >= 10000
    assert data.orders["order_date"].min() >= pd.Timestamp("2024-01-01")
    assert data.orders["order_date"].max() < pd.Timestamp("2026-11-01")


def test_integridade_referencial(data):
    assert data.products["category_id"].isin(data.categories["id"]).all()
    assert data.orders["customer_id"].isin(data.customers["id"]).all()
    assert data.order_items["order_id"].isin(data.orders["id"]).all()
    assert data.order_items["product_id"].isin(data.products["id"]).all()
    assert data.orders["coupon_id"].dropna().isin(data.coupons["id"]).all()


def test_chaves_unicas_e_sem_item_duplicado(data):
    for nome, tabela in data.tables().items():
        assert tabela["id"].is_unique, nome
    assert not data.order_items.duplicated(["order_id", "product_id"]).any()
    assert data.customers["email"].is_unique


def test_regras_de_dominio_do_esquema(data):
    produtos = data.products
    assert (produtos["price"] > 0).all() and (produtos["cost"] >= 0).all()
    assert (produtos["cost"] < produtos["price"]).all()
    assert (data.order_items["quantity"] > 0).all()
    assert data.orders["status"].isin(["completed", "canceled", "returned"]).all()
    assert data.orders["payment_method"].isin(["credit_card", "pix", "boleto"]).all()


def test_nenhum_dado_real_emails_em_dominio_reservado(data):
    assert data.customers["email"].str.endswith("@example.com").all()


def test_cliente_so_compra_depois_de_cadastrado(data):
    juntos = data.orders.merge(data.customers, left_on="customer_id", right_on="id", suffixes=("", "_c"))
    assert (juntos["order_date"] >= juntos["created_at"]).all()


def test_padrao_boleto_cancela_mais(data):
    taxa = data.orders.groupby("payment_method")["status"].apply(lambda s: (s == "canceled").mean())
    assert taxa["boleto"] > 2 * max(taxa["credit_card"], taxa["pix"])


def test_padrao_sazonalidade_novembro_e_dezembro(data):
    por_mes = data.orders.groupby(data.orders["order_date"].dt.to_period("M")).size()
    base = por_mes[[pd.Period("2025-09"), pd.Period("2025-10")]].mean()
    assert por_mes[pd.Period("2025-11")] > 1.15 * base
    assert por_mes[pd.Period("2025-12")] > 1.15 * base


def test_padrao_black_friday_e_o_dia_mais_forte_do_ano(data):
    por_dia = data.orders.groupby(data.orders["order_date"].dt.date).size()
    assert por_dia.idxmax() in {black_friday(2024), black_friday(2025)}


def test_padrao_pareto_20pct_dos_produtos_concentram_receita(data):
    itens = data.order_items.assign(receita=lambda d: d["quantity"] * d["unit_price"])
    por_produto = itens.groupby("product_id")["receita"].sum().sort_values(ascending=False)
    top20 = por_produto.head(round(0.2 * len(data.products))).sum() / por_produto.sum()
    assert top20 > 0.55


def test_padrao_margem_por_categoria(data):
    produtos = data.products.merge(data.categories, left_on="category_id", right_on="id", suffixes=("", "_c"))
    margem = (1 - produtos["cost"] / produtos["price"]).groupby(produtos["name_c"]).mean()
    assert margem["Eletrônicos"] < 0.25 < 0.50 < margem["Beleza e Cuidados"]


def test_padrao_cupom_aumenta_itens_por_pedido(data):
    itens = data.order_items.groupby("order_id").size()
    com_cupom = data.orders["coupon_id"].notna().to_numpy()
    assert itens.to_numpy()[com_cupom].mean() > itens.to_numpy()[~com_cupom].mean()


def test_black_friday_e_sexta_feira():
    assert black_friday(2024).isoformat() == "2024-11-29"
    assert black_friday(2025).isoformat() == "2025-11-28"
    assert black_friday(2026).weekday() == 4
