from __future__ import annotations

import os
import httpx
from models import LeadRecord


def format_telegram_message(lead: LeadRecord) -> str:
    """Формирует понятное уведомление менеджеру."""
    return (
        "🆕 Новая заявка с сайта\n\n"
        f"ID: {lead.lead_id}\n"
        f"Услуга: {lead.service}\n"
        f"Клиент: {lead.name}\n"
        f"Телефон: {lead.phone}\n"
        f"Email: {lead.email}\n\n"
        f"Комментарий: {lead.comment or '—'}\n\n"
        f"UTM: {lead.utm_source} / {lead.utm_medium} / {lead.utm_campaign}\n"
        f"Страница: {lead.page_url or '—'}"
    )


async def send_to_crm(lead: LeadRecord) -> bool:
    """Отправляет заявку в CRM через webhook."""
    webhook_url = os.getenv("CRM_WEBHOOK_URL")
    if not webhook_url:
        return False
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=lead.model_dump())
        response.raise_for_status()
    return True


async def send_to_google_sheets(lead: LeadRecord) -> bool:
    """Отправляет заявку в Google Sheets через Apps Script webhook."""
    webhook_url = os.getenv("GOOGLE_SHEETS_WEBHOOK_URL")
    if not webhook_url:
        return False
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=lead.model_dump())
        response.raise_for_status()
    return True


async def send_to_telegram(lead: LeadRecord) -> bool:
    """Отправляет уведомление менеджеру в Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": format_telegram_message(lead)}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
    return True
