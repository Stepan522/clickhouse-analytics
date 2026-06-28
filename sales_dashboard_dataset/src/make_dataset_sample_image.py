"""Создать PNG с примером строк итогового датасета."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

NAVY = "#0F172A"
GRAY = "#64748B"
LIGHT_GRAY = "#F8FAFC"
BORDER = "#E2E8F0"
BLUE = "#2563EB"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size=size)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PNG-пример строк датасета")
    parser.add_argument("--input", default="data/processed/dashboard_sales_dataset.csv")
    parser.add_argument("--output", default="assets/dataset_sample.png")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.input).head(8)
    cols = ["order_date", "order_id", "customer_id", "sales_channel", "category", "net_revenue", "margin", "is_repeat_purchase"]
    sample = df[cols].copy()
    sample["net_revenue"] = sample["net_revenue"].map(lambda x: f"{x:,.0f} ₽".replace(",", " "))
    sample["margin"] = sample["margin"].map(lambda x: f"{x:,.0f} ₽".replace(",", " "))

    headers = ["Дата", "Заказ", "Клиент", "Канал", "Категория", "Выручка", "Маржа", "Повтор"]
    widths = [130, 130, 120, 180, 170, 150, 140, 110]

    img = Image.new("RGB", (1280, 720), "#F8FAFC")
    draw = ImageDraw.Draw(img)
    draw.text((44, 34), "Пример итогового датасета", fill=NAVY, font=font(34, True))
    draw.text((46, 82), "Фрагмент dashboard_sales_dataset.csv после склейки и расчета метрик", fill=GRAY, font=font(20))

    x, y = 44, 140
    draw.rounded_rectangle((x, y, 1236, 650), radius=18, fill="white", outline=BORDER)
    table_x = x + 24
    table_y = y + 34
    row_h = 48
    draw.rounded_rectangle((table_x, table_y, 1212, table_y + row_h), radius=10, fill=LIGHT_GRAY)

    cx = table_x + 14
    for i, h in enumerate(headers):
        draw.text((cx, table_y + 15), h, fill=GRAY, font=font(15, True))
        cx += widths[i]

    for ridx, (_, row) in enumerate(sample.iterrows(), start=1):
        yy = table_y + row_h * ridx
        draw.line((table_x, yy, 1212, yy), fill=BORDER)
        cx = table_x + 14
        values = [str(row[c]) for c in cols]
        for i, value in enumerate(values):
            color = BLUE if cols[i] == "order_id" else NAVY if cols[i] in ["net_revenue", "margin"] else GRAY
            draw.text((cx, yy + 15), value[:22], fill=color, font=font(14, cols[i] in ["net_revenue", "margin"]))
            cx += widths[i]

    draw.text((70, 666), "Данные синтетические. Структура подходит для DataLens, Power BI или Tableau.", fill=GRAY, font=font(16))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    img.save(args.output, quality=95)


if __name__ == "__main__":
    main()
