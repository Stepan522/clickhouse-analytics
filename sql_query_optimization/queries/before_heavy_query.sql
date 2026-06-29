-- BEFORE: пример тяжелого запроса.
-- Проблемы:
-- 1. Функция toDate(created_at) в WHERE.
-- 2. Лишние JOIN до фильтрации периода.
-- 3. Повторные подзапросы.
-- 4. Агрегация идет после расширения строк через JOIN.

SELECT
    toDate(o.created_at) AS order_date,
    o.channel,
    o.city,
    m.department,
    count(DISTINCT o.order_id) AS orders,
    sum(oi.quantity * oi.price - oi.discount) AS revenue,
    avg(oi.quantity * oi.price - oi.discount) AS avg_item_revenue,
    count(DISTINCT o.customer_id) AS customers,
    (
        SELECT count(DISTINCT o2.order_id)
        FROM orders o2
        WHERE toDate(o2.created_at) = toDate(o.created_at)
          AND o2.status = 'paid'
    ) AS paid_orders_same_day
FROM orders o
LEFT JOIN order_items oi ON o.order_id = oi.order_id
LEFT JOIN products p ON oi.product_id = p.product_id
LEFT JOIN managers m ON o.manager_id = m.manager_id
LEFT JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN traffic_sources ts ON o.channel = ts.channel
LEFT JOIN cities city_dict ON o.city = city_dict.city
WHERE toDate(o.created_at) BETWEEN '2026-06-01' AND '2026-06-30'
  AND lower(o.status) IN ('paid', 'shipped')
  AND p.category NOT IN ('test', 'demo')
GROUP BY
    order_date,
    o.channel,
    o.city,
    m.department
ORDER BY order_date, revenue DESC;
