from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]


class BaseApiClient:
    """API-клиент с mock-режимом.

    MOCK_MODE=1 читает локальные JSON, чтобы проект запускался без реальных токенов.
    MOCK_MODE=0 ходит в реальные API рекламных кабинетов, CRM и заказов.
    """

    def __init__(self, base_url: str | None, token: str | None, mock_file: str) -> None:
        self.base_url = base_url
        self.token = token
        self.mock_file = PROJECT_DIR / "data" / "mock_api" / mock_file
        self.mock_mode = os.getenv("MOCK_MODE", "1") == "1"

    async def get_json(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict]:
        if self.mock_mode:
            return pd.read_json(self.mock_file).to_dict("records")

        if not self.base_url:
            raise RuntimeError("Не задан base_url для API-клиента")

        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()


class AdsApiClient(BaseApiClient):
    async def fetch_spend(self, date_from: str, date_to: str) -> pd.DataFrame:
        data = await self.get_json("/stats/spend", {"date_from": date_from, "date_to": date_to})
        return pd.DataFrame(data)


class CrmApiClient(BaseApiClient):
    async def fetch_leads(self, date_from: str, date_to: str) -> pd.DataFrame:
        data = await self.get_json("/leads", {"date_from": date_from, "date_to": date_to})
        return pd.DataFrame(data)


class OrdersApiClient(BaseApiClient):
    async def fetch_orders(self, date_from: str, date_to: str) -> pd.DataFrame:
        data = await self.get_json("/orders", {"date_from": date_from, "date_to": date_to})
        return pd.DataFrame(data)


def build_clients() -> tuple[AdsApiClient, CrmApiClient, OrdersApiClient]:
    return (
        AdsApiClient(os.getenv("ADS_API_URL"), os.getenv("ADS_API_TOKEN"), "ad_spend.json"),
        CrmApiClient(os.getenv("CRM_API_URL"), os.getenv("CRM_API_TOKEN"), "crm_leads.json"),
        OrdersApiClient(os.getenv("ORDERS_API_URL"), os.getenv("ORDERS_API_TOKEN"), "orders.json"),
    )
