from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, status
from integrations import send_to_crm, send_to_google_sheets, send_to_telegram
from models import LeadRecord, LeadRequest, LeadResponse
from storage import CsvLeadStorage

load_dotenv()
PROJECT_DIR = Path(__file__).resolve().parents[1]
LEADS_PATH = PROJECT_DIR / "data" / "leads.csv"

app = FastAPI(
    title="Site Leads API",
    description="API для приема заявок с сайта и отправки в CRM, Google Sheets и Telegram.",
    version="1.0.0",
)
storage = CsvLeadStorage(LEADS_PATH)


def check_api_token(x_api_token: str | None = Header(default=None)) -> None:
    """Простая защита endpoint от случайного спама."""
    expected_token = os.getenv("API_TOKEN")
    if expected_token and x_api_token != expected_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/leads", response_model=LeadResponse, dependencies=[Depends(check_api_token)])
async def create_lead(payload: LeadRequest) -> LeadResponse:
    """Принимает заявку с формы сайта."""
    lead = LeadRecord.from_request(payload)

    # Сначала сохраняем локально, чтобы заявка не потерялась даже при ошибке CRM.
    storage.append(lead)

    try:
        lead.crm_status = "sent" if await send_to_crm(lead) else "skipped"
    except Exception:
        lead.crm_status = "error"

    try:
        lead.sheets_status = "sent" if await send_to_google_sheets(lead) else "skipped"
    except Exception:
        lead.sheets_status = "error"

    try:
        lead.telegram_status = "sent" if await send_to_telegram(lead) else "skipped"
    except Exception:
        lead.telegram_status = "error"

    # Для демо сохраняем вторую строку с финальными статусами интеграций.
    # В реальном проекте лучше делать update по lead_id.
    storage.append(lead)

    return LeadResponse(ok=True, lead_id=lead.lead_id, message="Заявка принята и поставлена в очередь обработки.")
