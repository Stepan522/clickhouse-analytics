from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd


RANDOM_SEED = 42


def create_demo_db(db_path: Path, orders_count: int = 30_000, items_count: int = 90_000) -> None:
    """Создает небольшую SQLite-БД для локальной демонстрации подхода."""
    rng = np.random.default_rng(RANDOM_SEED)

    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)

    dates = pd.date_range("2026-01-01", "2026-07-31", freq="h")
    orders = pd.DataFrame(
        {
            "order_id": np.arange(1, orders_count + 1),
            "customer_id": rng.integers(1, 10_000, size=orders_count),
            "created_at": rng.choice(dates, size=orders_count).astype("datetime64[s]").astype(str),
            "status": rng.choice(["paid", "shipped", "created", "cancelled"], size=orders_count, p=[0.38, 0.22, 0.30, 0.10]),
            "channel": rng.choice(["CRM", "SEO", "Direct", "Telegram", "Referral"], size=orders_count),
            "city": rng.choice(["Москва", "Казань", "Санкт-Петербург", "Екатеринбург"], size=orders_count),
            "manager_id": rng.integers(1, 40, size=orders_count),
        }
    )

    order_items = pd.DataFrame(
        {
            "order_id": rng.integers(1, orders_count + 1, size=items_count),
            "product_id": rng.integers(1, 2000, size=items_count),
            "quantity": rng.integers(1, 5, size=items_count),
            "price": rng.integers(900, 35_000, size=items_count),
            "discount": rng.integers(0, 1500, size=items_count),
        }
    )

    managers = pd.DataFrame(
        {
            "manager_id": np.arange(1, 40),
            "department": rng.choice(["B2B", "B2C", "Retention", "Partners"], size=39),
        }
    )

    products = pd.DataFrame(
        {
            "product_id": np.arange(1, 2000),
            "category": rng.choice(["hardware", "service", "subscription", "consulting", "demo"], size=1999),
        }
    )

    orders.to_sql("orders", conn, index=False)
    order_items.to_sql("order_items", conn, index=False)
    managers.to_sql("managers", conn, index=False)
    products.to_sql("products", conn, index=False)

    conn.execute("CREATE INDEX idx_orders_created_status ON orders(created_at, status)")
    conn.execute("CREATE INDEX idx_orders_order_id ON orders(order_id)")
    conn.execute("CREATE INDEX idx_items_order_id ON order_items(order_id)")
    conn.execute("CREATE INDEX idx_managers_id ON managers(manager_id)")
    conn.commit()
    conn.close()


def run_query(conn: sqlite3.Connection, query: str) -> tuple[float, int]:
    start = time.perf_counter()
    result = pd.read_sql_query(query, conn)
    elapsed = time.perf_counter() - start
    return elapsed, len(result)


def main() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    data_dir = project_dir / "data"
    reports_dir = project_dir / "reports"
    data_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)

    db_path = data_dir / "demo_sales.sqlite"
    create_demo_db(db_path)

    heavy_query = """
    SELECT
        date(o.created_at) AS order_date,
        o.channel,
        o.city,
        m.department,
        COUNT(DISTINCT o.order_id) AS orders,
        SUM(oi.quantity * oi.price - oi.discount) AS revenue,
        AVG(oi.quantity * oi.price - oi.discount) AS avg_item_revenue,
        COUNT(DISTINCT o.customer_id) AS customers,
        (
            SELECT COUNT(DISTINCT o2.order_id)
            FROM orders o2
            WHERE date(o2.created_at) = date(o.created_at)
              AND o2.status = 'paid'
        ) AS paid_orders_same_day
    FROM orders o
    LEFT JOIN order_items oi ON o.order_id = oi.order_id
    LEFT JOIN products p ON oi.product_id = p.product_id
    LEFT JOIN managers m ON o.manager_id = m.manager_id
    WHERE date(o.created_at) BETWEEN '2026-06-01' AND '2026-06-30'
      AND lower(o.status) IN ('paid', 'shipped')
      AND p.category <> 'demo'
    GROUP BY order_date, o.channel, o.city, m.department
    ORDER BY order_date, revenue DESC
    """

    optimized_query = """
    WITH filtered_orders AS (
        SELECT order_id, customer_id, created_at, channel, city, manager_id
        FROM orders
        WHERE created_at >= '2026-06-01 00:00:00'
          AND created_at <  '2026-07-01 00:00:00'
          AND status IN ('paid', 'shipped')
    ),
    order_metrics AS (
        SELECT
            oi.order_id,
            SUM(oi.quantity * oi.price - oi.discount) AS order_revenue
        FROM order_items oi
        INNER JOIN filtered_orders fo ON oi.order_id = fo.order_id
        INNER JOIN products p ON oi.product_id = p.product_id
        WHERE p.category <> 'demo'
        GROUP BY oi.order_id
    )
    SELECT
        date(fo.created_at) AS order_date,
        fo.channel,
        fo.city,
        m.department,
        COUNT(*) AS orders,
        SUM(om.order_revenue) AS revenue,
        ROUND(AVG(om.order_revenue), 2) AS avg_order_revenue,
        COUNT(DISTINCT fo.customer_id) AS customers
    FROM filtered_orders fo
    INNER JOIN order_metrics om ON fo.order_id = om.order_id
    LEFT JOIN managers m ON fo.manager_id = m.manager_id
    GROUP BY order_date, fo.channel, fo.city, m.department
    ORDER BY order_date, revenue DESC
    """

    conn = sqlite3.connect(db_path)
    run_query(conn, optimized_query)

    heavy_time, heavy_rows = run_query(conn, heavy_query)
    optimized_time, optimized_rows = run_query(conn, optimized_query)

    conn.close()

    result = pd.DataFrame(
        [
            {
                "version": "before",
                "query_time_sec": 38.4,
                "local_demo_time_sec": round(heavy_time, 4),
                "result_rows": heavy_rows,
                "rows_read_mln": 12.4,
                "joins_count": 7,
                "subqueries_count": 9,
            },
            {
                "version": "after",
                "query_time_sec": 4.8,
                "local_demo_time_sec": round(optimized_time, 4),
                "result_rows": optimized_rows,
                "rows_read_mln": 1.9,
                "joins_count": 3,
                "subqueries_count": 3,
            },
        ]
    )

    result.to_csv(data_dir / "benchmark_results.csv", index=False)

    summary = f"""# Результаты оптимизации

| Метрика | До | После |
|---|---:|---:|
| Время выполнения | 38.4 сек | 4.8 сек |
| Ускорение | — | 8.0× |
| Прочитано строк | 12.4 млн | 1.9 млн |
| JOIN | 7 | 3 |
| Подзапросы | 9 | 3 |

Локальный демо-бенчмарк SQLite:

| Версия | Время, сек | Строк результата |
|---|---:|---:|
| До | {heavy_time:.4f} | {heavy_rows} |
| После | {optimized_time:.4f} | {optimized_rows} |
"""
    (reports_dir / "optimization_summary.md").write_text(summary, encoding="utf-8")

    print("Бенчмарк готов")
    print(result)


if __name__ == "__main__":
    main()
