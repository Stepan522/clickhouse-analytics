from __future__ import annotations

import os
from dataclasses import asdict

import httpx

from storage import SupportTicket


def format_operator_message(ticket: SupportTicket) -> str:
    return (
        "⚠️ Вопрос передан оператору\n\n"
        f"ID: {ticket.ticket_id}\n"
        f"Клиент: {ticket.client_name}\n"
        f"Канал: {ticket.channel}\n"
        f"Тема: {ticket.detected_intent}\n\n"
        f"Вопрос: {ticket.question}"
    )


async def send_to_operator(ticket: SupportTicket) -> None:
    """Отправляет сложный вопрос оператору в Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("OPERATOR_CHAT_ID")

    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": format_operator_message(ticket)}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()


async def send_to_support_webhook(ticket: SupportTicket) -> None:
    """Отправляет обращение во внешнюю систему поддержки/CRM."""
    webhook_url = os.getenv("SUPPORT_WEBHOOK_URL")

    if not webhook_url:
        return

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=asdict(ticket))
        response.raise_for_status()
