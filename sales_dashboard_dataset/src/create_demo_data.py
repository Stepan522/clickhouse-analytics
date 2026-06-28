"""Создание демо-данных продаж для витрины дашборда.

Скрипт генерирует небольшие CSV-таблицы, которые имитируют типичный набор
источников: заказы, товары, клиенты и строки заказов. Данные синтетические,
их можно безопасно размещать в портфолио.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


RANDOM_SEED = 522


CITIES = [
    "Москва",
    "Санкт-Петербург",
    "Казань",
    "Екатеринбург",
    "Новосибирск",
    "Краснодар",
    "Нижний Новгород",
    "Самара",
]

CHANNELS = [
    "CRM",
    "Яндекс Директ",
    "SEO",
    "Telegram",
    "Рекомендации",
    "Email",
]

PAYMENT_METHODS = ["card", "invoice", "sbp", "cashless"]
ORDER_STATUSES = ["paid", "paid", "paid", "paid", "cancelled", "refunded"]

PRODUCTS = [
    ("P001", "Монтаж оборудования", "Монтаж", 32000, 18500),
    ("P002", "Настройка интеграции", "Интеграции", 24000, 12200),
    ("P003", "Подписка Базовая", "Подписки", 9900, 3400),
    ("P004", "Подписка Профи", "Подписки", 17900, 6200),
    ("P005", "Сервисное обслуживание", "Сервис", 14900, 7600),
    ("P006", "Консультация аналитика", "Консалтинг", 12000, 5800),
    ("P007", "Разработка отчета", "Аналитика", 26000, 12600),
    ("P008", "Аудит данных", "Аналитика", 22000, 9200),
    ("P009", "Дополнительные услуги", "Доп. услуги", 8500, 4100),
    ("P010", "Обучение команды", "Обучение", 18000, 7300),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Сгенерировать демо-CSV для датасета продаж")
    parser.add_argument("--output-dir", default="data/raw", help="Папка для сырых CSV")
    parser.add_argument("--customers", type=int, default=180, help="Количество клиентов")
    parser.add_argument("--orders", type=int, default=620, help="Количество заказов")
    return parser.parse_args()


def make_customers(rng: np.random.Generator, n_customers: int) -> pd.DataFrame:
    signup_dates = pd.date_range("2025-10-01", "2026-06-25", freq="D")
    customers = pd.DataFrame(
        {
            "customer_id": [f"C{idx:04d}" for idx in range(1, n_customers + 1)],
            "customer_name": [f"Клиент {idx:04d}" for idx in range(1, n_customers + 1)],
            "city": rng.choice(CITIES, size=n_customers),
            "customer_type": rng.choice(["B2B", "B2C"], size=n_customers, p=[0.68, 0.32]),
            "signup_date": rng.choice(signup_dates, size=n_customers),
            "acquisition_channel": rng.choice(CHANNELS, size=n_customers, p=[0.22, 0.25, 0.18, 0.1, 0.15, 0.1]),
        }
    )
    return customers.sort_values("customer_id")


def make_products() -> pd.DataFrame:
    return pd.DataFrame(
        PRODUCTS,
        columns=["product_id", "product_name", "category", "base_price", "unit_cost"],
    )


def make_orders(
    rng: np.random.Generator,
    customers: pd.DataFrame,
    n_orders: int,
) -> pd.DataFrame:
    order_dates = pd.date_range("2026-01-01", "2026-06-25", freq="D")

    # Повторные покупки встречаются чаще у части клиентов.
    customer_pool = customers["customer_id"].to_numpy()
    weights = rng.power(2.8, size=len(customer_pool))
    weights = weights / weights.sum()

    orders = pd.DataFrame(
        {
            "order_id": [f"O{idx:06d}" for idx in range(1, n_orders + 1)],
            "customer_id": rng.choice(customer_pool, size=n_orders, p=weights),
            "order_date": rng.choice(order_dates, size=n_orders),
            "sales_channel": rng.choice(CHANNELS, size=n_orders, p=[0.28, 0.26, 0.17, 0.09, 0.12, 0.08]),
            "payment_method": rng.choice(PAYMENT_METHODS, size=n_orders, p=[0.42, 0.36, 0.17, 0.05]),
            "order_status": rng.choice(ORDER_STATUSES, size=n_orders, p=[0.44, 0.18, 0.16, 0.1, 0.08, 0.04]),
            "manager": rng.choice(["Иван Петров", "Анна Кузнецова", "Мария Орлова", "Дмитрий Соколов"], size=n_orders),
        }
    )
    return orders.sort_values(["order_date", "order_id"])


def make_order_items(
    rng: np.random.Generator,
    orders: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    product_ids = products["product_id"].to_numpy()
    product_weights = np.array([0.16, 0.12, 0.14, 0.12, 0.12, 0.1, 0.08, 0.06, 0.07, 0.03])
    product_weights = product_weights / product_weights.sum()
    price_map = products.set_index("product_id")["base_price"].to_dict()

    for order_id in orders["order_id"]:
        item_count = int(rng.choice([1, 1, 1, 2, 2, 3], p=[0.34, 0.22, 0.13, 0.18, 0.08, 0.05]))
        chosen_products = rng.choice(product_ids, size=item_count, replace=False, p=product_weights)
        for product_id in chosen_products:
            base_price = price_map[product_id]
            unit_price = int(base_price * rng.normal(1.0, 0.08) // 100 * 100)
            rows.append(
                {
                    "order_id": order_id,
                    "product_id": product_id,
                    "quantity": int(rng.choice([1, 1, 1, 2, 3], p=[0.5, 0.22, 0.12, 0.11, 0.05])),
                    "unit_price": max(unit_price, 1000),
                    "discount_pct": float(rng.choice([0, 0, 0, 0.05, 0.1, 0.15], p=[0.48, 0.16, 0.12, 0.1, 0.09, 0.05])),
                }
            )

    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(RANDOM_SEED)

    customers = make_customers(rng, args.customers)
    products = make_products()
    orders = make_orders(rng, customers, args.orders)
    order_items = make_order_items(rng, orders, products)

    customers.to_csv(output_dir / "customers.csv", index=False)
    products.to_csv(output_dir / "products.csv", index=False)
    orders.to_csv(output_dir / "orders.csv", index=False)
    order_items.to_csv(output_dir / "order_items.csv", index=False)

    print(f"Готово. CSV сохранены в {output_dir.resolve()}")


if __name__ == "__main__":
    main()
