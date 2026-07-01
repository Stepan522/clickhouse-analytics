-- Пример таблицы ClickHouse для обращений в поддержку.

CREATE TABLE support_tickets
(
    ticket_id String,
    created_at DateTime,
    client_name String,
    channel LowCardinality(String),
    question String,
    detected_intent LowCardinality(String),
    status LowCardinality(String),
    need_operator UInt8
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (created_at, status, detected_intent, ticket_id);

-- Сводка для дашборда поддержки:
SELECT
    toDate(created_at) AS date,
    detected_intent,
    status,
    count() AS tickets,
    round(avg(need_operator) * 100, 1) AS operator_share
FROM support_tickets
GROUP BY date, detected_intent, status
ORDER BY date DESC, tickets DESC;
