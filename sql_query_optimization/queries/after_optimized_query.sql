-- AFTER: оптимизированная версия.
-- 1. Фильтр по DateTime без функции от created_at.
-- 2. Сначала отбираем заказы за период.
-- 3. Сначала считаем метрики на уровне order_id.
-- 4. Подключаем только нужные справочники.
-- 5. Логика разбита на читаемые CTE.

WITH
    toDateTime('2026-06-01 00:00:00') AS date_from,
    toDateTime('2026-07-01 00:00:00') AS date_to,

filtered_orders AS
(
    SELECT
        order_id,
        customer_id,
        created_at,
        channel,
        city,
        manager_id
    FROM orders
    WHERE created_at >= date_from
      AND created_at < date_to
      AND status IN ('paid', 'shipped')
),

order_metrics AS
(
    SELECT
        order_id,
        sum(quantity * price - discount) AS order_revenue,
        sum(quantity) AS items_count
    FROM order_items
    WHERE order_id IN (SELECT order_id FROM filtered_orders)
    GROUP BY order_id
),

final AS
(
    SELECT
        toDate(fo.created_at) AS order_date,
        fo.channel,
        fo.city,
        m.department,
        fo.order_id,
        fo.customer_id,
        om.order_revenue,
        om.items_count
    FROM filtered_orders fo
    INNER JOIN order_metrics om ON fo.order_id = om.order_id
    LEFT JOIN managers m ON fo.manager_id = m.manager_id
)

SELECT
    order_date,
    channel,
    city,
    department,
    count() AS orders,
    sum(order_revenue) AS revenue,
    round(avg(order_revenue), 2) AS avg_order_revenue,
    uniqExact(customer_id) AS customers
FROM final
GROUP BY
    order_date,
    channel,
    city,
    department
ORDER BY order_date, revenue DESC;
