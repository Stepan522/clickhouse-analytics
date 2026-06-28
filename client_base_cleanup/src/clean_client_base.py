from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import pandas as pd


EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")


def normalize_phone(value: object) -> str:
    """Приводит телефон к формату +7XXXXXXXXXX."""
    if pd.isna(value):
        return ""

    digits = re.sub(r"\D+", "", str(value))

    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits.startswith("7"):
        pass
    else:
        return ""

    return f"+{digits}"


def normalize_email(value: object) -> str:
    """Чистит email: регистр, пробелы, простая валидация."""
    if pd.isna(value):
        return ""

    email = str(value).strip().lower()
    email = re.sub(r"\s+", "", email)

    return email if EMAIL_RE.match(email) else ""


def normalize_name(value: object) -> str:
    """Стандартизирует ФИО."""
    if pd.isna(value):
        return ""

    name = str(value).replace("ё", "е").replace("Ё", "Е")
    name = re.sub(r"\s+", " ", name.strip())
    return name.title()


def normalize_city(value: object) -> str:
    if pd.isna(value):
        return ""

    city = re.sub(r"\s+", " ", str(value).strip())
    return city.title()


def build_duplicate_key(row: pd.Series) -> str:
    """
    Приоритет ключей дедупликации:
    1. Телефон — самый надежный бытовой идентификатор.
    2. Email — если телефона нет.
    3. ФИО + город — fallback для неполных записей.
    """
    if row["phone_clean"]:
        return f"phone:{row['phone_clean']}"
    if row["email_clean"]:
        return f"email:{row['email_clean']}"

    name_city = f"{row['full_name_clean']}|{row['city_clean']}"
    return "name_city:" + hashlib.sha1(name_city.encode("utf-8")).hexdigest()[:16]


def completeness_score(row: pd.Series) -> int:
    """Оценка полноты контакта для выбора основной записи в группе дублей."""
    fields = [
        "full_name_clean",
        "phone_clean",
        "email_clean",
        "city_clean",
        "registered_at",
        "last_order_at",
        "loyalty_level",
    ]
    return sum(bool(str(row.get(field, "")).strip()) for field in fields)


def enrich_from_group(group: pd.DataFrame, column: str) -> object:
    """Берем первое непустое значение в группе дублей."""
    values = group[column].dropna().astype(str)
    values = values[values.str.strip() != ""]
    return values.iloc[0] if len(values) else ""


def choose_master_record(group: pd.DataFrame) -> pd.Series:
    """Выбирает лучшую запись: полнее, новее и с большей историей покупок."""
    sorted_group = group.sort_values(
        by=["completeness_score", "last_order_dt", "revenue_rub", "total_orders"],
        ascending=[False, False, False, False],
    )
    return sorted_group.iloc[0].copy()


def clean_client_base(input_path: Path, output_dir: Path) -> dict[str, int | float]:
    df = pd.read_csv(input_path)

    raw_rows = len(df)

    # Нормализация контактов.
    df["full_name_clean"] = df["full_name"].apply(normalize_name)
    df["phone_clean"] = df["phone"].apply(normalize_phone)
    df["email_clean"] = df["email"].apply(normalize_email)
    df["city_clean"] = df["city"].apply(normalize_city)

    df["registered_dt"] = pd.to_datetime(df["registered_at"], errors="coerce")
    df["last_order_dt"] = pd.to_datetime(df["last_order_at"], errors="coerce")

    df["completeness_score"] = df.apply(completeness_score, axis=1)
    df["duplicate_key"] = df.apply(build_duplicate_key, axis=1)
    df["duplicate_group_size"] = df.groupby("duplicate_key")["client_id"].transform("count")
    df["is_duplicate_group"] = df["duplicate_group_size"] > 1

    clean_rows = []
    duplicate_rows = []

    for group_id, (duplicate_key, group) in enumerate(df.groupby("duplicate_key"), start=1):
        master = choose_master_record(group)

        # Обогащаем мастер-запись непустыми значениями из группы.
        master["full_name_clean"] = enrich_from_group(group, "full_name_clean")
        master["phone_clean"] = enrich_from_group(group, "phone_clean")
        master["email_clean"] = enrich_from_group(group, "email_clean")
        master["city_clean"] = enrich_from_group(group, "city_clean")

        master["raw_records_in_group"] = len(group)
        master["merged_client_ids"] = ", ".join(group["client_id"].astype(str).tolist())

        clean_rows.append(master)

        if len(group) > 1:
            duplicate_rows.append(
                {
                    "duplicate_group_id": group_id,
                    "duplicate_key": duplicate_key,
                    "records_in_group": len(group),
                    "selected_client_id": master["client_id"],
                    "merged_client_ids": ", ".join(group["client_id"].astype(str).tolist()),
                    "dedup_reason": "phone/email/name_city match",
                }
            )

    clean = pd.DataFrame(clean_rows)

    # Финальная схема для CRM, рассылок и аналитики.
    clean["client_uid"] = clean["duplicate_key"].apply(
        lambda x: hashlib.sha1(str(x).encode("utf-8")).hexdigest()[:12]
    )

    clean_export = clean[
        [
            "client_uid",
            "client_id",
            "full_name_clean",
            "phone_clean",
            "email_clean",
            "city_clean",
            "source",
            "registered_at",
            "last_order_at",
            "total_orders",
            "revenue_rub",
            "loyalty_level",
            "consent_email",
            "consent_sms",
            "raw_records_in_group",
            "merged_client_ids",
        ]
    ].rename(
        columns={
            "full_name_clean": "full_name",
            "phone_clean": "phone",
            "email_clean": "email",
            "city_clean": "city",
            "source": "primary_source",
        }
    )

    clean_export = clean_export.sort_values(["revenue_rub", "total_orders"], ascending=False)

    output_dir.mkdir(parents=True, exist_ok=True)
    clean_export.to_csv(output_dir / "clients_clean.csv", index=False, encoding="utf-8")

    duplicate_report = pd.DataFrame(duplicate_rows)
    duplicate_report.to_csv(output_dir / "duplicate_groups.csv", index=False, encoding="utf-8")

    # Отдельный список записей, которые были дублями.
    duplicate_records = df[df["is_duplicate_group"]].copy()
    duplicate_records.to_csv(output_dir / "duplicate_records_raw.csv", index=False, encoding="utf-8")

    data_dictionary = pd.DataFrame(
        [
            ["client_uid", "Стабильный ID клиента после дедупликации"],
            ["client_id", "ID выбранной мастер-записи из сырой базы"],
            ["full_name", "Нормализованное ФИО"],
            ["phone", "Телефон в формате +7XXXXXXXXXX"],
            ["email", "Email в нижнем регистре без лишних пробелов"],
            ["city", "Нормализованный город"],
            ["primary_source", "Источник из мастер-записи"],
            ["total_orders", "Количество заказов в мастер-записи"],
            ["revenue_rub", "Выручка по клиенту в рублях"],
            ["raw_records_in_group", "Сколько сырых строк было объединено в клиента"],
            ["merged_client_ids", "Список сырых ID, объединенных в одну запись"],
        ],
        columns=["column", "description"],
    )
    data_dictionary.to_csv(output_dir / "data_dictionary.csv", index=False, encoding="utf-8")

    unique_rows = len(clean_export)
    duplicates_found = raw_rows - unique_rows

    before_valid_phone = int((df["phone_clean"] != "").sum())
    before_valid_email = int((df["email_clean"] != "").sum())
    after_valid_phone = int((clean_export["phone"] != "").sum())
    after_valid_email = int((clean_export["email"] != "").sum())

    contact_quality_before = round((before_valid_phone + before_valid_email) / (raw_rows * 2) * 100, 1)
    contact_quality_after = round((after_valid_phone + after_valid_email) / (unique_rows * 2) * 100, 1)

    summary = pd.DataFrame(
        [
            ["Строк в сырой базе", raw_rows, unique_rows, raw_rows - unique_rows],
            ["Найдено дублей", duplicates_found, 0, duplicates_found],
            ["Валидных телефонов", before_valid_phone, after_valid_phone, after_valid_phone - before_valid_phone],
            ["Валидных email", before_valid_email, after_valid_email, after_valid_email - before_valid_email],
            ["Качество контактов, %", contact_quality_before, contact_quality_after, round(contact_quality_after - contact_quality_before, 1)],
        ],
        columns=["metric", "before", "after", "delta"],
    )
    summary.to_csv(output_dir / "quality_summary.csv", index=False, encoding="utf-8")

    return {
        "raw_rows": raw_rows,
        "unique_rows": unique_rows,
        "duplicates_found": duplicates_found,
        "contact_quality_before": contact_quality_before,
        "contact_quality_after": contact_quality_after,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Очистка и дедупликация клиентской базы")
    parser.add_argument("--input", default="data/raw/clients_dirty.csv", help="Путь к сырой базе клиентов")
    parser.add_argument("--output-dir", default="data/processed", help="Папка для готовых файлов")
    args = parser.parse_args()

    project_dir = Path(__file__).resolve().parents[1]
    input_path = project_dir / args.input
    output_dir = project_dir / args.output_dir

    stats = clean_client_base(input_path=input_path, output_dir=output_dir)

    print("Готово")
    print(f"Сырых строк: {stats['raw_rows']}")
    print(f"Уникальных клиентов: {stats['unique_rows']}")
    print(f"Найдено дублей: {stats['duplicates_found']}")
    print(f"Качество контактов: {stats['contact_quality_before']}% → {stats['contact_quality_after']}%")


if __name__ == "__main__":
    main()
