from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4


@dataclass
class NotificationEvent:
    """Событие, по которому нужно отправить внутреннее уведомление."""

    event_id: str
    created_at: str
    event_type: str
    title: str
    entity_id: str
    priority: str
    responsible: str
    status: str
    channel: str
    message: str


class NotificationStorage:
    """Простой слой хранения событий в CSV.

    В реальном проекте можно заменить на PostgreSQL, ClickHouse,
    Google Sheets, CRM API или очередь сообщений.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def create_event(
        self,
        event_type: str,
        title: str,
        entity_id: str,
        priority: str,
        responsible: str,
        message: str,
        channel: str = "telegram",
    ) -> NotificationEvent:
        event = NotificationEvent(
            event_id=f"E-{datetime.now():%Y%m%d}-{uuid4().hex[:6].upper()}",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            event_type=event_type,
            title=title,
            entity_id=entity_id,
            priority=priority,
            responsible=responsible,
            status="queued",
            channel=channel,
            message=message,
        )

        self._append(event)
        return event

    def _append(self, event: NotificationEvent) -> None:
        file_exists = self.path.exists()

        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(asdict(event).keys()))

            if not file_exists:
                writer.writeheader()

            writer.writerow(asdict(event))
