from __future__ import annotations

from pathlib import Path
import pandas as pd


def main() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    leads = pd.read_csv(project_dir / "data" / "leads.csv")
    summary = (
        leads.groupby(["service", "utm_source"], as_index=False)
        .agg(leads_count=("lead_id", "count"))
        .sort_values("leads_count", ascending=False)
    )
    output_path = project_dir / "data" / "leads_summary.csv"
    summary.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Сводка сохранена: {output_path}")


if __name__ == "__main__":
    main()
