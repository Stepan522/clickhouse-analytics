from __future__ import annotations

from pathlib import Path

import pandas as pd


def main() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    leads_path = project_dir / "data" / "leads.csv"
    output_path = project_dir / "data" / "lead_summary.csv"

    leads = pd.read_csv(leads_path)
    summary = (
        leads.groupby(["service", "status"], as_index=False)
        .agg(leads_count=("lead_id", "count"))
        .sort_values("leads_count", ascending=False)
    )

    summary.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Сводка сохранена: {output_path}")


if __name__ == "__main__":
    main()
