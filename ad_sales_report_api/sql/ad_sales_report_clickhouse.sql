-- Пример витрины ClickHouse для объединенного отчета рекламы и продаж.

CREATE TABLE ad_sales_report
(
    date Date,
    channel LowCardinality(String),
    campaign String,
    impressions UInt64,
    clicks UInt64,
    cost Float64,
    leads UInt64,
    sales UInt64,
    revenue Float64,
    gross_profit Float64,
    ctr Float64,
    cpl Float64,
    cpo Float64,
    cr_lead_to_sale Float64,
    romi Float64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(date)
ORDER BY (date, channel, campaign);

SELECT
    channel,
    sum(cost) AS cost,
    sum(leads) AS leads,
    sum(sales) AS sales,
    sum(revenue) AS revenue,
    round(sum(cost) / nullIf(sum(leads), 0), 2) AS cpl,
    round((sum(gross_profit) - sum(cost)) / nullIf(sum(cost), 0), 3) AS romi
FROM ad_sales_report
GROUP BY channel
ORDER BY cost DESC;
