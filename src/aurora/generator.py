"""Gerador determinístico de dados sintéticos da Loja Aurora (fictícia).

Função pura: ``generate(config)`` não acessa banco nem disco. Mesma seed, mesmos dados.
Nenhuma pessoa ou empresa é real; e-mails usam o domínio reservado example.com.

Padrões embutidos (documentados no README):
  * sazonalidade (Black Friday e Natal) sobre uma tendência de crescimento;
  * curva de Pareto na popularidade dos produtos;
  * canais de aquisição com qualidades diferentes (recompra e volume de compras);
  * boleto com taxa de cancelamento maior;
  * margens diferentes por categoria;
  * cupons que aumentam o ticket bruto e reduzem a margem.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
from faker import Faker

EMAIL_DOMAIN = "example.com"

# nome, margem bruta média, faixa de preço (R$), substantivos dos produtos
CATEGORIES: list[tuple[str, float, tuple[float, float], list[str]]] = [
    ("Eletrônicos", 0.16, (250, 4500), ["Smartphone", "Notebook", "Fone Bluetooth", "Smart TV", "Tablet"]),
    ("Moda", 0.55, (40, 450), ["Jaqueta", "Tênis", "Vestido", "Mochila", "Relógio"]),
    ("Beleza e Cuidados", 0.60, (20, 280), ["Perfume", "Hidratante", "Shampoo", "Maquiagem", "Protetor Solar"]),
    ("Casa e Decoração", 0.42, (30, 900), ["Luminária", "Jogo de Cama", "Panela", "Tapete", "Organizador"]),
    ("Esportes e Lazer", 0.38, (40, 1200), ["Bicicleta", "Halter", "Barraca", "Bola", "Esteira"]),
    ("Livros", 0.30, (20, 140), ["Romance", "Biografia", "Livro Técnico", "HQ", "Livro Infantil"]),
    ("Brinquedos", 0.45, (25, 400), ["Quebra-Cabeça", "Boneca", "Carrinho", "Jogo de Tabuleiro", "Blocos"]),
    ("Alimentos e Bebidas", 0.26, (10, 180), ["Café Especial", "Azeite", "Vinho", "Chocolate", "Castanhas"]),
]
VARIANTS = ["Essencial", "Premium", "Compacto"]

# canal -> (participação na aquisição, multiplicador de atividade de compra)
CHANNELS: dict[str, tuple[float, float]] = {
    "organic": (0.30, 1.0),
    "paid_search": (0.25, 0.8),
    "social": (0.20, 0.55),
    "email": (0.12, 1.3),
    "referral": (0.13, 1.7),
}

STATES: dict[str, float] = {
    "SP": 0.32, "RJ": 0.13, "MG": 0.12, "RS": 0.07, "PR": 0.07, "BA": 0.06,
    "SC": 0.05, "DF": 0.04, "GO": 0.04, "PE": 0.04, "CE": 0.03, "ES": 0.03,
}

# forma de pagamento -> (participação, probabilidade de cancelamento)
PAYMENTS: dict[str, tuple[float, float]] = {
    "credit_card": (0.55, 0.035),
    "pix": (0.30, 0.020),
    "boleto": (0.15, 0.140),
}
RETURN_PROBABILITY = 0.04  # sobre pedidos não cancelados

COUPONS: list[tuple[str, float]] = [
    ("BEMVINDO10", 10.0), ("AURORA15", 15.0), ("CUPOM5", 5.0), ("BLACK25", 25.0), ("NATAL20", 20.0),
]
REGULAR_COUPONS = ["BEMVINDO10", "AURORA15", "CUPOM5"]
REGULAR_COUPON_RATE = 0.16
BLACK_FRIDAY_COUPON_RATE = 0.55
CHRISTMAS_COUPON_RATE = 0.30
COUPON_EXTRA_ITEM_PROBABILITY = 0.40  # cupom aumenta o ticket bruto

MONTH_FACTOR = {1: 0.95, 2: 0.85, 3: 0.90, 4: 0.90, 5: 1.10, 6: 0.95,
                7: 0.90, 8: 0.90, 9: 0.95, 10: 1.00, 11: 1.35, 12: 1.20}
HOUR_WEIGHTS = np.array([1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 7, 7, 7, 7, 7, 7, 7, 8, 9, 10, 10, 9, 6, 3], dtype=float)


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = 42
    n_customers: int = 5000
    n_orders: int = 12000
    start: date = date(2024, 1, 1)
    end: date = date(2026, 10, 31)


@dataclass(frozen=True)
class SyntheticData:
    categories: pd.DataFrame
    products: pd.DataFrame
    coupons: pd.DataFrame
    customers: pd.DataFrame
    orders: pd.DataFrame
    order_items: pd.DataFrame

    def tables(self) -> dict[str, pd.DataFrame]:
        """Tabelas na ordem de carga (pais antes dos filhos)."""
        return {
            "categories": self.categories,
            "products": self.products,
            "coupons": self.coupons,
            "customers": self.customers,
            "orders": self.orders,
            "order_items": self.order_items,
        }


def black_friday(year: int) -> date:
    """Sexta-feira seguinte ao quarto Thursday de novembro."""
    first = date(year, 11, 1)
    first_thursday = first + timedelta(days=(3 - first.weekday()) % 7)
    return first_thursday + timedelta(weeks=3, days=1)


def _event_factor(day: date) -> float:
    delta = (day - black_friday(day.year)).days
    if delta == 0:
        return 4.5
    if 1 <= delta <= 3:
        return 2.0
    if -7 <= delta < 0:
        return 1.3
    if day.month == 12 and day.day <= 24:
        return 1.0 + day.day / 24  # corrida de Natal
    if day.month == 12 and day.day > 25:
        return 0.6
    return 1.0


def daily_weights(days: pd.DatetimeIndex) -> np.ndarray:
    """Peso relativo de pedidos por dia: tendência x mês x fim de semana x eventos."""
    weights = np.empty(len(days))
    for i, stamp in enumerate(days):
        day = stamp.date()
        trend = 1 + 0.30 * i / 365
        weekend = 1.1 if day.weekday() >= 5 else 1.0
        weights[i] = trend * MONTH_FACTOR[day.month] * weekend * _event_factor(day)
    return weights


def _generate_categories_and_products(rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    categories = pd.DataFrame({"id": range(1, len(CATEGORIES) + 1), "name": [c[0] for c in CATEGORIES]})
    rows = []
    product_id = 1
    for category_id, (_, margin_mean, (low, high), nouns) in enumerate(CATEGORIES, start=1):
        for noun in nouns:
            for variant in VARIANTS:
                price = float(np.floor(np.exp(rng.uniform(np.log(low), np.log(high)))) + 0.90)
                margin = float(np.clip(rng.normal(margin_mean, 0.04), 0.05, 0.80))
                rows.append((product_id, category_id, f"{noun} {variant}", price, round(price * (1 - margin), 2)))
                product_id += 1
    products = pd.DataFrame(rows, columns=["id", "category_id", "name", "price", "cost"])
    return categories, products


def _generate_customers(rng: np.random.Generator, fake: Faker, config: GeneratorConfig,
                        days: pd.DatetimeIndex) -> pd.DataFrame:
    n = config.n_customers
    # Mais clientes novos ao longo do tempo (beta com massa à direita).
    offsets = np.sort((rng.beta(1.3, 1.0, size=n) * (len(days) - 1)).astype(int))
    offsets[0] = 0
    seconds = rng.integers(0, 86400, size=n)
    created_at = days[offsets] + pd.to_timedelta(seconds, unit="s")
    created_at = created_at.to_series().reset_index(drop=True)
    created_at.iloc[0] = days[0]  # primeiro cliente existe desde a abertura da loja
    created_at = created_at.sort_values(ignore_index=True)  # ids crescem com a data de cadastro
    channels = list(CHANNELS)
    return pd.DataFrame({
        "id": np.arange(1, n + 1),
        "name": [fake.name() for _ in range(n)],
        "email": [f"cliente{i:05d}@{EMAIL_DOMAIN}" for i in range(1, n + 1)],
        "state": rng.choice(list(STATES), size=n, p=list(STATES.values())),
        "acquisition_channel": rng.choice(channels, size=n, p=[CHANNELS[c][0] for c in channels]),
        "created_at": created_at,
    })


def _order_timestamps(rng: np.random.Generator, days: pd.DatetimeIndex, n_orders: int) -> pd.DatetimeIndex:
    weights = daily_weights(days)
    day_index = rng.choice(len(days), size=n_orders, p=weights / weights.sum())
    hours = rng.choice(24, size=n_orders, p=HOUR_WEIGHTS / HOUR_WEIGHTS.sum())
    seconds = rng.integers(0, 3600, size=n_orders)
    stamps = days[day_index] + pd.to_timedelta(hours * 3600 + seconds, unit="s")
    return stamps.sort_values()


def _assign_customers(rng: np.random.Generator, customers: pd.DataFrame,
                      stamps: pd.DatetimeIndex) -> np.ndarray:
    """Cada pedido escolhe um cliente já cadastrado, com probabilidade proporcional à atividade."""
    channel_boost = customers["acquisition_channel"].map({c: v[1] for c, v in CHANNELS.items()}).to_numpy()
    activity = rng.gamma(shape=0.9, scale=1.0, size=len(customers)) * channel_boost
    cumulative = np.cumsum(activity)
    created = customers["created_at"].to_numpy(dtype="datetime64[ns]")
    eligible = np.searchsorted(created, stamps.to_numpy(dtype="datetime64[ns]"), side="right")
    eligible = np.maximum(eligible, 1)
    draws = rng.random(len(stamps)) * cumulative[eligible - 1]
    chosen = np.minimum(np.searchsorted(cumulative, draws, side="right"), eligible - 1)
    return customers["id"].to_numpy()[chosen]


def _assign_coupons(rng: np.random.Generator, stamps: pd.DatetimeIndex,
                    coupon_ids: dict[str, int]) -> np.ndarray:
    """Devolve o id do cupom por pedido (0 = sem cupom)."""
    n = len(stamps)
    draw = rng.random(n)
    regular = rng.choice([coupon_ids[c] for c in REGULAR_COUPONS], size=n, p=[0.5, 0.3, 0.2])
    deltas = np.array([(s.date() - black_friday(s.year)).days for s in stamps])
    in_black_friday = (deltas >= -3) & (deltas <= 3)
    in_christmas = (stamps.month == 12) & (stamps.day <= 25)

    result = np.where(draw < REGULAR_COUPON_RATE, regular, 0)
    result = np.where(in_christmas & (draw < CHRISTMAS_COUPON_RATE), coupon_ids["NATAL20"], result)
    result = np.where(in_black_friday & (draw < BLACK_FRIDAY_COUPON_RATE), coupon_ids["BLACK25"], result)
    return result


def _assign_status(rng: np.random.Generator, payments: np.ndarray) -> np.ndarray:
    cancel_probability = np.array([PAYMENTS[p][1] for p in payments])
    canceled = rng.random(len(payments)) < cancel_probability
    returned = rng.random(len(payments)) < RETURN_PROBABILITY
    return np.where(canceled, "canceled", np.where(returned, "returned", "completed"))


def _generate_items(rng: np.random.Generator, products: pd.DataFrame, has_coupon: np.ndarray) -> pd.DataFrame:
    """Itens por pedido. Popularidade dos produtos segue uma lei de potência (Pareto)."""
    n_products = len(products)
    ranks = rng.permutation(n_products) + 1
    popularity = 1.0 / ranks ** 1.1
    popularity /= popularity.sum()
    prices = products["price"].to_numpy()
    costs = products["cost"].to_numpy()
    product_ids = products["id"].to_numpy()

    base_items = rng.choice([1, 2, 3, 4], size=len(has_coupon), p=[0.50, 0.28, 0.14, 0.08])
    extra = (rng.random(len(has_coupon)) < COUPON_EXTRA_ITEM_PROBABILITY) & has_coupon
    n_items = np.minimum(base_items + extra, 4)

    rows = []
    item_id = 1
    for order_id, count in enumerate(n_items, start=1):
        picked = rng.choice(n_products, size=count, replace=False, p=popularity)
        for index in picked:
            quantity = 1 if prices[index] > 1500 else int(rng.choice([1, 2, 3], p=[0.80, 0.15, 0.05]))
            rows.append((item_id, order_id, int(product_ids[index]), quantity, float(prices[index]), float(costs[index])))
            item_id += 1
    return pd.DataFrame(rows, columns=["id", "order_id", "product_id", "quantity", "unit_price", "unit_cost"])


def generate(config: GeneratorConfig = GeneratorConfig()) -> SyntheticData:
    """Gera todas as tabelas. Determinístico para uma mesma configuração."""
    rng = np.random.default_rng(config.seed)
    fake = Faker("pt_BR")
    fake.seed_instance(config.seed)
    days = pd.date_range(config.start, config.end, freq="D")

    categories, products = _generate_categories_and_products(rng)
    coupons = pd.DataFrame(
        [(i, code, pct) for i, (code, pct) in enumerate(COUPONS, start=1)],
        columns=["id", "code", "discount_pct"],
    )
    coupon_ids = dict(zip(coupons["code"], coupons["id"]))
    customers = _generate_customers(rng, fake, config, days)

    stamps = _order_timestamps(rng, days, config.n_orders)
    payment_names = list(PAYMENTS)
    payments = rng.choice(payment_names, size=config.n_orders, p=[PAYMENTS[p][0] for p in payment_names])
    coupon_per_order = _assign_coupons(rng, stamps, coupon_ids)
    orders = pd.DataFrame({
        "id": np.arange(1, config.n_orders + 1),
        "customer_id": _assign_customers(rng, customers, stamps),
        "coupon_id": pd.array(np.where(coupon_per_order == 0, pd.NA, coupon_per_order), dtype="Int64"),
        "order_date": stamps,
        "status": _assign_status(rng, payments),
        "payment_method": payments,
    })
    items = _generate_items(rng, products, coupon_per_order > 0)
    return SyntheticData(categories, products, coupons, customers, orders, items)
