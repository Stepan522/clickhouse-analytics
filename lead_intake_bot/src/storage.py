from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4


@dataclass
class Lead:
    lead_id: str
    created_at: str
    name: str
    phone: str
    email: str
    service: str
    budget: str
    comment: str
    status: str = "new"
    manager: str = "Не назначен"
    source: str = "telegram_bot"


class LeadStorage:
    """Сохранение заявок в CSV. В реальном проекте можно заменить на CRM/API."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def create_lead(
        self,
        name: str,
        phone: str,
        email: str,
        service: str,
        budget: str,
        comment: str,
        manager: str = "Мария",
    ) -> Lead:
        lead = Lead(
            lead_id=f"L-{datetime.now():%Y%m%d}-{uuid4().hex[:6].upper()}",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            name=name.strip(),
            phone=phone.strip(),
            email=email.strip().lower(),
            service=service.strip(),
            budget=budget.strip(),
            comment=comment.strip(),
            manager=manager,
        )
        self._append(lead)
        return lead

    def _append(self, lead: Lead) -> None:
        file_exists = self.path.exists()
        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(asdict(lead).keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerow(asdict(lead))
