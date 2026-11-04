"""Gráficos em PNG: um eixo por gráfico, rótulos diretos e paleta daltônica (Okabe-Ito)."""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend sem janela: funciona em servidores e no CI
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402

from aurora.analysis.pipeline import AnalysisResults  # noqa: E402
from aurora.labels import CHANNEL_LABELS, PAYMENT_LABELS, brl, month_label, number_br, percent  # noqa: E402

logger = logging.getLogger(__name__)

BLUE, ORANGE, GREY, GREEN, RED = "#0072B2", "#E69F00", "#9AA0A6", "#009E73", "#D55E00"
INK = "#222222"
DPI = 150

plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": GREY, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK, "ytick.color": INK, "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
})


def _save(fig: plt.Figure, directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Gráfico salvo: %s", path.name)
    return path


def _hbar(ax: Axes, labels: list[str], values: list[float], colors, fmt) -> None:
    """Barras horizontais com valor escrito na ponta (sem eixo de valores)."""
    positions = range(len(labels))
    ax.barh(positions, values, color=colors)
    ax.set_yticks(list(positions), labels)
    ax.set_ylim(len(labels) - 0.5, -0.5)  # primeira categoria no topo (idempotente com sharey)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    limit = max(values) if values else 1
    for position, value in zip(positions, values):
        ax.text(value + limit * 0.01, position, fmt(value), va="center", fontsize=9)
    ax.set_xlim(0, limit * 1.18)


def monthly_revenue(results: AnalysisResults, directory: Path) -> Path:
    monthly = results.monthly
    peak_months = monthly["month"].dt.month.isin([11, 12])
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(10, 7), sharex=True, height_ratios=[3, 2])
    top.bar(monthly["month"], monthly["revenue"] / 1000, width=22, color=[ORANGE if p else BLUE for p in peak_months])
    top.set_title("Receita líquida mensal (R$ mil): novembro e dezembro em laranja", loc="left", fontweight="bold")
    top.set_ylabel("R$ mil")
    for _, row in monthly[peak_months].iterrows():
        top.text(row["month"], row["revenue"] / 1000, number_br(row["revenue"] / 1000), ha="center", va="bottom", fontsize=8)

    bottom.plot(monthly["month"], monthly["margin_pct"], color=GREEN, marker="o", markersize=3)
    bottom.set_title("Margem de lucro mensal (%)", loc="left", fontweight="bold")
    bottom.set_ylabel("% da receita líquida")
    bottom.set_ylim(0, max(monthly["margin_pct"].max() * 1.25, 1))
    last = monthly.iloc[-1]
    bottom.annotate(percent(last["margin_pct"]), (last["month"], last["margin_pct"]),
                    textcoords="offset points", xytext=(6, 4), fontsize=9, color=GREEN)
    bottom.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m/%y"))
    fig.tight_layout()
    return _save(fig, directory, "01_receita_margem_mensal.png")


def category_margin(results: AnalysisResults, directory: Path) -> Path:
    data = results.categories.sort_values("revenue", ascending=False)
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 5), sharey=True)
    _hbar(left, list(data["category"]), list(data["revenue"] / 1000), BLUE, lambda v: f"R$ {number_br(v)} mil")
    left.set_title("Receita líquida", loc="left", fontweight="bold")
    _hbar(right, list(data["category"]), list(data["margin_pct"]), GREEN, lambda v: percent(v))
    right.set_title("Margem de lucro", loc="left", fontweight="bold")
    right.tick_params(axis="y", left=False)
    fig.suptitle("Categorias: quem vende mais nem sempre lucra mais", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    return _save(fig, directory, "02_categorias.png")


def abc_curve(results: AnalysisResults, directory: Path) -> Path:
    abc = results.abc
    n = len(abc)
    x = 100 * abc["rank_pos"] / n
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(x, abc["cum_share_pct"], color=BLUE, linewidth=2)
    ax.axhline(80, color=GREY, linestyle="--", linewidth=1)
    a_count = int((abc["abc_class"] == "A").sum())
    a_pct = 100 * a_count / n
    ax.scatter([a_pct], [abc.loc[abc["abc_class"] == "A", "cum_share_pct"].max()], color=ORANGE, zorder=3)
    ax.annotate(f"{a_count} produtos ({percent(a_pct, 0)} do catálogo) formam a classe A",
                (a_pct, abc.loc[abc["abc_class"] == "A", "cum_share_pct"].max()),
                textcoords="offset points", xytext=(12, -22), fontsize=9)
    ax.text(100, 81.5, "80% da receita", ha="right", fontsize=9, color=GREY)
    ax.set_xlabel("% acumulada de produtos (do mais ao menos vendido)")
    ax.set_ylabel("% acumulada da receita líquida")
    ax.set_title("Curva ABC de produtos", loc="left", fontweight="bold")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 102)
    return _save(fig, directory, "03_curva_abc.png")


def rfm_segments(results: AnalysisResults, directory: Path) -> Path:
    data = results.rfm_segments
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    _hbar(left, list(data["segment"]), list(data["customer_share_pct"]), GREY, lambda v: percent(v))
    left.set_title("% dos clientes", loc="left", fontweight="bold")
    _hbar(right, list(data["segment"]), list(data["revenue_share_pct"]), BLUE, lambda v: percent(v))
    right.set_title("% da receita", loc="left", fontweight="bold")
    right.tick_params(axis="y", left=False)
    fig.suptitle("Segmentos RFM: poucos clientes concentram a receita", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    return _save(fig, directory, "04_rfm_segmentos.png")


def cohort_heatmap(results: AnalysisResults, directory: Path, max_months: int = 12) -> Path:
    retention = results.retention.iloc[:, 1: max_months + 1]  # o mês 0 é sempre 100% e fica fora
    fig, ax = plt.subplots(figsize=(11, 9))
    image = ax.imshow(retention.to_numpy(dtype=float), cmap="Blues", vmin=0, vmax=40, aspect="auto")
    ax.set_xticks(range(retention.shape[1]), [str(c) for c in retention.columns])
    ax.set_yticks(range(len(retention)), [month_label(c) for c in retention.index], fontsize=8)
    for i in range(retention.shape[0]):
        for j in range(retention.shape[1]):
            value = retention.iat[i, j]
            if pd.notna(value):
                ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7,
                        color="white" if value > 25 else INK)
    ax.set_xlabel("Meses desde o primeiro pedido")
    ax.set_ylabel("Coorte (mês do primeiro pedido concluído)")
    ax.set_title("Retenção por coorte: % de clientes que voltam a comprar", loc="left", fontweight="bold")
    fig.colorbar(image, ax=ax, label="% de clientes da coorte (escala limitada a 40%)", shrink=0.7)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return _save(fig, directory, "05_retencao_coortes.png")


def channel_quality(results: AnalysisResults, directory: Path) -> Path:
    data = results.channels
    labels = [CHANNEL_LABELS.get(c, c) for c in data["channel"]]
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    _hbar(left, labels, list(data["revenue_per_customer"]), BLUE, lambda v: brl(v))
    left.set_title("Receita líquida por cliente adquirido", loc="left", fontweight="bold")
    _hbar(right, labels, list(data["repeat_rate_pct"]), GREEN, lambda v: percent(v))
    right.set_title("% de compradores que recompram", loc="left", fontweight="bold")
    right.tick_params(axis="y", left=False)
    fig.tight_layout()
    return _save(fig, directory, "06_canais_aquisicao.png")


def coupon_impact(results: AnalysisResults, directory: Path) -> Path:
    data = results.coupon_summary.set_index("coupon_group").reindex(["Sem cupom", "Com cupom"])
    fig, (left, right) = plt.subplots(1, 2, figsize=(10, 4.5))
    colors = [GREY, ORANGE]
    for ax, column, title, fmt in [
        (left, "net_ticket", "Ticket médio líquido (R$)", lambda v: brl(v)),
        (right, "margin_pct", "Margem de lucro (%)", lambda v: percent(v)),
    ]:
        ax.bar(data.index, data[column], color=colors, width=0.55)
        for position, value in enumerate(data[column]):
            ax.text(position, value, fmt(value), ha="center", va="bottom", fontsize=10)
        ax.set_title(title, loc="left", fontweight="bold")
        ax.set_ylim(0, data[column].max() * 1.15)
        ax.yaxis.set_visible(False)
        ax.spines["left"].set_visible(False)
    fig.suptitle("Pedidos com cupom x sem cupom", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    return _save(fig, directory, "07_cupons.png")


def payment_failures(results: AnalysisResults, directory: Path) -> Path:
    data = results.payments
    labels = [PAYMENT_LABELS.get(p, p) for p in data["payment_method"]]
    fig, (left, right) = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    colors = [RED if p == "boleto" else GREY for p in data["payment_method"]]
    _hbar(left, labels, list(data["cancel_rate_pct"]), colors, lambda v: percent(v))
    left.set_title("Taxa de cancelamento", loc="left", fontweight="bold")
    _hbar(right, labels, list(data["return_rate_pct"]), GREY, lambda v: percent(v))
    right.set_title("Taxa de devolução (entre não cancelados)", loc="left", fontweight="bold")
    right.tick_params(axis="y", left=False)
    fig.tight_layout()
    return _save(fig, directory, "08_pagamento.png")


def state_revenue(results: AnalysisResults, directory: Path, top: int = 10) -> Path:
    data = results.states.head(top)
    fig, ax = plt.subplots(figsize=(9, 5))
    _hbar(ax, list(data["state"]), list(data["revenue"] / 1000),
          BLUE, lambda v: f"R$ {number_br(v)} mil")
    ax.set_title(f"Receita líquida por estado (top {len(data)})", loc="left", fontweight="bold")
    return _save(fig, directory, "09_receita_por_estado.png")


def render_all(results: AnalysisResults, directory: Path) -> list[Path]:
    builders = [monthly_revenue, category_margin, abc_curve, rfm_segments, cohort_heatmap,
                channel_quality, coupon_impact, payment_failures, state_revenue]
    return [builder(results, directory) for builder in builders]
