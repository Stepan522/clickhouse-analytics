-- Пример таблицы ClickHouse для внутренних уведомлений.

CREATE TABLE internal_notifications
(
    event_id String,
    created_at DateTime,
    event_type LowCardinality(String),
    title String,
    entity_id String,
    priority LowCardinality(String),
    responsible LowCardinality(String),
    status LowCardinality(String),
    channel LowCardinality(String),
    message String
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (created_at, status, priority, event_type);

-- Сводка для контроля уведомлений:
SELECT
    toDate(created_at) AS date,
    event_type,
    priority,
    status,
    count() AS events
FROM internal_notifications
GROUP BY date, event_type, priority, status
ORDER BY date DESC, events DESC;
