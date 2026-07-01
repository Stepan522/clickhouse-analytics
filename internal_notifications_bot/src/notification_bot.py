from __future__ import annotations

import asyncio
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from notifier import format_notification, send_telegram_message, send_webhook


load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parents[1]
EVENTS_PATH = PROJECT_DIR / "data" / "notification_events.csv"
RULES_PATH = PROJECT_DIR / "data" / "notification_rules.csv"


def load_events() -> pd.DataFrame:
    return pd.read_csv(EVENTS_PATH)


def load_rules() -> pd.DataFrame:
    rules = pd.read_csv(RULES_PATH)
    return rules[rules["enabled"] == 1]


def prepare_queue(events: pd.DataFrame, rules: pd.DataFrame) -> pd.DataFrame:
    """Готовит очередь уведомлений.

    Оставляем только события с активными правилами и статусом queued.
    """
    active_types = set(rules["event_type"])
    queue = events[
        (events["status"] == "queued")
        & (events["event_type"].isin(active_types))
    ].copy()

    priority_order = {"critical": 1, "high": 2, "normal": 3, "low": 4}
    queue["priority_sort"] = queue["priority"].map(priority_order).fillna(9)

    return queue.sort_values(["priority_sort", "created_at"])


async def process_notifications() -> None:
    """Отправляет уведомления из очереди."""
    events = load_events()
    rules = load_rules()
    queue = prepare_queue(events, rules)

    for _, row in queue.iterrows():
        text = format_notification(row)

        await send_telegram_message(text)
        await send_webhook(row.to_dict())

        events.loc[events["event_id"] == row["event_id"], "status"] = "sent"

    events.to_csv(EVENTS_PATH, index=False, encoding="utf-8")
    print(f"Отправлено уведомлений: {len(queue)}")


def main() -> None:
    asyncio.run(process_notifications())


if __name__ == "__main__":
    main()
