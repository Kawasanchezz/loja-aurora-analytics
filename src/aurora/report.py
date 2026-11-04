"""Geração do relatório em Markdown. Todo número vem dos resultados da análise (nada é digitado à mão)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from aurora.analysis.pipeline import AnalysisResults
from aurora.labels import CHANNEL_LABELS, PAYMENT_LABELS, brl, month_label, number_br, percent


def md_table(df: pd.DataFrame, headers: dict[str, str], formats: dict[str, callable] | None = None) -> str:
    """Tabela Markdown com as colunas de ``headers`` (coluna -> título)."""
    formats = formats or {}
    lines = ["| " + " | ".join(headers.values()) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for _, row in df.iterrows():
        cells = [formats.get(col, str)(row[col]) for col in headers]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _seasonal_lift(monthly: pd.DataFrame, month: int) -> list[str]:
    """Para cada ano com o mês dado, compara com a média dos dois meses anteriores."""
    lines = []
    indexed = monthly.set_index("month")["revenue"]
    for stamp in indexed.index[indexed.index.month == month]:
        previous = indexed[(indexed.index < stamp)].tail(2)
        if len(previous) == 2:
            lift = 100 * (indexed[stamp] / previous.mean() - 1)
            lines.append(f"{month_label(stamp)}: {brl(indexed[stamp], 0)}, {percent(lift)} acima da média dos dois meses anteriores")
    return lines


def _year_over_year(monthly: pd.DataFrame) -> str:
    last = monthly["month"].max()
    current = monthly[monthly["month"].dt.year == last.year]
    previous = monthly[(monthly["month"].dt.year == last.year - 1) & (monthly["month"].dt.month <= last.month)]
    if previous.empty or len(current) != len(previous):
        return "Não há dados suficientes para comparar com o mesmo período do ano anterior."
    growth = 100 * (current["revenue"].sum() / previous["revenue"].sum() - 1)
    direction = "acima" if growth >= 0 else "abaixo"
    return (f"De janeiro a {month_label(last)}, a receita líquida foi {brl(current['revenue'].sum(), 0)}, "
            f"{percent(abs(growth))} {direction} do mesmo período de {last.year - 1} ({brl(previous['revenue'].sum(), 0)}).")


def _peak_margin_line(monthly: pd.DataFrame) -> str:
    """Compara a margem média de nov/dez com a dos demais meses (média simples dos meses)."""
    is_peak = monthly["month"].dt.month.isin([11, 12])
    peak, rest = monthly.loc[is_peak, "margin_pct"].mean(), monthly.loc[~is_peak, "margin_pct"].mean()
    return (f"Margem média de novembro e dezembro: {percent(peak)}; nos demais meses: {percent(rest)} "
            f"(diferença de {number_br(peak - rest, 1)} p.p.).")


def _retention_line(results: AnalysisResults) -> str:
    matrix = results.retention
    parts = []
    for month_index in (1, 3, 6):
        if month_index in matrix.columns:
            values = matrix[month_index].dropna()
            if not values.empty:
                parts.append(f"mês {month_index}: {percent(values.mean())}")
    return ", ".join(parts) if parts else "sem dados suficientes"


def build_report(results: AnalysisResults) -> str:
    k = results.kpis
    monthly, categories, abc = results.monthly, results.categories, results.abc
    channels, payments, states = results.channels, results.payments, results.states
    coupons = results.coupon_summary.set_index("coupon_group")
    status = results.order_status.set_index("status")["orders"]
    total_orders = int(status.sum())

    best_month = monthly.loc[monthly["revenue"].idxmax()]
    top_category = categories.iloc[0]
    margin_top = categories.loc[categories["margin_pct"].idxmax()]
    margin_low = categories.loc[categories["margin_pct"].idxmin()]
    a_products = abc[abc["abc_class"] == "A"]
    top20_n = max(1, round(0.2 * len(abc)))
    top20_share = abc.loc[abc["rank_pos"] <= top20_n, "share_pct"].sum()
    segments = results.rfm_segments.set_index("segment")
    best_channel, worst_channel = channels.iloc[0], channels.iloc[-1]
    boleto = payments[payments["payment_method"] == "boleto"].iloc[0]
    others = payments[payments["payment_method"] != "boleto"]
    others_cancel = 100 * others["canceled"].sum() / others["orders"].sum()
    with_c, without_c = coupons.loc["Com cupom"], coupons.loc["Sem cupom"]
    top3_states = states.head(3)
    discounted = results.coupons[results.coupons["coupon"] != "Sem cupom"]
    worst_coupon = discounted.loc[discounted["margin_pct"].idxmin()]

    out: list[str] = []
    add = out.append
    add("# Relatório de análise: Loja Aurora\n")
    add("> **Dados 100% fictícios**, gerados por script com seed fixa. As conclusões descrevem o conjunto simulado, "
        "não um negócio real. Este arquivo é gerado automaticamente por `python -m aurora report`.\n")

    add("## 1. Indicadores principais\n")
    add(f"Período dos pedidos: {pd.Timestamp(k['first_order']):%d/%m/%Y} a {pd.Timestamp(k['last_order']):%d/%m/%Y}.\n")
    add(md_table(pd.DataFrame([
        ("Receita líquida", brl(k["revenue"], 0)),
        ("Lucro bruto", brl(k["profit"], 0)),
        ("Margem de lucro", percent(k["margin_pct"])),
        ("Pedidos concluídos", number_br(k["completed_orders"])),
        ("Ticket médio líquido", brl(k["aov"])),
        ("Clientes cadastrados", number_br(results.customers_total)),
        ("Clientes com compra concluída", number_br(k["buyers"])),
        ("Pedidos cancelados", f"{number_br(status.get('canceled', 0))} ({percent(100 * status.get('canceled', 0) / total_orders)})"),
        ("Pedidos devolvidos", f"{number_br(status.get('returned', 0))} ({percent(100 * status.get('returned', 0) / total_orders)})"),
    ], columns=["i", "v"]), {"i": "Indicador", "v": "Valor"}))
    add("\nReceita líquida = valor dos pedidos concluídos menos o desconto do cupom. "
        "Lucro bruto = receita líquida menos o custo dos produtos.\n")

    add("## 2. Receita, lucro e margem mensal\n")
    add("![Receita e margem mensal](figures/01_receita_margem_mensal.png)\n")
    add(f"- Melhor mês: **{month_label(best_month['month'])}**, com {brl(best_month['revenue'], 0)} "
        f"e margem de {percent(best_month['margin_pct'])}.")
    for line in _seasonal_lift(monthly, 11) + _seasonal_lift(monthly, 12):
        add(f"- {line}.")
    add(f"- {_year_over_year(monthly)}")
    add(f"- Margem mensal entre {percent(monthly['margin_pct'].min())} e {percent(monthly['margin_pct'].max())}.")
    add(f"- {_peak_margin_line(monthly)}\n")
    add("<details><summary>Tabela mensal</summary>\n")
    add(md_table(monthly.assign(month=monthly["month"].map(month_label)),
                 {"month": "Mês", "orders": "Pedidos", "revenue": "Receita", "profit": "Lucro",
                  "margin_pct": "Margem", "mom_growth_pct": "Var. mês a mês"},
                 {"orders": number_br, "revenue": lambda v: brl(v, 0), "profit": lambda v: brl(v, 0),
                  "margin_pct": percent, "mom_growth_pct": lambda v: "-" if pd.isna(v) else percent(v)}))
    add("\n</details>\n")

    add("## 3. Categorias\n")
    add("![Categorias](figures/02_categorias.png)\n")
    add(md_table(categories, {"category": "Categoria", "units": "Unidades", "revenue": "Receita", "margin_pct": "Margem",
                              "revenue_share_pct": "% da receita"},
                 {"units": number_br, "revenue": lambda v: brl(v, 0), "margin_pct": percent, "revenue_share_pct": percent}))
    add(f"\n- Maior receita: **{top_category['category']}** ({percent(top_category['revenue_share_pct'])} do total, "
        f"margem {percent(top_category['margin_pct'])}).")
    add(f"- Maior margem: **{margin_top['category']}** ({percent(margin_top['margin_pct'])}); "
        f"menor margem: **{margin_low['category']}** ({percent(margin_low['margin_pct'])}).\n")

    add("## 4. Curva ABC de produtos\n")
    add("![Curva ABC](figures/03_curva_abc.png)\n")
    counts = abc["abc_class"].value_counts()
    add(f"- Classe A: {counts.get('A', 0)} produtos; B: {counts.get('B', 0)}; C: {counts.get('C', 0)} (total {len(abc)}).")
    add(f"- Os {top20_n} produtos mais vendidos (20% do catálogo) geram {percent(top20_share)} da receita líquida.")
    add(f"- Produto líder: **{abc.iloc[0]['name']}** ({abc.iloc[0]['category']}), {percent(abc.iloc[0]['share_pct'])} da receita.\n")

    add("## 5. Segmentação RFM\n")
    add("![Segmentos RFM](figures/04_rfm_segmentos.png)\n")
    add(md_table(results.rfm_segments, {"segment": "Segmento", "customers": "Clientes", "customer_share_pct": "% clientes",
                                         "revenue_share_pct": "% receita", "avg_orders": "Pedidos/cliente",
                                         "avg_recency_days": "Dias desde a última compra"},
                 {"customers": number_br, "customer_share_pct": percent, "revenue_share_pct": percent,
                  "avg_orders": lambda v: number_br(v, 2), "avg_recency_days": lambda v: number_br(v, 0)}))
    if "Campeões" in segments.index:
        champions = segments.loc["Campeões"]
        add(f"\n- Campeões: {percent(champions['customer_share_pct'])} dos clientes e {percent(champions['revenue_share_pct'])} da receita.")
    if "Em risco" in segments.index:
        risk = segments.loc["Em risco"]
        add(f"- Em risco (3 ou mais pedidos, mas sem comprar há muito tempo): {number_br(risk['customers'])} clientes, "
            f"{percent(risk['revenue_share_pct'])} da receita histórica.")
    add("\nNotas R e M por quintil; F por faixas fixas (1, 2, 3, 4, 5+ pedidos). Veja `src/aurora/analysis/rfm.py`.\n")

    add("## 6. Retenção por coorte\n")
    add("![Retenção por coorte](figures/05_retencao_coortes.png)\n")
    add(f"- Retenção média entre as coortes (média simples): {_retention_line(results)}.")
    add("- Coorte = mês do primeiro pedido concluído; cliente \"ativo\" = fez ao menos um pedido concluído no mês.\n")

    add("## 7. Canais de aquisição\n")
    add("![Canais](figures/06_canais_aquisicao.png)\n")
    add(md_table(channels.assign(channel=channels["channel"].map(CHANNEL_LABELS)),
                 {"channel": "Canal", "customers_acquired": "Clientes", "conversion_pct": "% que compraram",
                  "revenue_per_customer": "Receita/cliente", "repeat_rate_pct": "% recompra",
                  "aov": "Ticket médio", "margin_pct": "Margem", "cancel_rate_pct": "% cancel."},
                 {"customers_acquired": number_br, "conversion_pct": percent, "revenue_per_customer": brl,
                  "repeat_rate_pct": percent, "aov": brl, "margin_pct": percent, "cancel_rate_pct": percent}))
    ratio = best_channel["revenue_per_customer"] / worst_channel["revenue_per_customer"]
    add(f"\n- Melhor canal por receita por cliente adquirido: **{CHANNEL_LABELS[best_channel['channel']]}** "
        f"({brl(best_channel['revenue_per_customer'])}); pior: **{CHANNEL_LABELS[worst_channel['channel']]}** "
        f"({brl(worst_channel['revenue_per_customer'])}), uma diferença de {number_br(ratio, 1)}x.")
    add("- Este relatório não inclui custo de aquisição por canal (a base não tem gasto de marketing), "
        "então não calcula CAC nem ROAS.\n")

    add("## 8. Cupons\n")
    add("![Cupons](figures/07_cupons.png)\n")
    add(md_table(results.coupons, {"coupon": "Cupom", "discount_pct": "Desconto", "orders": "Pedidos",
                                    "gross_ticket": "Ticket bruto", "net_ticket": "Ticket líquido", "margin_pct": "Margem"},
                 {"discount_pct": lambda v: percent(v, 0), "orders": number_br, "gross_ticket": brl,
                  "net_ticket": brl, "margin_pct": percent}))
    add(f"\n- Pedidos com cupom: ticket bruto de {brl(with_c['gross_ticket'])} contra {brl(without_c['gross_ticket'])} sem cupom; "
        f"após o desconto, {brl(with_c['net_ticket'])} contra {brl(without_c['net_ticket'])}.")
    add(f"- Margem com cupom: {percent(with_c['margin_pct'])}; sem cupom: {percent(without_c['margin_pct'])} "
        f"(queda de {number_br(without_c['margin_pct'] - with_c['margin_pct'], 1)} p.p.).")
    add(f"- Cupom de pior margem: **{worst_coupon['coupon']}** ({percent(worst_coupon['discount_pct'], 0)} de desconto), "
        f"com margem de {percent(worst_coupon['margin_pct'])} em {number_br(worst_coupon['orders'])} pedidos.\n")

    add("## 9. Cancelamento e devolução por forma de pagamento\n")
    add("![Pagamento](figures/08_pagamento.png)\n")
    add(md_table(payments.assign(payment_method=payments["payment_method"].map(PAYMENT_LABELS)),
                 {"payment_method": "Pagamento", "orders": "Pedidos", "canceled": "Cancelados", "cancel_rate_pct": "% cancel.",
                  "returned": "Devolvidos", "return_rate_pct": "% devol."},
                 {"orders": number_br, "canceled": number_br, "returned": number_br,
                  "cancel_rate_pct": percent, "return_rate_pct": percent}))
    add(f"\n- Boleto: {percent(boleto['cancel_rate_pct'])} de cancelamento, contra {percent(others_cancel)} nas demais formas "
        f"({number_br(boleto['cancel_rate_pct'] / others_cancel, 1)}x).\n")

    add("## 10. Receita por estado\n")
    add("![Receita por estado](figures/09_receita_por_estado.png)\n")
    add(md_table(states.head(10), {"state": "UF", "buyers": "Compradores", "orders": "Pedidos", "revenue": "Receita",
                                   "share_pct": "% da receita", "margin_pct": "Margem"},
                 {"buyers": number_br, "orders": number_br, "revenue": lambda v: brl(v, 0),
                  "share_pct": percent, "margin_pct": percent}))
    add(f"\n- {', '.join(top3_states['state'])} concentram {percent(top3_states['share_pct'].sum())} da receita.\n")

    add("## 11. Recomendações\n")
    add(f"1. **Estoque e campanhas sazonais:** concentrar estoque e verba em novembro e dezembro, os meses de pico "
        f"(melhor mês: {month_label(best_month['month'])}).")
    add(f"2. **Mix de produtos:** proteger a disponibilidade dos {len(a_products)} produtos da classe A e revisar os da classe C.")
    add(f"3. **Margem:** priorizar a exposição de {margin_top['category']} (margem {percent(margin_top['margin_pct'])}) "
        f"e revisar preço ou custo de {margin_low['category']} (margem {percent(margin_low['margin_pct'])}).")
    add(f"4. **Retenção:** criar réguas de reativação para os clientes do segmento \"Em risco\" e programa de fidelidade para os Campeões.")
    add(f"5. **Canais:** investir mais em {CHANNEL_LABELS[best_channel['channel']]} e reavaliar {CHANNEL_LABELS[worst_channel['channel']]}, "
        "após cruzar com o custo de aquisição (não disponível nesta base).")
    add(f"6. **Cupons:** rever o desconto do cupom {worst_coupon['coupon']} (margem de {percent(worst_coupon['margin_pct'])}); "
        f"em média, pedidos com cupom têm margem {number_br(without_c['margin_pct'] - with_c['margin_pct'], 1)} p.p. menor.")
    add(f"7. **Pagamento:** incentivar Pix no lugar de boleto (cancelamento de {percent(boleto['cancel_rate_pct'])} no boleto).\n")

    add("## Limitações\n")
    add("- Os dados são simulados: padrões como sazonalidade e a diferença do boleto foram embutidos de propósito no gerador.")
    add("- Não há custo de frete, de marketing nem estoque; o lucro é bruto (receita líquida menos custo do produto).")
    add("- Cancelados e devolvidos são excluídos da receita; não há estorno parcial nem data de devolução.")
    return "\n".join(out) + "\n"


def write_report(results: AnalysisResults, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(results), encoding="utf-8")
    return path
