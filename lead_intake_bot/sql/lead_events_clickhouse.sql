-- Пример таблицы ClickHouse для хранения заявок из бота.

CREATE TABLE bot_leads
(
    lead_id String,
    created_at DateTime,
    name String,
    phone String,
    email String,
    service LowCardinality(String),
    budget LowCardinality(String),
    comment String,
    status LowCardinality(String),
    manager LowCardinality(String),
    source LowCardinality(String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (created_at, status, service, lead_id);

SELECT
    toDate(created_at) AS date,
    service,
    status,
    count() AS leads,
    uniqExact(phone) AS unique_contacts
FROM bot_leads
GROUP BY date, service, status
ORDER BY date DESC, leads DESC;
