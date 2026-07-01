-- Пример таблицы ClickHouse для заявок с сайта.

CREATE TABLE site_leads
(
    lead_id String,
    created_at DateTime,
    name String,
    phone String,
    email String,
    service LowCardinality(String),
    comment String,
    utm_source LowCardinality(String),
    utm_medium LowCardinality(String),
    utm_campaign String,
    page_url String,
    status LowCardinality(String),
    crm_status LowCardinality(String),
    telegram_status LowCardinality(String),
    sheets_status LowCardinality(String)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (created_at, service, utm_source, lead_id);

SELECT
    toDate(created_at) AS date,
    service,
    utm_source,
    count() AS leads,
    countIf(crm_status = 'sent') AS sent_to_crm
FROM site_leads
GROUP BY date, service, utm_source
ORDER BY date DESC, leads DESC;
