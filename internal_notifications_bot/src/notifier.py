from __future__ import annotations

import os

import httpx
import pandas as pd


def format_notification(row: pd.Series) -> str:
    """Формирует текст внутреннего уведомления."""
    priority_emoji = {
        "critical": "🚨",
        "high": "⚠️",
        "normal": "ℹ️",
        "low": "🔹",
    }

    emoji = priority_emoji.get(str(row["priority"]), "ℹ️")

    return (
        f"{emoji} {row['title']}\n\n"
        f"Тип: {row['event_type']}\n"
        f"Объект: {row['entity_id']}\n"
        f"Ответственный: {row['responsible']}\n"
        f"Приоритет: {row['priority']}\n\n"
        f"{row['message']}"
    )


async def send_telegram_message(text: str, chat_id: str | None = None) -> None:
    """Отправляет сообщение в Telegram.

    Если переменные окружения не заданы, отправка пропускается.
    Так демо-проект можно запускать локально без токена.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or os.getenv("NOTIFICATION_CHAT_ID")

    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()


async def send_webhook(payload: dict) -> None:
    """Отправляет событие во внешний webhook, если он задан."""
    webhook_url = os.getenv("NOTIFICATION_WEBHOOK_URL")

    if not webhook_url:
        return

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=payload)
        response.raise_for_status()
