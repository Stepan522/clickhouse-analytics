/*
Пример SQL-запроса для ClickHouse.
В реальном проекте этот запрос можно использовать как источник данных для Python-скрипта.
*/

WITH
    toDate({report_date:String}) AS report_date,
    report_date - 1 AS previous_date

SELECT
    order_date,
    channel,
    category,
    countDistinctIf(order_id, status IN ('paid', 'completed', 'done', 'success')) AS orders,
    sumIf(revenue, status IN ('paid', 'completed', 'done', 'success')) AS revenue,
    round(revenue / nullIf(orders, 0), 2) AS avg_check,
    countDistinctIf(order_id, status IN ('canceled', 'cancelled', 'cancel')) AS canceled_orders,
    uniqExactIf(customer_id, is_new_client = 1 AND status IN ('paid', 'completed', 'done', 'success')) AS new_clients
FROM mart.sales_orders
WHERE order_date IN (report_date, previous_date)
GROUP BY
    order_date,
    channel,
    category
ORDER BY
    order_date,
    revenue DESC;
