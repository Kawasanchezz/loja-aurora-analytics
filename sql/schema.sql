-- Loja Aurora (fictícia): esquema normalizado (3FN) para MySQL 8.
-- Idempotente: remove e recria os objetos. Dados são apagados a cada init-db.

DROP VIEW  IF EXISTS vw_order_net_revenue;
DROP VIEW  IF EXISTS vw_item_net_revenue;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS coupons;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;

CREATE TABLE categories (
    id   TINYINT UNSIGNED NOT NULL,
    name VARCHAR(60)      NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_categories_name (name)
) ENGINE=InnoDB;

CREATE TABLE products (
    id          SMALLINT UNSIGNED NOT NULL,
    category_id TINYINT UNSIGNED  NOT NULL,
    name        VARCHAR(100)      NOT NULL,
    price       DECIMAL(10,2)     NOT NULL,
    cost        DECIMAL(10,2)     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_products_name (name),
    KEY ix_products_category (category_id),
    CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories (id),
    CONSTRAINT ck_products_price CHECK (price > 0),
    CONSTRAINT ck_products_cost CHECK (cost >= 0 AND cost < price)
) ENGINE=InnoDB;

CREATE TABLE coupons (
    id           TINYINT UNSIGNED NOT NULL,
    code         VARCHAR(20)      NOT NULL,
    discount_pct DECIMAL(5,2)     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_coupons_code (code),
    CONSTRAINT ck_coupons_discount CHECK (discount_pct > 0 AND discount_pct <= 100)
) ENGINE=InnoDB;

CREATE TABLE customers (
    id                  INT UNSIGNED NOT NULL,
    name                VARCHAR(120) NOT NULL,
    email               VARCHAR(120) NOT NULL,
    state               CHAR(2)      NOT NULL,
    acquisition_channel ENUM('organic', 'paid_search', 'social', 'email', 'referral') NOT NULL,
    created_at          DATETIME     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_customers_email (email),
    KEY ix_customers_channel (acquisition_channel),
    KEY ix_customers_state (state)
) ENGINE=InnoDB;

CREATE TABLE orders (
    id             INT UNSIGNED     NOT NULL,
    customer_id    INT UNSIGNED     NOT NULL,
    coupon_id      TINYINT UNSIGNED NULL,
    order_date     DATETIME         NOT NULL,
    status         ENUM('completed', 'canceled', 'returned')       NOT NULL,
    payment_method ENUM('credit_card', 'pix', 'boleto')            NOT NULL,
    PRIMARY KEY (id),
    KEY ix_orders_customer_date (customer_id, order_date),
    KEY ix_orders_date (order_date),
    KEY ix_orders_payment_status (payment_method, status),
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers (id),
    CONSTRAINT fk_orders_coupon FOREIGN KEY (coupon_id) REFERENCES coupons (id)
) ENGINE=InnoDB;

-- unit_price e unit_cost são o preço e o custo praticados na data da venda (fato histórico).
CREATE TABLE order_items (
    id         INT UNSIGNED      NOT NULL,
    order_id   INT UNSIGNED      NOT NULL,
    product_id SMALLINT UNSIGNED NOT NULL,
    quantity   TINYINT UNSIGNED  NOT NULL,
    unit_price DECIMAL(10,2)     NOT NULL,
    unit_cost  DECIMAL(10,2)     NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_order_product (order_id, product_id),
    KEY ix_items_product (product_id),
    CONSTRAINT fk_items_order FOREIGN KEY (order_id) REFERENCES orders (id),
    CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products (id),
    CONSTRAINT ck_items_quantity CHECK (quantity > 0),
    CONSTRAINT ck_items_prices CHECK (unit_price > 0 AND unit_cost >= 0)
) ENGINE=InnoDB;

-- Receita líquida por item: só pedidos concluídos (exclui cancelados e devolvidos).
-- O desconto do cupom incide sobre o valor bruto do item.
CREATE VIEW vw_item_net_revenue AS
SELECT
    oi.id                                                   AS order_item_id,
    o.id                                                    AS order_id,
    o.customer_id,
    o.order_date,
    oi.product_id,
    oi.quantity,
    oi.quantity * oi.unit_price                             AS gross_revenue,
    ROUND(oi.quantity * oi.unit_price * COALESCE(c.discount_pct, 0) / 100, 2) AS discount,
    oi.quantity * oi.unit_price
        - ROUND(oi.quantity * oi.unit_price * COALESCE(c.discount_pct, 0) / 100, 2) AS net_revenue,
    oi.quantity * oi.unit_cost                              AS cogs
FROM order_items oi
JOIN orders o        ON o.id = oi.order_id
LEFT JOIN coupons c  ON c.id = o.coupon_id
WHERE o.status = 'completed';

-- Receita líquida por pedido, construída sobre a view de itens (evita duplicar a regra).
CREATE VIEW vw_order_net_revenue AS
SELECT
    i.order_id,
    i.customer_id,
    i.order_date,
    SUM(i.gross_revenue)              AS gross_revenue,
    SUM(i.discount)                   AS discount,
    SUM(i.net_revenue)                AS net_revenue,
    SUM(i.cogs)                       AS cogs,
    SUM(i.net_revenue - i.cogs)       AS profit
FROM vw_item_net_revenue i
GROUP BY i.order_id, i.customer_id, i.order_date;
