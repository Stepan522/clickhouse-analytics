/*
    Пример SQL-витрины для ежедневного отчета по рекламе.
    В реальном проекте этот запрос можно запускать в ClickHouse,
    а результат отдавать в Python-скрипт вместо CSV.
*/

WITH
    toDate('{report_date}') AS report_date
SELECT
    stat_date AS report_date,
    traffic_source AS source,
    campaign_name AS campaign,
    sum(impressions) AS impressions,
    sum(clicks) AS clicks,
    sum(cost) AS cost,
    countIf(event_name = 'lead') AS leads,
    countIf(event_name = 'purchase') AS orders,
    sumIf(revenue, event_name = 'purchase') AS revenue,
    round(clicks / nullIf(impressions, 0) * 100, 2) AS ctr,
    round(cost / nullIf(clicks, 0), 2) AS cpc,
    round(cost / nullIf(leads, 0), 2) AS cpl,
    round(cost / nullIf(orders, 0), 2) AS cpa,
    round(revenue / nullIf(cost, 0), 2) AS roas
FROM marketing.ads_events
WHERE stat_date BETWEEN report_date - 1 AND report_date
GROUP BY
    stat_date,
    traffic_source,
    campaign_name
ORDER BY
    stat_date,
    cost DESC;
