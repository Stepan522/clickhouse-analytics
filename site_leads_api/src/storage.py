from __future__ import annotations

import csv
from pathlib import Path

from models import LeadRecord


class CsvLeadStorage:
    """Сохраняет заявки в CSV.

    Для портфолио этого достаточно: видно структуру данных и результат.
    В реальном проекте можно заменить на PostgreSQL, ClickHouse, Google Sheets,
    CRM API или очередь сообщений.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, lead: LeadRecord) -> None:
        file_exists = self.path.exists()
        row = lead.model_dump()

        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(row.keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
