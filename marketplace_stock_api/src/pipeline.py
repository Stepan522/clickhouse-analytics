from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import pandas as pd

from api_clients import build_clients, load_products

PROJECT_DIR = Path(__file__).resolve().parents[1]


def build_stock_report(stock: pd.DataFrame, orders: pd.DataFrame, products: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Объединяет остатки, цены, комиссии и продажи в одну витрину."""
    stock = stock.copy()
    orders = orders.copy()
    products = products.copy()

    stock["available_stock"] = stock["stock"] - stock["reserved"]
    stock["commission_amount"] = stock["price"] * stock["commission_rate"]
    stock["net_price"] = stock["price"] - stock["commission_amount"]

    orders["date"] = pd.to_datetime(orders["date"]).dt.date

    sales_agg = (
        orders.groupby(["marketplace", "sku"], as_index=False)
        .agg(
            orders_3d=("orders", "sum"),
            revenue_3d=("revenue", "sum"),
        )
    )

    report = (
        stock.merge(products, on="sku", how="left")
        .merge(sales_agg, on=["marketplace", "sku"], how="left")
        .fillna({"orders_3d": 0, "revenue_3d": 0})
    )

    report["orders_3d"] = report["orders_3d"].astype(int)
    report["daily_sales_avg"] = (report["orders_3d"] / 3).round(2)
    report["days_of_stock"] = (report["available_stock"] / report["daily_sales_avg"]).replace([float("inf")], 999).fillna(999).round(1)
    report["gross_margin_per_unit"] = (report["net_price"] - report["cost_price"]).round(2)
    report["gross_margin_rate"] = (report["gross_margin_per_unit"] / report["price"]).round(4)

    def alert(row: pd.Series) -> str:
        if row["available_stock"] <= 0:
            return "out_of_stock"
        if row["available_stock"] <= 5 or row["days_of_stock"] <= 3:
            return "reorder"
        if row["gross_margin_rate"] < 0.15:
            return "low_margin"
        return "ok"

    report["alert"] = report.apply(alert, axis=1)

    final_cols = [
        "marketplace",
        "sku",
        "product_name",
        "category",
        "warehouse",
        "stock",
        "reserved",
        "available_stock",
        "price",
        "commission_rate",
        "commission_amount",
        "net_price",
        "cost_price",
        "gross_margin_per_unit",
        "gross_margin_rate",
        "orders_3d",
        "revenue_3d",
        "daily_sales_avg",
        "days_of_stock",
        "status",
        "alert",
    ]
    report = report[final_cols].sort_values(["alert", "marketplace", "sku"])

    alerts = report[report["alert"].ne("ok")].copy()

    return report, alerts


async def run_pipeline(date_from: str, date_to: str, output_dir: Path) -> pd.DataFrame:
    ozon, wb, yandex, orders_client = build_clients()

    ozon_stock, wb_stock, yandex_stock, orders = await asyncio.gather(
        ozon.fetch_stock(),
        wb.fetch_stock(),
        yandex.fetch_stock(),
        orders_client.fetch_orders(date_from, date_to),
    )

    stock = pd.concat([ozon_stock, wb_stock, yandex_stock], ignore_index=True)
    products = load_products()

    report, alerts = build_stock_report(stock, orders, products)

    output_dir.mkdir(parents=True, exist_ok=True)
    report.to_csv(output_dir / "marketplace_stock_report.csv", index=False, encoding="utf-8")
    alerts.to_csv(output_dir / "stock_alerts.csv", index=False, encoding="utf-8")

    marketplace_summary = (
        report.groupby("marketplace", as_index=False)
        .agg(
            sku_count=("sku", "nunique"),
            available_stock=("available_stock", "sum"),
            revenue_3d=("revenue_3d", "sum"),
            alerts_count=("alert", lambda x: (x != "ok").sum()),
        )
        .sort_values("revenue_3d", ascending=False)
    )
    marketplace_summary.to_csv(output_dir / "marketplace_summary.csv", index=False, encoding="utf-8")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Маркетплейсы и остатки: загрузка по API")
    parser.add_argument("--date-from", default="2026-06-23")
    parser.add_argument("--date-to", default="2026-06-25")
    parser.add_argument("--output-dir", default="data/processed")
    args = parser.parse_args()

    output_dir = PROJECT_DIR / args.output_dir
    report = asyncio.run(run_pipeline(args.date_from, args.date_to, output_dir))

    print("Готово")
    print(f"Строк в отчете: {len(report)}")
    print(f"Файл: {output_dir / 'marketplace_stock_report.csv'}")


if __name__ == "__main__":
    main()
