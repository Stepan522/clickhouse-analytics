from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]


def build_alert_message(alerts: pd.DataFrame) -> str:
    if alerts.empty:
        return "✅ По остаткам все хорошо. Критичных предупреждений нет."

    lines = [
        "📦 Контроль остатков маркетплейсов",
        "",
        f"Товаров с предупреждениями: {len(alerts)}",
        "",
    ]

    for _, row in alerts.iterrows():
        lines.append(
            f"• {row['marketplace']} / {row['sku']}: {row['product_name']} — "
            f"доступно {int(row['available_stock'])}, статус {row['alert']}"
        )

    return "\n".join(lines)


def main() -> None:
    alerts_path = PROJECT_DIR / "data" / "processed" / "stock_alerts.csv"
    alerts = pd.read_csv(alerts_path)
    print(build_alert_message(alerts))


if __name__ == "__main__":
    main()
