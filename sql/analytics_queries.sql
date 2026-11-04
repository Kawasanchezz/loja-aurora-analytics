-- Consultas analíticas nomeadas. Cada bloco começa com "-- name: <id>" e é lido por src/aurora/queries.py.
-- Convenção: a agregação pesada fica aqui; o pandas só aplica scoring e formatação.
-- Receita líquida = pedidos concluídos, com desconto de cupom (views vw_*_net_revenue).

-- name: kpis
SELECT
    COUNT(*)                                          AS completed_orders,
    COUNT(DISTINCT customer_id)                       AS buyers,
    ROUND(SUM(net_revenue), 2)                        AS revenue,
    ROUND(SUM(profit), 2)                             AS profit,
    ROUND(100 * SUM(profit) / SUM(net_revenue), 2)    AS margin_pct,
    ROUND(AVG(net_revenue), 2)                        AS aov,
    MIN(order_date)                                   AS first_order,
    MAX(order_date)                                   AS last_order
FROM vw_order_net_revenue;

-- name: order_status_summary
SELECT status, COUNT(*) AS orders, ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS share_pct
FROM orders
GROUP BY status
ORDER BY orders DESC;

-- name: customer_count
SELECT COUNT(*) AS customers FROM customers;

-- name: monthly_performance
-- 1) Receita, lucro e margem mensal, com crescimento mês a mês (LAG).
WITH monthly AS (
    SELECT
        CAST(DATE_FORMAT(order_date, '%Y-%m-01') AS DATE) AS month,
        COUNT(*)        AS orders,
        SUM(net_revenue) AS revenue,
        SUM(profit)      AS profit
    FROM vw_order_net_revenue
    GROUP BY CAST(DATE_FORMAT(order_date, '%Y-%m-01') AS DATE)
)
SELECT
    month,
    orders,
    ROUND(revenue, 2)                                  AS revenue,
    ROUND(profit, 2)                                   AS profit,
    ROUND(100 * profit / revenue, 2)                   AS margin_pct,
    ROUND(100 * (revenue - LAG(revenue) OVER (ORDER BY month))
              / LAG(revenue) OVER (ORDER BY month), 2) AS mom_growth_pct
FROM monthly
ORDER BY month;

-- name: category_performance
-- 2) Receita e margem por categoria, com participação na receita total (SUM OVER).
SELECT
    c.name                                                         AS category,
    SUM(i.quantity)                                                AS units,
    ROUND(SUM(i.net_revenue), 2)                                   AS revenue,
    ROUND(SUM(i.net_revenue - i.cogs), 2)                          AS profit,
    ROUND(100 * SUM(i.net_revenue - i.cogs) / SUM(i.net_revenue), 2) AS margin_pct,
    ROUND(100 * SUM(i.net_revenue) / SUM(SUM(i.net_revenue)) OVER (), 2) AS revenue_share_pct
FROM vw_item_net_revenue i
JOIN products p   ON p.id = i.product_id
JOIN categories c ON c.id = p.category_id
GROUP BY c.name
ORDER BY revenue DESC;

-- name: abc_products
-- 3) Curva ABC: A = produtos que somam até 80% da receita, B até 95%, C o restante.
WITH product_revenue AS (
    SELECT
        p.id AS product_id, p.name, c.name AS category,
        SUM(i.net_revenue)            AS revenue,
        SUM(i.net_revenue - i.cogs)   AS profit
    FROM vw_item_net_revenue i
    JOIN products p   ON p.id = i.product_id
    JOIN categories c ON c.id = p.category_id
    GROUP BY p.id, p.name, c.name
),
ranked AS (
    SELECT
        product_id, name, category, revenue, profit,
        ROW_NUMBER() OVER (ORDER BY revenue DESC, product_id)                  AS rank_pos,
        revenue / SUM(revenue) OVER ()                                         AS share,
        SUM(revenue) OVER (ORDER BY revenue DESC, product_id) / SUM(revenue) OVER () AS cum_share
    FROM product_revenue
)
SELECT
    rank_pos, product_id, name, category,
    ROUND(revenue, 2)         AS revenue,
    ROUND(profit, 2)          AS profit,
    ROUND(100 * share, 2)     AS share_pct,
    ROUND(100 * cum_share, 2) AS cum_share_pct,
    CASE
        WHEN cum_share - share < 0.80 THEN 'A'
        WHEN cum_share - share < 0.95 THEN 'B'
        ELSE 'C'
    END AS abc_class
FROM ranked
ORDER BY rank_pos;

-- name: rfm_base
-- 4) Base do RFM: uma linha por cliente com pedidos concluídos. O scoring é feito em pandas.
SELECT
    customer_id,
    MAX(order_date)              AS last_order_date,
    COUNT(*)                     AS frequency,
    ROUND(SUM(net_revenue), 2)   AS monetary
FROM vw_order_net_revenue
GROUP BY customer_id;

-- name: cohort_retention
-- 5) Coortes por mês do primeiro pedido concluído; month_index = meses desde a coorte.
WITH customer_months AS (
    SELECT customer_id, CAST(DATE_FORMAT(order_date, '%Y-%m-01') AS DATE) AS order_month
    FROM vw_order_net_revenue
    GROUP BY customer_id, CAST(DATE_FORMAT(order_date, '%Y-%m-01') AS DATE)
),
cohorts AS (
    SELECT customer_id, order_month,
           MIN(order_month) OVER (PARTITION BY customer_id) AS cohort_month
    FROM customer_months
)
SELECT
    cohort_month,
    TIMESTAMPDIFF(MONTH, cohort_month, order_month) AS month_index,
    COUNT(*)                                        AS active_customers
FROM cohorts
GROUP BY cohort_month, TIMESTAMPDIFF(MONTH, cohort_month, order_month)
ORDER BY cohort_month, month_index;

-- name: channel_performance
-- 6) Performance por canal de aquisição.
WITH acquired AS (
    SELECT acquisition_channel AS channel, COUNT(*) AS customers_acquired
    FROM customers
    GROUP BY acquisition_channel
),
buyer_totals AS (
    SELECT c.acquisition_channel AS channel, v.customer_id,
           COUNT(*) AS orders, SUM(v.net_revenue) AS revenue, SUM(v.profit) AS profit
    FROM vw_order_net_revenue v
    JOIN customers c ON c.id = v.customer_id
    GROUP BY c.acquisition_channel, v.customer_id
),
channel_totals AS (
    SELECT channel,
           COUNT(*)                          AS buyers,
           SUM(orders)                       AS orders,
           SUM(revenue)                      AS revenue,
           SUM(profit)                       AS profit,
           SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END) AS repeat_buyers
    FROM buyer_totals
    GROUP BY channel
),
cancellations AS (
    SELECT c.acquisition_channel AS channel, AVG(o.status = 'canceled') AS cancel_rate
    FROM orders o
    JOIN customers c ON c.id = o.customer_id
    GROUP BY c.acquisition_channel
)
SELECT
    a.channel,
    a.customers_acquired,
    t.buyers,
    ROUND(100 * t.buyers / a.customers_acquired, 2)          AS conversion_pct,
    t.orders,
    ROUND(t.revenue, 2)                                      AS revenue,
    ROUND(100 * t.profit / t.revenue, 2)                     AS margin_pct,
    ROUND(t.revenue / t.orders, 2)                           AS aov,
    ROUND(100 * t.repeat_buyers / t.buyers, 2)               AS repeat_rate_pct,
    ROUND(t.revenue / a.customers_acquired, 2)               AS revenue_per_customer,
    ROUND(100 * x.cancel_rate, 2)                            AS cancel_rate_pct
FROM acquired a
JOIN channel_totals t ON t.channel = a.channel
JOIN cancellations x  ON x.channel = a.channel
ORDER BY revenue_per_customer DESC;

-- name: coupon_impact
-- 7) Impacto por cupom no ticket (bruto e líquido) e na margem.
SELECT
    COALESCE(c.code, 'Sem cupom')                    AS coupon,
    COALESCE(c.discount_pct, 0)                      AS discount_pct,
    COUNT(*)                                         AS orders,
    ROUND(AVG(v.gross_revenue), 2)                   AS gross_ticket,
    ROUND(AVG(v.net_revenue), 2)                     AS net_ticket,
    ROUND(100 * SUM(v.profit) / SUM(v.net_revenue), 2) AS margin_pct,
    ROUND(SUM(v.discount), 2)                        AS discount_total
FROM vw_order_net_revenue v
JOIN orders o       ON o.id = v.order_id
LEFT JOIN coupons c ON c.id = o.coupon_id
GROUP BY COALESCE(c.code, 'Sem cupom'), COALESCE(c.discount_pct, 0)
ORDER BY orders DESC;

-- name: coupon_summary
-- 7b) Com cupom x sem cupom.
SELECT
    CASE WHEN o.coupon_id IS NULL THEN 'Sem cupom' ELSE 'Com cupom' END AS coupon_group,
    COUNT(*)                                          AS orders,
    ROUND(AVG(v.gross_revenue), 2)                    AS gross_ticket,
    ROUND(AVG(v.net_revenue), 2)                      AS net_ticket,
    ROUND(100 * SUM(v.profit) / SUM(v.net_revenue), 2) AS margin_pct
FROM vw_order_net_revenue v
JOIN orders o ON o.id = v.order_id
GROUP BY CASE WHEN o.coupon_id IS NULL THEN 'Sem cupom' ELSE 'Com cupom' END;

-- name: payment_status
-- 8) Cancelamento (sobre todos os pedidos) e devolução (sobre pedidos não cancelados) por pagamento.
SELECT
    payment_method,
    COUNT(*)                                                          AS orders,
    SUM(status = 'canceled')                                          AS canceled,
    SUM(status = 'returned')                                          AS returned,
    ROUND(100 * SUM(status = 'canceled') / COUNT(*), 2)               AS cancel_rate_pct,
    ROUND(100 * SUM(status = 'returned')
              / NULLIF(SUM(status <> 'canceled'), 0), 2)              AS return_rate_pct
FROM orders
GROUP BY payment_method
ORDER BY cancel_rate_pct DESC;

-- name: state_revenue
-- 9) Receita por estado, com participação (SUM OVER) e margem.
SELECT
    cu.state,
    COUNT(DISTINCT v.customer_id)                          AS buyers,
    COUNT(*)                                               AS orders,
    ROUND(SUM(v.net_revenue), 2)                           AS revenue,
    ROUND(100 * SUM(v.net_revenue) / SUM(SUM(v.net_revenue)) OVER (), 2) AS share_pct,
    ROUND(100 * SUM(v.profit) / SUM(v.net_revenue), 2)     AS margin_pct
FROM vw_order_net_revenue v
JOIN customers cu ON cu.id = v.customer_id
GROUP BY cu.state
ORDER BY revenue DESC;
