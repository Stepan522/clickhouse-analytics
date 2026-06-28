"""Генерация PNG-превью для README и сайта.

Скрин создается из итоговых CSV, поэтому его можно обновлять вместе с данными.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


BLUE = "#2563EB"
NAVY = "#0F172A"
GRAY = "#64748B"
LIGHT_GRAY = "#F8FAFC"
BORDER = "#E2E8F0"
GREEN = "#16A34A"
RED = "#EF4444"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Собрать PNG-превью датасета")
    parser.add_argument("--processed-dir", default="data/processed", help="Папка с итоговыми CSV")
    parser.add_argument("--output", default="assets/report_preview.png", help="Файл PNG")
    return parser.parse_args()


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    path = Path("/usr/share/fonts/truetype/dejavu") / name
    return ImageFont.truetype(str(path), size=size)


def money(value: float) -> str:
    return f"{value:,.0f} ₽".replace(",", " ")


def card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int = 20) -> None:
    draw.rounded_rectangle(box, radius=radius, fill="white", outline=BORDER, width=1)


def draw_kpi(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, title: str, value: str, delta: str, delta_color: str) -> None:
    card(draw, (x, y, x + w, y + h), radius=18)
    draw.text((x + 24, y + 22), title, fill=GRAY, font=font(20))
    draw.text((x + 24, y + 58), value, fill=NAVY, font=font(24, bold=True))
    draw.text((x + 24, y + 102), delta, fill=delta_color, font=font(18))
    draw.ellipse((x + w - 72, y + 32, x + w - 28, y + 76), fill="#DBEAFE")
    draw.text((x + w - 61, y + 39), "◆", fill=BLUE, font=font(22, bold=True))


def make_line_chart(daily: pd.DataFrame, output: Path) -> None:
    last = daily.tail(14).copy()
    last["order_date"] = pd.to_datetime(last["order_date"])
    last["date_label"] = last["order_date"].dt.strftime("%d.%m")

    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, ax = plt.subplots(figsize=(7.4, 3.0), dpi=160)
    ax.plot(last["date_label"], last["revenue"], marker="o", linewidth=2.5)
    ax.fill_between(range(len(last)), last["revenue"].to_numpy(), alpha=0.08)
    ax.set_title("Динамика выручки по дням", loc="left", fontsize=13, fontweight="bold", color=NAVY, pad=10)
    ax.set_ylabel("Выручка, ₽", fontsize=9, color=GRAY)
    ax.grid(axis="y", alpha=0.25)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(BORDER)
    ax.tick_params(axis="x", labelsize=8, colors=GRAY, rotation=0)
    ax.tick_params(axis="y", labelsize=8, colors=GRAY)
    ax.margins(x=0.02)
    fig.tight_layout()
    fig.savefig(output, transparent=True)
    plt.close(fig)


def make_bar_chart(category: pd.DataFrame, output: Path) -> None:
    top = category.groupby("category", as_index=False)["revenue"].sum().sort_values("revenue", ascending=True).tail(7)

    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, ax = plt.subplots(figsize=(5.2, 3.0), dpi=160)
    ax.barh(top["category"], top["revenue"])
    ax.set_title("Выручка по категориям", loc="left", fontsize=13, fontweight="bold", color=NAVY, pad=10)
    ax.set_xlabel("Выручка, ₽", fontsize=9, color=GRAY)
    ax.grid(axis="x", alpha=0.22)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(BORDER)
    ax.tick_params(axis="x", labelsize=8, colors=GRAY)
    ax.tick_params(axis="y", labelsize=9, colors=NAVY)
    fig.tight_layout()
    fig.savefig(output, transparent=True)
    plt.close(fig)


def draw_table(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, rows: list[list[str]]) -> None:
    row_h = 42
    col_widths = [230, 150, 120, 120, 150, 190]
    headers = ["Поле", "Тип", "Пример", "BI", "Расчет", "Комментарий"]
    card(draw, (x, y, x + w, y + row_h * (len(rows) + 1) + 24), radius=18)
    draw.text((x + 24, y + 18), "Фрагмент словаря полей", fill=NAVY, font=font(22, bold=True))
    table_y = y + 62
    draw.rounded_rectangle((x + 20, table_y, x + w - 20, table_y + row_h), radius=8, fill=LIGHT_GRAY)
    cx = x + 36
    for idx, header in enumerate(headers):
        draw.text((cx, table_y + 12), header, fill=GRAY, font=font(14, bold=True))
        cx += col_widths[idx]
    for r_idx, row in enumerate(rows):
        yy = table_y + row_h * (r_idx + 1)
        draw.line((x + 20, yy, x + w - 20, yy), fill=BORDER, width=1)
        cx = x + 36
        for c_idx, value in enumerate(row):
            draw.text((cx, yy + 12), value, fill=NAVY if c_idx == 0 else GRAY, font=font(14, bold=(c_idx == 0)))
            cx += col_widths[c_idx]


def make_preview(processed_dir: Path, output: Path) -> None:
    detail = pd.read_csv(processed_dir / "dashboard_sales_dataset.csv", parse_dates=["order_date"])
    daily = pd.read_csv(processed_dir / "dashboard_daily_metrics.csv", parse_dates=["order_date"])
    category = pd.read_csv(processed_dir / "dashboard_category_metrics.csv")
    customers = pd.read_csv(processed_dir / "dashboard_customer_metrics.csv")

    paid = detail[detail["is_paid"] == 1]
    order_level = paid.drop_duplicates("order_id")

    revenue = paid["net_revenue"].sum()
    orders = order_level["order_id"].nunique()
    avg_check = order_level["order_total"].mean()
    repeat_share = order_level["is_repeat_purchase"].mean() * 100
    margin_pct = paid["margin"].sum() / paid["net_revenue"].sum() * 100

    output.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = output.parent / "_tmp"
    tmp_dir.mkdir(exist_ok=True)
    line_path = tmp_dir / "line.png"
    bar_path = tmp_dir / "bar.png"
    make_line_chart(daily, line_path)
    make_bar_chart(category, bar_path)

    img = Image.new("RGB", (1440, 1160), "#F8FAFC")
    draw = ImageDraw.Draw(img)

    draw.text((62, 40), "Датасет продаж для дашборда", fill=NAVY, font=font(42, bold=True))
    draw.text((64, 96), "Готовая BI-витрина: заказы, клиенты, товары, каналы продаж и оплаты", fill=GRAY, font=font(22))
    draw.rounded_rectangle((1120, 44, 1368, 92), radius=14, fill="white", outline=BORDER)
    draw.text((1144, 57), "Обновлено: 25.06.2026", fill=NAVY, font=font(18))

    kpi_y = 150
    kpis = [
        ("Строк в датасете", f"{len(detail):,}".replace(",", " "), "+ raw → mart", GREEN),
        ("Выручка", money(revenue), "+ очищено", GREEN),
        ("Заказы", f"{orders:,}".replace(",", " "), "+ статусы", GREEN),
        ("Средний чек", money(avg_check), "order-level", BLUE),
        ("Повторные", f"{repeat_share:.1f}%", "+ флаг", GREEN),
    ]
    for i, (title, value, delta, color) in enumerate(kpis):
        draw_kpi(draw, 62 + i * 268, kpi_y, 244, 142, title, value, delta, color)

    # Карты с графиками
    card(draw, (62, 330, 850, 660), radius=22)
    line = Image.open(line_path).convert("RGBA").resize((720, 290))
    img.paste(line, (88, 360), line)

    card(draw, (880, 330, 1378, 660), radius=22)
    bar = Image.open(bar_path).convert("RGBA").resize((456, 290))
    img.paste(bar, (902, 360), bar)

    # Мини-блоки с результатом обработки
    card(draw, (62, 690, 446, 830), radius=18)
    draw.text((88, 718), "Что собрано", fill=NAVY, font=font(22, bold=True))
    draw.text((88, 760), "• orders + items + customers + products", fill=GRAY, font=font(17))
    draw.text((88, 790), "• единые revenue / margin / avg_check", fill=GRAY, font=font(17))

    card(draw, (476, 690, 860, 830), radius=18)
    draw.text((502, 718), "Что исправлено", fill=NAVY, font=font(22, bold=True))
    draw.text((502, 760), "• отмены не попадают в продажи", fill=GRAY, font=font(17))
    draw.text((502, 790), "• повторные покупки считаются кодом", fill=GRAY, font=font(17))

    card(draw, (890, 690, 1378, 830), radius=18)
    draw.text((916, 718), "Маржинальность", fill=NAVY, font=font(22, bold=True))
    draw.text((916, 756), f"{margin_pct:.1f}%", fill=BLUE, font=font(42, bold=True))
    draw.text((1062, 772), "по оплаченным заказам", fill=GRAY, font=font(16))

    table_rows = [
        ["net_revenue", "number", "24817", "метрика", "qty × price − discount", "выручка после скидки"],
        ["avg_check", "number", "17033", "метрика", "order_total", "на уровне заказа"],
        ["is_repeat_purchase", "int", "1", "фильтр", "sequence > 1", "повторная покупка"],
        ["sales_channel", "string", "SEO", "разрез", "из orders", "канал продажи"],
        ["order_month", "string", "2026-06", "период", "date → month", "для динамики"],
    ]
    draw_table(draw, 62, 858, 1316, table_rows)

    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output, quality=95)

    for path in [line_path, bar_path]:
        path.unlink(missing_ok=True)
    tmp_dir.rmdir()


if __name__ == "__main__":
    args = parse_args()
    make_preview(Path(args.processed_dir), Path(args.output))
