from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


RANDOM_SEED = 42
RAW_ROWS_TARGET = 1847
UNIQUE_CLIENTS = 1535
DUPLICATES_TO_ADD = RAW_ROWS_TARGET - UNIQUE_CLIENTS


FIRST_NAMES = [
    "Алексей", "Иван", "Дмитрий", "Сергей", "Павел", "Михаил", "Андрей", "Никита",
    "Анна", "Мария", "Елена", "Ольга", "Ирина", "Светлана", "Дарья", "Ксения",
]
LAST_NAMES = [
    "Иванов", "Петров", "Сидоров", "Смирнов", "Кузнецов", "Попов", "Орлов",
    "Соколов", "Волков", "Морозов", "Новиков", "Федоров", "Лебедев", "Козлов",
]
CITIES = ["Москва", "Санкт-Петербург", "Казань", "Екатеринбург", "Новосибирск", "Краснодар", "Нижний Новгород"]
SOURCES = ["CRM", "Сайт", "Реклама", "Маркетплейс", "Колл-центр", "Офлайн"]
LEVELS = ["new", "bronze", "silver", "gold", "vip"]
DOMAINS = ["mail.ru", "gmail.com", "yandex.ru", "company.ru", "example.com"]


def format_phone(phone: str) -> str:
    """Создает грязный вариант телефона из нормального +7XXXXXXXXXX."""
    digits = phone.replace("+", "")
    variants = [
        f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:]}",
        f"8{digits[1:]}",
        f"7{digits[1:]}",
        f"+7{digits[1:]}",
        f"{digits[1:4]} {digits[4:7]} {digits[7:9]} {digits[9:]}",
        f"+7-{digits[1:4]}-{digits[4:7]}-{digits[7:9]}-{digits[9:]}",
    ]
    return random.choice(variants)


def distort_email(email: str) -> str:
    """Создает грязный вариант email."""
    variants = [
        email,
        email.upper(),
        f" {email} ",
        email.replace("@", " @ "),
        email.replace(".", " . ", 1),
    ]
    return random.choice(variants)


def distort_name(name: str) -> str:
    """Создает грязный вариант ФИО."""
    variants = [
        name,
        name.upper(),
        name.lower(),
        f" {name} ",
        "  ".join(name.split()),
    ]
    return random.choice(variants)


def build_base_clients(n: int) -> pd.DataFrame:
    random.seed(RANDOM_SEED)

    rows = []
    start_date = datetime(2025, 1, 1)

    for i in range(1, n + 1):
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)

        phone = f"+79{random.randint(100000000, 999999999)}"
        email = f"{first_name.lower()}.{last_name.lower()}{i}@{random.choice(DOMAINS)}".replace("ё", "е")

        registered_at = start_date + timedelta(days=random.randint(0, 520))
        last_order_at = registered_at + timedelta(days=random.randint(0, 380))
        total_orders = random.randint(0, 14)
        revenue = 0 if total_orders == 0 else random.randint(2_500, 180_000)

        rows.append(
            {
                "client_id": f"RAW-{i:05d}",
                "internal_id": f"CRM-{i:05d}" if random.random() > 0.12 else "",
                "full_name": f"{last_name} {first_name}",
                "phone": format_phone(phone) if random.random() > 0.08 else "",
                "email": distort_email(email) if random.random() > 0.10 else "",
                "city": random.choice(CITIES),
                "source": random.choice(SOURCES),
                "registered_at": registered_at.strftime("%Y-%m-%d"),
                "last_order_at": last_order_at.strftime("%Y-%m-%d"),
                "total_orders": total_orders,
                "revenue_rub": revenue,
                "loyalty_level": random.choice(LEVELS),
                "consent_email": random.choice([1, 1, 1, 0]),
                "consent_sms": random.choice([1, 1, 0]),
            }
        )

    return pd.DataFrame(rows)


def add_duplicates(df: pd.DataFrame, duplicates_to_add: int) -> pd.DataFrame:
    random.seed(RANDOM_SEED + 1)

    duplicate_rows = []
    sample = df.sample(duplicates_to_add, random_state=RANDOM_SEED + 2)

    for idx, row in sample.iterrows():
        new_row = row.copy()

        # Новый сырой ID, но это тот же клиент.
        new_row["client_id"] = f"RAW-DUP-{idx:05d}"

        # В дублях часто отличается внутренний ID, формат имени/контактов или источник.
        new_row["internal_id"] = "" if random.random() > 0.35 else row["internal_id"]
        new_row["full_name"] = distort_name(str(row["full_name"]))
        new_row["phone"] = format_phone(str(row["phone"])) if str(row["phone"]).strip() else row["phone"]
        new_row["email"] = distort_email(str(row["email"])) if str(row["email"]).strip() else row["email"]
        new_row["source"] = random.choice(SOURCES)

        # Часть показателей может быть устаревшей или неполной.
        if random.random() > 0.65:
            new_row["city"] = ""
        if random.random() > 0.70:
            new_row["total_orders"] = max(0, int(row["total_orders"]) - random.randint(0, 2))
            new_row["revenue_rub"] = max(0, int(row["revenue_rub"]) - random.randint(0, 10_000))

        duplicate_rows.append(new_row.to_dict())

    return pd.concat([df, pd.DataFrame(duplicate_rows)], ignore_index=True)


def main() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    output_path = project_dir / "data" / "raw" / "clients_dirty.csv"

    base = build_base_clients(UNIQUE_CLIENTS)
    dirty = add_duplicates(base, DUPLICATES_TO_ADD)

    # Немного перемешиваем строки, как в реальной выгрузке из CRM/таблиц.
    dirty = dirty.sample(frac=1, random_state=RANDOM_SEED + 3).reset_index(drop=True)
    dirty.to_csv(output_path, index=False, encoding="utf-8")

    print(f"Создан файл: {output_path}")
    print(f"Строк в сырой базе: {len(dirty)}")


if __name__ == "__main__":
    main()
