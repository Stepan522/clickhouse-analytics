-- Пример витрины ClickHouse для остатков маркетплейсов.

CREATE TABLE marketplace_stock_report
(
    loaded_at DateTime DEFAULT now(),
    marketplace LowCardinality(String),
    sku String,
    product_name String,
    category LowCardinality(String),
    warehouse LowCardinality(String),
    stock Int64,
    reserved Int64,
    available_stock Int64,
    price Float64,
    commission_rate Float64,
    commission_amount Float64,
    net_price Float64,
    cost_price Float64,
    gross_margin_per_unit Float64,
    gross_margin_rate Float64,
    orders_3d UInt64,
    revenue_3d Float64,
    daily_sales_avg Float64,
    days_of_stock Float64,
    status LowCardinality(String),
    alert LowCardinality(String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(loaded_at)
ORDER BY (marketplace, sku, warehouse);

SELECT
    marketplace,
    countDistinct(sku) AS sku_count,
    sum(available_stock) AS available_stock,
    sum(revenue_3d) AS revenue_3d,
    countIf(alert != 'ok') AS alerts_count
FROM marketplace_stock_report
GROUP BY marketplace
ORDER BY revenue_3d DESC;
