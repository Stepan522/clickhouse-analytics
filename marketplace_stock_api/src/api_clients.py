from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parents[1]


class MarketplaceApiClient:
    """API-клиент маркетплейса с mock-режимом.

    MOCK_MODE=1 читает локальные JSON-файлы, чтобы проект можно было запустить без реальных ключей.
    MOCK_MODE=0 отправляет запросы в реальные API маркетплейсов.
    """

    def __init__(self, marketplace: str, base_url: str | None, token: str | None, mock_file: str) -> None:
        self.marketplace = marketplace
        self.base_url = base_url
        self.token = token
        self.mock_file = PROJECT_DIR / "data" / "mock_api" / mock_file
        self.mock_mode = os.getenv("MOCK_MODE", "1") == "1"

    async def get_json(self, endpoint: str, params: dict[str, Any] | None = None) -> list[dict]:
        if self.mock_mode:
            return pd.read_json(self.mock_file).to_dict("records")

        if not self.base_url:
            raise RuntimeError(f"Не задан base_url для {self.marketplace}")

        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def fetch_stock(self) -> pd.DataFrame:
        data = await self.get_json("/stocks")
        return pd.DataFrame(data)


class OrdersApiClient(MarketplaceApiClient):
    async def fetch_orders(self, date_from: str, date_to: str) -> pd.DataFrame:
        data = await self.get_json("/orders", {"date_from": date_from, "date_to": date_to})
        return pd.DataFrame(data)


def load_products() -> pd.DataFrame:
    return pd.read_json(PROJECT_DIR / "data" / "mock_api" / "products.json")


def build_clients() -> tuple[MarketplaceApiClient, MarketplaceApiClient, MarketplaceApiClient, OrdersApiClient]:
    ozon = MarketplaceApiClient(
        marketplace="Ozon",
        base_url=os.getenv("OZON_API_URL"),
        token=os.getenv("OZON_API_TOKEN"),
        mock_file="ozon_stock.json",
    )
    wildberries = MarketplaceApiClient(
        marketplace="Wildberries",
        base_url=os.getenv("WB_API_URL"),
        token=os.getenv("WB_API_TOKEN"),
        mock_file="wildberries_stock.json",
    )
    yandex = MarketplaceApiClient(
        marketplace="Yandex Market",
        base_url=os.getenv("YANDEX_MARKET_API_URL"),
        token=os.getenv("YANDEX_MARKET_API_TOKEN"),
        mock_file="yandex_market_stock.json",
    )
    orders = OrdersApiClient(
        marketplace="Orders",
        base_url=os.getenv("ORDERS_API_URL"),
        token=os.getenv("ORDERS_API_TOKEN"),
        mock_file="orders.json",
    )
    return ozon, wildberries, yandex, orders
