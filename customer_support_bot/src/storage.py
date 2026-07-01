from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4


@dataclass
class SupportTicket:
    ticket_id: str
    created_at: str
    client_name: str
    channel: str
    question: str
    detected_intent: str
    status: str
    need_operator: int


class TicketStorage:
    """Сохраняет обращения клиентов в CSV."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def create_ticket(
        self,
        client_name: str,
        question: str,
        detected_intent: str,
        need_operator: bool,
        channel: str = "telegram",
    ) -> SupportTicket:
        ticket = SupportTicket(
            ticket_id=f"T-{datetime.now():%Y%m%d}-{uuid4().hex[:6].upper()}",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            client_name=client_name.strip() or "Клиент",
            channel=channel,
            question=question.strip(),
            detected_intent=detected_intent,
            status="operator" if need_operator else "answered",
            need_operator=int(need_operator),
        )
        self._append(ticket)
        return ticket

    def _append(self, ticket: SupportTicket) -> None:
        file_exists = self.path.exists()

        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(asdict(ticket).keys()))

            if not file_exists:
                writer.writeheader()

            writer.writerow(asdict(ticket))
