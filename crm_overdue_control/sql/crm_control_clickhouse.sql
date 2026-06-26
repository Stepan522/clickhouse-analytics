/*
Пример витрины для контроля заявок и просрочек в ClickHouse.

Идея: каждый день собирать открытые заявки, проверять SLA по следующему действию,
дедлайн закрытия, наличие ответственного и длительность зависания в статусе.
*/

WITH
    toDate('{report_date}') AS report_date,
    report_date + INTERVAL 1 DAY - INTERVAL 1 SECOND AS report_end,
    ['Закрыта', 'Отказ', 'Продажа'] AS closed_statuses
SELECT
    manager,
    countIf(status NOT IN closed_statuses) AS open_requests,
    countIf(
        status NOT IN closed_statuses
        AND next_action_due_at <= report_end
    ) AS overdue_actions,
    countIf(
        status NOT IN closed_statuses
        AND close_due_at <= report_end
    ) AS overdue_closings,
    countIf(
        status NOT IN closed_statuses
        AND (manager IS NULL OR manager = '')
    ) AS without_manager,
    countIf(
        status NOT IN closed_statuses
        AND status_updated_at < report_date - INTERVAL 3 DAY
    ) AS stale_requests,
    sumIf(
        amount,
        status NOT IN closed_statuses
        AND (
            next_action_due_at <= report_end
            OR close_due_at <= report_end
            OR status_updated_at < report_date - INTERVAL 3 DAY
        )
    ) AS amount_in_risk
FROM crm_requests
WHERE created_at <= report_end
GROUP BY manager
ORDER BY overdue_actions DESC, overdue_closings DESC, amount_in_risk DESC;


/* Детализация проблемных заявок */
WITH
    toDate('{report_date}') AS report_date,
    report_date + INTERVAL 1 DAY - INTERVAL 1 SECOND AS report_end,
    ['Закрыта', 'Отказ', 'Продажа'] AS closed_statuses
SELECT
    request_id,
    client,
    source,
    if(manager = '', 'Не назначен', manager) AS manager,
    status,
    priority,
    amount,
    next_action_due_at,
    close_due_at,
    dateDiff('day', toDate(status_updated_at), report_date) AS days_without_update,
    multiIf(
        next_action_due_at <= report_end AND priority = 'Высокий', 'Критично: просрочено действие по горячей заявке',
        next_action_due_at <= report_end, 'Просрочено следующее действие',
        close_due_at <= report_end, 'Просрочен дедлайн закрытия',
        manager = '', 'Нет ответственного',
        status_updated_at < report_date - INTERVAL 3 DAY, 'Заявка зависла в статусе',
        'Проверить'
    ) AS problem
FROM crm_requests
WHERE
    status NOT IN closed_statuses
    AND (
        next_action_due_at <= report_end
        OR close_due_at <= report_end
        OR manager = ''
        OR status_updated_at < report_date - INTERVAL 3 DAY
    )
ORDER BY
    priority = 'Высокий' DESC,
    amount DESC,
    next_action_due_at ASC;
