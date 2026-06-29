-- Пример схемы ClickHouse для отчета по продажам.

CREATE TABLE orders
(
    order_id UInt64,
    customer_id UInt64,
    created_at DateTime,
    status LowCardinality(String),
    channel LowCardinality(String),
    city LowCardinality(String),
    manager_id UInt64
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (created_at, status, order_id);

CREATE TABLE order_items
(
    order_id UInt64,
    product_id UInt64,
    quantity UInt32,
    price Float64,
    discount Float64
)
ENGINE = MergeTree
ORDER BY (order_id, product_id);

CREATE TABLE products
(
    product_id UInt64,
    category LowCardinality(String),
    product_name String
)
ENGINE = MergeTree
ORDER BY product_id;

CREATE TABLE managers
(
    manager_id UInt64,
    manager_name String,
    department LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY manager_id;
