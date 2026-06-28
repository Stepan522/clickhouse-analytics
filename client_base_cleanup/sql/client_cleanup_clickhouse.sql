-- Пример SQL-логики для ClickHouse:
-- нормализация телефонов/email и поиск дублей в клиентской базе.

WITH prepared AS (
    SELECT
        client_id,
        lowerUTF8(trim(email)) AS email_clean,
        replaceRegexpAll(phone, '[^0-9]', '') AS phone_digits,
        trim(full_name) AS full_name_clean,
        city,
        source,
        total_orders,
        revenue_rub
    FROM raw_clients
),
normalized AS (
    SELECT
        *,
        multiIf(
            length(phone_digits) = 11 AND startsWith(phone_digits, '8'), concat('+7', substring(phone_digits, 2)),
            length(phone_digits) = 11 AND startsWith(phone_digits, '7'), concat('+', phone_digits),
            length(phone_digits) = 10, concat('+7', phone_digits),
            ''
        ) AS phone_clean
    FROM prepared
),
duplicate_keys AS (
    SELECT
        *,
        multiIf(
            phone_clean != '', concat('phone:', phone_clean),
            email_clean != '', concat('email:', email_clean),
            concat('name_city:', hex(MD5(concat(full_name_clean, '|', city))))
        ) AS duplicate_key
    FROM normalized
)
SELECT
    duplicate_key,
    count() AS records_in_group,
    groupArray(client_id) AS client_ids,
    any(phone_clean) AS phone,
    any(email_clean) AS email,
    max(revenue_rub) AS max_revenue
FROM duplicate_keys
GROUP BY duplicate_key
HAVING records_in_group > 1
ORDER BY records_in_group DESC;
