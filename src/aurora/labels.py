"""Rótulos em português e formatação numérica no padrão brasileiro."""
from __future__ import annotations

CHANNEL_LABELS = {
    "organic": "Orgânico", "paid_search": "Busca paga", "social": "Redes sociais",
    "email": "E-mail", "referral": "Indicação",
}
PAYMENT_LABELS = {"credit_card": "Cartão de crédito", "pix": "Pix", "boleto": "Boleto"}
MONTH_NAMES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _swap_separators(text: str) -> str:
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def number_br(value: float, decimals: int = 0) -> str:
    """1234567.891 -> '1.234.568' (padrão pt-BR)."""
    return _swap_separators(f"{value:,.{decimals}f}")


def brl(value: float, decimals: int = 2) -> str:
    return f"R$ {number_br(value, decimals)}"


def percent(value: float, decimals: int = 1) -> str:
    return f"{number_br(value, decimals)}%"


def month_label(stamp) -> str:
    """Timestamp -> 'nov/2025'."""
    return f"{MONTH_NAMES[stamp.month - 1]}/{stamp.year}"
