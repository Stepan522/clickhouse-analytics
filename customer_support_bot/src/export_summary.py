from __future__ import annotations

from pathlib import Path

import pandas as pd


def main() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    tickets = pd.read_csv(project_dir / "data" / "support_tickets.csv")

    summary = (
        tickets.groupby(["detected_intent", "status"], as_index=False)
        .agg(tickets_count=("ticket_id", "count"), operator_share=("need_operator", "mean"))
        .sort_values("tickets_count", ascending=False)
    )
    summary["operator_share"] = (summary["operator_share"] * 100).round(1)

    output_path = project_dir / "data" / "support_summary.csv"
    summary.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Сводка сохранена: {output_path}")


if __name__ == "__main__":
    main()
