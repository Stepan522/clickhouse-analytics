from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field, field_validator


class LeadRequest(BaseModel):
    """Данные, которые форма сайта отправляет в API."""

    name: str = Field(..., min_length=2, max_length=120)
    phone: str = Field(..., min_length=7, max_length=30)
    email: EmailStr
    service: str = Field(..., min_length=2, max_length=160)
    comment: str = Field("", max_length=2000)

    utm_source: Optional[str] = ""
    utm_medium: Optional[str] = ""
    utm_campaign: Optional[str] = ""
    utm_content: Optional[str] = ""
    utm_term: Optional[str] = ""
    page_url: Optional[str] = ""
    referrer: Optional[str] = ""

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        """Упрощенная нормализация телефона для демо."""
        digits = "".join(ch for ch in value if ch.isdigit())

        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        elif len(digits) == 10:
            digits = "7" + digits

        if len(digits) != 11 or not digits.startswith("7"):
            raise ValueError("Телефон должен быть в формате РФ: +7XXXXXXXXXX")

        return f"+{digits}"


class LeadRecord(LeadRequest):
    """Запись, которую сохраняем после приема заявки."""

    lead_id: str
    created_at: str
    status: str = "new"
    crm_status: str = "queued"
    telegram_status: str = "queued"
    sheets_status: str = "queued"

    @classmethod
    def from_request(cls, lead: LeadRequest) -> "LeadRecord":
        return cls(
            **lead.model_dump(),
            lead_id=f"L-{datetime.now():%Y%m%d}-{uuid4().hex[:6].upper()}",
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )


class LeadResponse(BaseModel):
    """Ответ API для формы сайта."""

    ok: bool
    lead_id: str
    message: str
