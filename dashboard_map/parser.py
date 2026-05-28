import gspread
import requests
import psycopg2
from google.oauth2.service_account import Credentials
from typing import Optional, Tuple

from config import (
    POSTGRES_CONFIG,
    SERVICE_ACCOUNT_FILE,
    SPREADSHEET_NAME,
    WORKSHEET_NAME,
    YANDEX_API_KEY,
)


GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def geocode_address(address: str) -> Optional[Tuple[str, str, Optional[str]]]:
    response = requests.get(
        "https://geocode-maps.yandex.ru/1.x/",
        params={
            "apikey": YANDEX_API_KEY,
            "geocode": address,
            "format": "json",
        },
        timeout=20,
    )
    response.raise_for_status()
    geo = response.json()

    try:
        feature = geo["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]
        lon, lat = feature["Point"]["pos"].split()
        components = feature["metaDataProperty"]["GeocoderMetaData"]["Address"]["Components"]
    except (KeyError, IndexError, ValueError):
        return None

    district = None
    for component in components:
        if component.get("kind") == "area":
            district = component.get("name")
            break

    return lon, lat, district


def main() -> None:
    creds = Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_FILE),
        scopes=GOOGLE_SCOPES,
    )

    gc = gspread.authorize(creds)
    sheet = gc.open(SPREADSHEET_NAME).worksheet(WORKSHEET_NAME)
    rows = sheet.get_all_records()

    with psycopg2.connect(**POSTGRES_CONFIG) as conn:
        with conn.cursor() as cur:
            for idx, row in enumerate(rows, start=2):
                if str(row.get("status", "")).lower() != "ready":
                    continue

                address = (
                    f"{row.get('area', '')}, {row.get('city', '')}, "
                    f"{row.get('street', '')}, {row.get('locality', '')}, "
                    f"{row.get('house', '')}, {row.get('build', '')}"
                )

                geocoded = geocode_address(address)
                if geocoded is None:
                    print("Geocoding error:", address)
                    continue

                lon, lat, district = geocoded

                cur.execute(
                    """
                    INSERT INTO contacts (
                        phone, name, patronymic, surname, area, city,
                        street, locality, house, build, comment, number, date_inst,
                        guarantee, to1, date_to,
                        lon, lat, district
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (number)
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        patronymic = EXCLUDED.patronymic,
                        surname = EXCLUDED.surname,
                        area = EXCLUDED.area,
                        locality = EXCLUDED.locality,
                        build = EXCLUDED.build,
                        comment = EXCLUDED.comment,
                        number = EXCLUDED.number,
                        date_inst = EXCLUDED.date_inst,
                        guarantee = EXCLUDED.guarantee,
                        to1 = EXCLUDED.to1,
                        date_to = EXCLUDED.date_to,
                        lon = EXCLUDED.lon,
                        lat = EXCLUDED.lat,
                        district = EXCLUDED.district;
                    """,
                    (
                        row.get("phone"),
                        row.get("name"),
                        row.get("patronymic"),
                        row.get("surname"),
                        row.get("area"),
                        row.get("city"),
                        row.get("street"),
                        row.get("locality"),
                        row.get("house"),
                        row.get("build"),
                        row.get("comment"),
                        row.get("number"),
                        row.get("date_inst"),
                        row.get("guarantee"),
                        row.get("to1"),
                        row.get("date_to"),
                        lon,
                        lat,
                        district,
                    ),
                )

                conn.commit()
                sheet.update_cell(idx, list(row.keys()).index("status") + 1, "completed")

    print("Done")


if __name__ == "__main__":
    main()
