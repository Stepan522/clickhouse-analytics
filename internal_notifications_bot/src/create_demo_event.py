from __future__ import annotations

from pathlib import Path

from storage import NotificationStorage


def main() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    storage = NotificationStorage(project_dir / "data" / "notification_events.csv")

    event = storage.create_event(
        event_type="new_lead",
        title="Новая заявка с лендинга",
        entity_id="L-DEMO-001",
        priority="high",
        responsible="Мария",
        message="Клиент оставил заявку на автоматизацию отчетности. Нужно связаться сегодня.",
    )

    print(f"Создано событие: {event.event_id}")


if __name__ == "__main__":
    main()
