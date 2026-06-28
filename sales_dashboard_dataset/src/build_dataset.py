"""Сборка витрины продаж для дашборда.

На входе несколько сырых таблиц: заказы, строки заказов, клиенты и товары.
На выходе — готовые CSV для BI: детальный датасет, ежедневные KPI,
метрики по категориям и словарь полей.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PAID_STATUSES = {"paid", "refunded"}
CANCELLED_STATUSES = {"cancelled"}


DATA_DICTIONARY = [
    ("order_date", "Дата заказа", "date"),
    ("order_month", "Месяц заказа для группировки в BI", "string"),
    ("order_week", "ISO-неделя заказа", "string"),
    ("order_id", "Идентификатор заказа", "string"),
    ("customer_id", "Идентификатор клиента", "string"),
    ("customer_name", "Название/имя клиента", "string"),
    ("city", "Город клиента", "string"),
    ("customer_type", "Тип клиента: B2B или B2C", "string"),
    ("sales_channel", "Канал продажи", "string"),
    ("payment_method", "Способ оплаты", "string"),
    ("order_status", "Статус заказа", "string"),
    ("product_id", "Идентификатор товара/услуги", "string"),
    ("product_name", "Товар или услуга", "string"),
    ("category", "Категория товара/услуги", "string"),
    ("quantity", "Количество в строке заказа", "integer"),
    ("gross_revenue", "Выручка до скидки", "number"),
    ("discount_amount", "Сумма скидки", "number"),
    ("net_revenue", "Выручка после скидки", "number"),
    ("cost", "Себестоимость", "number"),
    ("margin", "Маржа", "number"),
    ("margin_pct", "Маржинальность", "number"),
    ("is_paid", "Флаг оплаченного/учитываемого заказа", "integer"),
    ("order_sequence", "Порядковый номер покупки клиента", "integer"),
    ("is_repeat_purchase", "Флаг повторной покупки", "integer"),
    ("order_total", "Сумма заказа после скидки", "number"),
    ("avg_check", "Средний чек заказа", "number"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Собрать датасет продаж для дашборда")
    parser.add_argument("--raw-dir", default="data/raw", help="Папка с исходными CSV")
    parser.add_argument("--output-dir", default="data/processed", help="Папка для итоговых CSV")
    return parser.parse_args()


def read_csv(raw_dir: Path, name: str, date_columns: list[str] | None = None) -> pd.DataFrame:
    path = raw_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл: {path}")
    return pd.read_csv(path, parse_dates=date_columns or [])


def build_detail_dataset(raw_dir: Path) -> pd.DataFrame:
    orders = read_csv(raw_dir, "orders.csv", ["order_date"])
    order_items = read_csv(raw_dir, "order_items.csv")
    customers = read_csv(raw_dir, "customers.csv", ["signup_date"])
    products = read_csv(raw_dir, "products.csv")

    # 1. Склеиваем строки заказов с заказами, клиентами и товарами.
    dataset = (
        order_items
        .merge(orders, on="order_id", how="left", validate="many_to_one")
        .merge(products, on="product_id", how="left", validate="many_to_one")
        .merge(customers, on="customer_id", how="left", validate="many_to_one")
    )

    # 2. Нормализуем даты и добавляем поля периодов для дашборда.
    dataset["order_date"] = pd.to_datetime(dataset["order_date"]).dt.date
    dataset["order_datetime"] = pd.to_datetime(dataset["order_date"])
    dataset["order_month"] = dataset["order_datetime"].dt.to_period("M").astype(str)
    dataset["order_week"] = dataset["order_datetime"].dt.strftime("%G-W%V")
    dataset["day_of_week"] = dataset["order_datetime"].dt.day_name()

    # 3. Считаем денежные метрики на уровне строки заказа.
    dataset["gross_revenue"] = dataset["quantity"] * dataset["unit_price"]
    dataset["discount_amount"] = (dataset["gross_revenue"] * dataset["discount_pct"]).round(2)
    dataset["net_revenue"] = (dataset["gross_revenue"] - dataset["discount_amount"]).round(2)
    dataset["cost"] = dataset["quantity"] * dataset["unit_cost"]
    dataset["margin"] = (dataset["net_revenue"] - dataset["cost"]).round(2)
    dataset["margin_pct"] = (dataset["margin"] / dataset["net_revenue"].replace(0, pd.NA)).fillna(0).round(4)

    # 4. Флаги статусов нужны, чтобы BI не считал отмененные заказы как продажи.
    dataset["is_paid"] = dataset["order_status"].isin(PAID_STATUSES).astype(int)
    dataset["is_cancelled"] = dataset["order_status"].isin(CANCELLED_STATUSES).astype(int)

    # 5. Повторные покупки считаем на уровне заказа, потом возвращаем в детализацию.
    order_totals = (
        dataset.groupby(["order_id", "customer_id", "order_datetime"], as_index=False)
        .agg(order_total=("net_revenue", "sum"), order_margin=("margin", "sum"))
        .sort_values(["customer_id", "order_datetime", "order_id"])
    )
    order_totals["order_sequence"] = order_totals.groupby("customer_id").cumcount() + 1
    order_totals["is_repeat_purchase"] = (order_totals["order_sequence"] > 1).astype(int)
    order_totals["avg_check"] = order_totals["order_total"]

    dataset = dataset.merge(
        order_totals[["order_id", "order_total", "order_margin", "order_sequence", "is_repeat_purchase", "avg_check"]],
        on="order_id",
        how="left",
        validate="many_to_one",
    )

    # 6. Удобная сортировка и набор полей для BI.
    columns = [
        "order_date",
        "order_month",
        "order_week",
        "day_of_week",
        "order_id",
        "customer_id",
        "customer_name",
        "city",
        "customer_type",
        "sales_channel",
        "payment_method",
        "order_status",
        "manager",
        "product_id",
        "product_name",
        "category",
        "quantity",
        "unit_price",
        "discount_pct",
        "gross_revenue",
        "discount_amount",
        "net_revenue",
        "cost",
        "margin",
        "margin_pct",
        "is_paid",
        "is_cancelled",
        "order_total",
        "order_margin",
        "avg_check",
        "order_sequence",
        "is_repeat_purchase",
    ]
    return dataset[columns].sort_values(["order_date", "order_id", "product_id"])


def build_daily_metrics(dataset: pd.DataFrame) -> pd.DataFrame:
    paid = dataset[dataset["is_paid"] == 1].copy()
    order_level = paid.drop_duplicates("order_id")

    daily_revenue = paid.groupby("order_date", as_index=False).agg(
        revenue=("net_revenue", "sum"),
        gross_revenue=("gross_revenue", "sum"),
        margin=("margin", "sum"),
        sold_units=("quantity", "sum"),
    )
    daily_orders = order_level.groupby("order_date", as_index=False).agg(
        orders=("order_id", "nunique"),
        customers=("customer_id", "nunique"),
        repeat_orders=("is_repeat_purchase", "sum"),
    )
    daily = daily_revenue.merge(daily_orders, on="order_date", how="left")
    daily["avg_check"] = (daily["revenue"] / daily["orders"].replace(0, pd.NA)).round(2)
    daily["margin_pct"] = (daily["margin"] / daily["revenue"].replace(0, pd.NA)).round(4)
    daily["repeat_order_share"] = (daily["repeat_orders"] / daily["orders"].replace(0, pd.NA)).fillna(0).round(4)
    return daily.sort_values("order_date")


def build_category_metrics(dataset: pd.DataFrame) -> pd.DataFrame:
    paid = dataset[dataset["is_paid"] == 1].copy()
    grouped = paid.groupby(["category", "product_name"], as_index=False).agg(
        revenue=("net_revenue", "sum"),
        orders=("order_id", "nunique"),
        sold_units=("quantity", "sum"),
        margin=("margin", "sum"),
    )
    grouped["avg_check"] = (grouped["revenue"] / grouped["orders"].replace(0, pd.NA)).round(2)
    grouped["margin_pct"] = (grouped["margin"] / grouped["revenue"].replace(0, pd.NA)).round(4)
    return grouped.sort_values("revenue", ascending=False)


def build_customer_metrics(dataset: pd.DataFrame) -> pd.DataFrame:
    paid = dataset[dataset["is_paid"] == 1].copy()
    order_level = paid.drop_duplicates("order_id")
    metrics = order_level.groupby(["customer_id", "customer_name", "city", "customer_type"], as_index=False).agg(
        first_order_date=("order_date", "min"),
        last_order_date=("order_date", "max"),
        orders=("order_id", "nunique"),
        revenue=("order_total", "sum"),
        repeat_purchases=("is_repeat_purchase", "sum"),
    )
    metrics["avg_check"] = (metrics["revenue"] / metrics["orders"].replace(0, pd.NA)).round(2)
    metrics["is_repeat_customer"] = (metrics["orders"] > 1).astype(int)
    return metrics.sort_values("revenue", ascending=False)


def main() -> None:
    args = parse_args()
    raw_dir = Path(args.raw_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = build_detail_dataset(raw_dir)
    daily = build_daily_metrics(dataset)
    category = build_category_metrics(dataset)
    customers = build_customer_metrics(dataset)
    dictionary = pd.DataFrame(DATA_DICTIONARY, columns=["field", "description", "type"])

    dataset.to_csv(output_dir / "dashboard_sales_dataset.csv", index=False)
    daily.to_csv(output_dir / "dashboard_daily_metrics.csv", index=False)
    category.to_csv(output_dir / "dashboard_category_metrics.csv", index=False)
    customers.to_csv(output_dir / "dashboard_customer_metrics.csv", index=False)
    dictionary.to_csv(output_dir / "data_dictionary.csv", index=False)

    print("Готово. Итоговые файлы:")
    for path in sorted(output_dir.glob("*.csv")):
        print(f"- {path}")


if __name__ == "__main__":
    main()
