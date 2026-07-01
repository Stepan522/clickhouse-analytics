from __future__ import annotations

import os
from dataclasses import asdict

import httpx

from storage import Lead


def format_manager_message(lead: Lead) -> str:
    return (
        "🆕 Новая заявка\n\n"
        f"ID: {lead.lead_id}\n"
        f"Услуга: {lead.service}\n"
        f"Бюджет: {lead.budget}\n"
        f"Клиент: {lead.name}\n"
        f"Телефон: {lead.phone}\n"
        f"Email: {lead.email}\n\n"
        f"Комментарий: {lead.comment}"
    )


async def send_to_telegram(lead: Lead) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("MANAGER_CHAT_ID")

    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": format_manager_message(lead)}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()


async def send_to_webhook(lead: Lead) -> None:
    webhook_url = os.getenv("LEAD_WEBHOOK_URL")

    if not webhook_url:
        return

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=asdict(lead))
        response.raise_for_status()
