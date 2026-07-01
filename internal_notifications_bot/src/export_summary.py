from __future__ import annotations

from pathlib import Path

import pandas as pd


def main() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    events = pd.read_csv(project_dir / "data" / "notification_events.csv")

    summary = (
        events.groupby(["event_type", "priority", "status"], as_index=False)
        .agg(events_count=("event_id", "count"))
        .sort_values("events_count", ascending=False)
    )

    output_path = project_dir / "data" / "notification_summary.csv"
    summary.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Сводка сохранена: {output_path}")


if __name__ == "__main__":
    main()
