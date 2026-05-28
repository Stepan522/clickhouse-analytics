import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()


def get_env(name: str, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Environment variable {name} is required")
    return value


YANDEX_API_KEY = get_env("YANDEX_API_KEY")

SPREADSHEET_NAME = get_env("SPREADSHEET_NAME")
WORKSHEET_NAME = get_env("WORKSHEET_NAME", "Clients")
SERVICE_ACCOUNT_FILE = Path(get_env("SERVICE_ACCOUNT_FILE", "service_account.json"))

POSTGRES_CONFIG = {
    "host": get_env("POSTGRES_HOST"),
    "dbname": get_env("POSTGRES_DB"),
    "user": get_env("POSTGRES_USER"),
    "password": get_env("POSTGRES_PASSWORD"),
    "port": get_env("POSTGRES_PORT", "5432"),
}
