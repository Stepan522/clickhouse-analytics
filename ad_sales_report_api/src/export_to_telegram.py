from __future__ import annotations

from pathlib import Path
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]


def build_message(summary: pd.DataFrame) -> str:
    total_cost = summary["cost"].sum()
    total_leads = summary["leads"].sum()
    total_sales = summary["sales"].sum()
    total_revenue = summary["revenue"].sum()

    lines = [
        "📊 Реклама и продажи за период",
        "",
        f"Расход: {total_cost:,.0f} ₽".replace(",", " "),
        f"Лиды: {int(total_leads)}",
        f"Продажи: {int(total_sales)}",
        f"Выручка: {total_revenue:,.0f} ₽".replace(",", " "),
        "",
        "По каналам:",
    ]

    for _, row in summary.sort_values("cost", ascending=False).iterrows():
        lines.append(
            f"• {row['channel']}: {row['cost']:,.0f} ₽, лиды {int(row['leads'])}, продажи {int(row['sales'])}, ROMI {row['romi']:.1%}".replace(",", " ")
        )
    return "\n".join(lines)


def main() -> None:
    summary = pd.read_csv(PROJECT_DIR / "data" / "processed" / "channel_summary.csv")
    print(build_message(summary))


if __name__ == "__main__":
    main()
