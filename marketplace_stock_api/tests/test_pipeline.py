import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from pipeline import build_stock_report


def test_low_stock_alert():
    stock = pd.DataFrame([
        {"marketplace": "Ozon", "sku": "SKU-1", "warehouse": "WH", "stock": 2, "reserved": 0, "price": 1000, "commission_rate": 0.1, "status": "active"}
    ])
    orders = pd.DataFrame([
        {"date": "2026-06-25", "marketplace": "Ozon", "sku": "SKU-1", "orders": 3, "revenue": 3000}
    ])
    products = pd.DataFrame([
        {"sku": "SKU-1", "product_name": "Товар", "category": "Категория", "cost_price": 500}
    ])

    report, alerts = build_stock_report(stock, orders, products)

    assert report.loc[0, "alert"] == "reorder"
    assert len(alerts) == 1
