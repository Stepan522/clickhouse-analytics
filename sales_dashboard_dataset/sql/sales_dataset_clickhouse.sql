/*
Витрина продаж для BI-дашборда на ClickHouse.

Идея: собрать одну плоскую таблицу, которую можно подключить в DataLens,
Power BI или другую BI-систему без ручных VLOOKUP и дополнительных Excel-файлов.
*/

CREATE OR REPLACE VIEW analytics.dashboard_sales_dataset AS
SELECT
    toDate(o.order_date) AS order_date,
    toYYYYMM(o.order_date) AS order_month,
    concat(toString(toISOYear(o.order_date)), '-W', lpad(toString(toISOWeek(o.order_date)), 2, '0')) AS order_week,
    o.order_id,
    o.customer_id,
    c.customer_name,
    c.city,
    c.customer_type,
    o.sales_channel,
    o.payment_method,
    o.order_status,
    o.manager,
    oi.product_id,
    p.product_name,
    p.category,
    oi.quantity,
    oi.unit_price,
    oi.discount_pct,
    oi.quantity * oi.unit_price AS gross_revenue,
    round(oi.quantity * oi.unit_price * oi.discount_pct, 2) AS discount_amount,
    round(oi.quantity * oi.unit_price * (1 - oi.discount_pct), 2) AS net_revenue,
    oi.quantity * p.unit_cost AS cost,
    round(net_revenue - cost, 2) AS margin,
    round(margin / nullIf(net_revenue, 0), 4) AS margin_pct,
    if(o.order_status IN ('paid', 'refunded'), 1, 0) AS is_paid,
    if(o.order_status = 'cancelled', 1, 0) AS is_cancelled,
    row_number() OVER (PARTITION BY o.customer_id ORDER BY o.order_date, o.order_id) AS order_sequence,
    if(order_sequence > 1, 1, 0) AS is_repeat_purchase
FROM raw.order_items AS oi
LEFT JOIN raw.orders AS o ON oi.order_id = o.order_id
LEFT JOIN raw.products AS p ON oi.product_id = p.product_id
LEFT JOIN raw.customers AS c ON o.customer_id = c.customer_id;

-- Ежедневные KPI для верхнего блока дашборда.
SELECT
    order_date,
    sumIf(net_revenue, is_paid = 1) AS revenue,
    uniqExactIf(order_id, is_paid = 1) AS orders,
    uniqExactIf(customer_id, is_paid = 1) AS customers,
    revenue / nullIf(orders, 0) AS avg_check,
    sumIf(margin, is_paid = 1) / nullIf(revenue, 0) AS margin_pct,
    sumIf(is_repeat_purchase, is_paid = 1) / nullIf(orders, 0) AS repeat_order_share
FROM analytics.dashboard_sales_dataset
GROUP BY order_date
ORDER BY order_date;
