import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))
from pipeline import build_report


def test_report_has_basic_metrics():
    ad_spend = pd.DataFrame([{"date": "2026-06-25", "channel": "Yandex Direct", "campaign": "search", "impressions": 1000, "clicks": 100, "cost": 1000}])
    leads = pd.DataFrame([{"lead_id": "L1", "created_at": "2026-06-25 10:00:00", "channel": "Yandex Direct", "campaign": "search", "status": "won", "order_id": "O1"}])
    orders = pd.DataFrame([{"order_id": "O1", "paid_at": "2026-06-25 12:00:00", "revenue": 10000, "gross_margin": 0.3}])

    report = build_report(ad_spend, leads, orders)

    assert report.loc[0, "leads"] == 1
    assert report.loc[0, "sales"] == 1
    assert report.loc[0, "cpl"] == 1000
