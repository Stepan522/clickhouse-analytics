from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import pandas as pd

from api_clients import build_clients

PROJECT_DIR = Path(__file__).resolve().parents[1]


def normalize_ad_spend(ad_spend: pd.DataFrame) -> pd.DataFrame:
    ad_spend = ad_spend.copy()
    ad_spend["date"] = pd.to_datetime(ad_spend["date"]).dt.date
    ad_spend["cost"] = ad_spend["cost"].astype(float)
    ad_spend["clicks"] = ad_spend["clicks"].astype(int)
    ad_spend["impressions"] = ad_spend["impressions"].astype(int)
    return ad_spend


def normalize_leads(leads: pd.DataFrame) -> pd.DataFrame:
    leads = leads.copy()
    leads["created_at"] = pd.to_datetime(leads["created_at"])
    leads["date"] = leads["created_at"].dt.date
    leads["is_won"] = leads["status"].eq("won").astype(int)
    return leads


def normalize_orders(orders: pd.DataFrame) -> pd.DataFrame:
    orders = orders.copy()
    orders["paid_at"] = pd.to_datetime(orders["paid_at"])
    orders["revenue"] = orders["revenue"].astype(float)
    orders["gross_profit"] = orders["revenue"] * orders["gross_margin"].astype(float)
    return orders


def build_report(ad_spend: pd.DataFrame, leads: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    """Объединяет расходы рекламы, заявки из CRM и продажи в один отчет."""
    ad_spend = normalize_ad_spend(ad_spend)
    leads = normalize_leads(leads)
    orders = normalize_orders(orders)

    leads_with_orders = leads.merge(orders, on="order_id", how="left")

    spend_agg = (
        ad_spend.groupby(["date", "channel", "campaign"], as_index=False)
        .agg(impressions=("impressions", "sum"), clicks=("clicks", "sum"), cost=("cost", "sum"))
    )

    leads_agg = (
        leads_with_orders.groupby(["date", "channel", "campaign"], as_index=False)
        .agg(
            leads=("lead_id", "nunique"),
            sales=("is_won", "sum"),
            revenue=("revenue", "sum"),
            gross_profit=("gross_profit", "sum"),
        )
    )

    report = spend_agg.merge(leads_agg, on=["date", "channel", "campaign"], how="outer").fillna(0)

    report["ctr"] = (report["clicks"] / report["impressions"]).where(report["impressions"] > 0, 0)
    report["cpl"] = (report["cost"] / report["leads"]).where(report["leads"] > 0, 0)
    report["cpo"] = (report["cost"] / report["sales"]).where(report["sales"] > 0, 0)
    report["cr_lead_to_sale"] = (report["sales"] / report["leads"]).where(report["leads"] > 0, 0)
    report["romi"] = ((report["gross_profit"] - report["cost"]) / report["cost"]).where(report["cost"] > 0, 0)

    for col in ["ctr", "cpl", "cpo", "cr_lead_to_sale", "romi"]:
        report[col] = report[col].round(4)

    return report.sort_values(["date", "channel", "campaign"])


async def run_pipeline(date_from: str, date_to: str, output_dir: Path) -> pd.DataFrame:
    ads_client, crm_client, orders_client = build_clients()

    ad_spend, leads, orders = await asyncio.gather(
        ads_client.fetch_spend(date_from, date_to),
        crm_client.fetch_leads(date_from, date_to),
        orders_client.fetch_orders(date_from, date_to),
    )

    report = build_report(ad_spend, leads, orders)

    output_dir.mkdir(parents=True, exist_ok=True)
    report.to_csv(output_dir / "ad_sales_unified_report.csv", index=False, encoding="utf-8")

    channel_summary = (
        report.groupby("channel", as_index=False)
        .agg(cost=("cost", "sum"), leads=("leads", "sum"), sales=("sales", "sum"), revenue=("revenue", "sum"), gross_profit=("gross_profit", "sum"))
    )
    channel_summary["cpl"] = (channel_summary["cost"] / channel_summary["leads"]).where(channel_summary["leads"] > 0, 0).round(2)
    channel_summary["romi"] = ((channel_summary["gross_profit"] - channel_summary["cost"]) / channel_summary["cost"]).where(channel_summary["cost"] > 0, 0).round(3)
    channel_summary.to_csv(output_dir / "channel_summary.csv", index=False, encoding="utf-8")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Расходы рекламы и продажи в одном отчете")
    parser.add_argument("--date-from", default="2026-06-19")
    parser.add_argument("--date-to", default="2026-06-25")
    parser.add_argument("--output-dir", default="data/processed")
    args = parser.parse_args()

    output_dir = PROJECT_DIR / args.output_dir
    report = asyncio.run(run_pipeline(args.date_from, args.date_to, output_dir))

    print("Готово")
    print(f"Строк в отчете: {len(report)}")
    print(f"Файл: {output_dir / 'ad_sales_unified_report.csv'}")


if __name__ == "__main__":
    main()
