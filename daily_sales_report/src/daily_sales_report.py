"""
Ежедневный отчет по продажам.

Скрипт показывает типовой пайплайн автоматизации отчетности:
1. Забираем данные из CSV / выгрузки CRM / результата SQL-запроса.
2. Считаем KPI за выбранный день и сравниваем с предыдущим днем.
3. Формируем HTML и PNG-скрин отчета.
4. При необходимости отправляем результат в Telegram или Email.

В демо-версии используется файл data/sales.csv.
В реальном проекте функцию read_sales_data можно заменить на чтение из ClickHouse,
PostgreSQL, Google Sheets, CRM API или любой другой системы.
"""

from __future__ import annotations

import argparse
import os
import smtplib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd
import requests

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


PAID_STATUSES = {"paid", "completed", "done", "success"}
CANCEL_STATUSES = {"cancelled", "canceled", "cancel"}


@dataclass
class KpiBlock:
    """Один KPI-блок для отчета."""

    title: str
    value: str
    delta: str
    delta_raw: float


@dataclass
class DailyReport:
    """Готовая витрина показателей для вывода в HTML, PNG и сообщения."""

    report_date: date
    kpis: list[KpiBlock]
    channel_table: pd.DataFrame
    category_table: pd.DataFrame
    alerts: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Автоматический ежедневный отчет по продажам")
    parser.add_argument("--data", default="data/sales.csv", help="Путь к CSV с заказами")
    parser.add_argument("--output-dir", default="reports", help="Папка для готовых отчетов")
    parser.add_argument(
        "--report-date",
        default=None,
        help="Дата отчета в формате YYYY-MM-DD. По умолчанию берется последняя дата из данных",
    )
    parser.add_argument("--send-telegram", action="store_true", help="Отправить отчет в Telegram")
    parser.add_argument("--send-email", action="store_true", help="Отправить отчет на Email")
    return parser.parse_args()


def read_sales_data(path: str | Path) -> pd.DataFrame:
    """Читает данные и приводит типы.

    Обязательные поля:
    - order_date
    - order_id
    - revenue
    - status
    - channel
    - category
    """
    df = pd.read_csv(path)
    df["order_date"] = pd.to_datetime(df["order_date"]).dt.date
    df["status"] = df["status"].str.lower().str.strip()
    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce").fillna(0)
    df["is_new_client"] = df["is_new_client"].astype(bool)
    return df


def get_report_date(df: pd.DataFrame, value: str | None) -> date:
    if value:
        return datetime.strptime(value, "%Y-%m-%d").date()
    return max(df["order_date"])


def calc_delta(current: float, previous: float) -> tuple[str, float]:
    """Возвращает дельту в процентах и сырое значение."""
    if previous == 0 and current == 0:
        return "0%", 0.0
    if previous == 0:
        return "+100%", 100.0

    delta = (current - previous) / previous * 100
    sign = "+" if delta > 0 else ""
    return f"{sign}{delta:.1f}%", delta


def money(value: float) -> str:
    return f"{value:,.0f} ₽".replace(",", " ")


def number(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def paid_orders(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["status"].isin(PAID_STATUSES)].copy()


def build_report(df: pd.DataFrame, report_date: date) -> DailyReport:
    current_day = df[df["order_date"] == report_date]
    previous_day = df[df["order_date"] == report_date - timedelta(days=1)]

    current_paid = paid_orders(current_day)
    previous_paid = paid_orders(previous_day)

    revenue = current_paid["revenue"].sum()
    prev_revenue = previous_paid["revenue"].sum()

    orders = current_paid["order_id"].nunique()
    prev_orders = previous_paid["order_id"].nunique()

    avg_check = revenue / orders if orders else 0
    prev_avg_check = prev_revenue / prev_orders if prev_orders else 0

    new_clients = int(current_paid["is_new_client"].sum())
    prev_new_clients = int(previous_paid["is_new_client"].sum())

    cancels = current_day[current_day["status"].isin(CANCEL_STATUSES)]["order_id"].nunique()
    prev_cancels = previous_day[previous_day["status"].isin(CANCEL_STATUSES)]["order_id"].nunique()

    revenue_delta, revenue_delta_raw = calc_delta(revenue, prev_revenue)
    orders_delta, orders_delta_raw = calc_delta(orders, prev_orders)
    avg_check_delta, avg_check_delta_raw = calc_delta(avg_check, prev_avg_check)
    new_clients_delta, new_clients_delta_raw = calc_delta(new_clients, prev_new_clients)
    cancels_delta, cancels_delta_raw = calc_delta(cancels, prev_cancels)

    kpis = [
        KpiBlock("Выручка", money(revenue), revenue_delta, revenue_delta_raw),
        KpiBlock("Заказы", number(orders), orders_delta, orders_delta_raw),
        KpiBlock("Средний чек", money(avg_check), avg_check_delta, avg_check_delta_raw),
        KpiBlock("Новые клиенты", number(new_clients), new_clients_delta, new_clients_delta_raw),
        KpiBlock("Отмены", number(cancels), cancels_delta, cancels_delta_raw),
    ]

    channel_table = (
        current_paid.groupby("channel", as_index=False)
        .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"))
        .sort_values("revenue", ascending=False)
    )
    channel_table["avg_check"] = channel_table["revenue"] / channel_table["orders"]

    category_table = (
        current_paid.groupby("category", as_index=False)
        .agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"))
        .sort_values("revenue", ascending=False)
    )
    category_table["avg_check"] = category_table["revenue"] / category_table["orders"]

    alerts = build_alerts(
        revenue_delta_raw=revenue_delta_raw,
        orders_delta_raw=orders_delta_raw,
        avg_check_delta_raw=avg_check_delta_raw,
        cancels=cancels,
        prev_cancels=prev_cancels,
    )

    return DailyReport(
        report_date=report_date,
        kpis=kpis,
        channel_table=channel_table,
        category_table=category_table,
        alerts=alerts,
    )


def build_alerts(
    revenue_delta_raw: float,
    orders_delta_raw: float,
    avg_check_delta_raw: float,
    cancels: int,
    prev_cancels: int,
) -> list[str]:
    """Формирует список отклонений, на которые стоит обратить внимание."""
    alerts: list[str] = []

    if revenue_delta_raw <= -15:
        alerts.append("Выручка просела больше чем на 15% к предыдущему дню")
    if orders_delta_raw <= -15:
        alerts.append("Количество заказов снизилось больше чем на 15%")
    if avg_check_delta_raw <= -10:
        alerts.append("Средний чек снизился больше чем на 10%")
    if cancels > prev_cancels and cancels >= 3:
        alerts.append("Количество отмен выше предыдущего дня")

    if not alerts:
        alerts.append("Критичных отклонений не найдено")

    return alerts


def format_table(df: pd.DataFrame, name_col: str) -> str:
    rows = []
    for _, row in df.iterrows():
        rows.append(
            f"""
            <tr>
                <td>{row[name_col]}</td>
                <td>{money(row['revenue'])}</td>
                <td>{number(row['orders'])}</td>
                <td>{money(row['avg_check'])}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def build_html(report: DailyReport) -> str:
    kpi_cards = "\n".join(
        f"""
        <div class="card">
            <div class="card-title">{kpi.title}</div>
            <div class="card-value">{kpi.value}</div>
            <div class="card-delta {'good' if kpi.delta_raw >= 0 else 'bad'}">{kpi.delta} к прошлому дню</div>
        </div>
        """
        for kpi in report.kpis
    )

    alerts = "".join(f"<li>{alert}</li>" for alert in report.alerts)

    return f"""
<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <title>Ежедневный отчет по продажам</title>
    <style>
        body {{
            margin: 0;
            background: #f4f7fb;
            color: #0f172a;
            font-family: Inter, Arial, sans-serif;
        }}
        .wrap {{
            max-width: 1080px;
            margin: 32px auto;
            padding: 0 24px;
        }}
        .header {{
            background: #0f172a;
            color: #fff;
            border-radius: 24px;
            padding: 28px 32px;
            margin-bottom: 20px;
        }}
        .date {{ color: #93c5fd; font-size: 16px; margin-top: 8px; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 14px;
            margin: 20px 0;
        }}
        .card {{
            background: #fff;
            border-radius: 18px;
            padding: 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, .08);
        }}
        .card-title {{ color: #64748b; font-size: 13px; }}
        .card-value {{ font-size: 24px; font-weight: 800; margin: 8px 0; }}
        .card-delta {{ font-size: 13px; }}
        .good {{ color: #059669; }}
        .bad {{ color: #dc2626; }}
        .section {{
            background: #fff;
            border-radius: 18px;
            padding: 22px;
            margin-bottom: 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, .08);
        }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px 10px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
        th {{ color: #64748b; font-weight: 600; }}
        ul {{ margin-bottom: 0; }}
    </style>
</head>
<body>
<div class="wrap">
    <div class="header">
        <h1>Ежедневный отчет по продажам</h1>
        <div class="date">Дата отчета: {report.report_date.strftime('%d.%m.%Y')}</div>
    </div>

    <div class="grid">
        {kpi_cards}
    </div>

    <div class="section">
        <h2>Продажи по каналам</h2>
        <table>
            <thead>
                <tr><th>Канал</th><th>Выручка</th><th>Заказы</th><th>Средний чек</th></tr>
            </thead>
            <tbody>{format_table(report.channel_table, 'channel')}</tbody>
        </table>
    </div>

    <div class="section">
        <h2>Продажи по категориям</h2>
        <table>
            <thead>
                <tr><th>Категория</th><th>Выручка</th><th>Заказы</th><th>Средний чек</th></tr>
            </thead>
            <tbody>{format_table(report.category_table, 'category')}</tbody>
        </table>
    </div>

    <div class="section">
        <h2>Отклонения</h2>
        <ul>{alerts}</ul>
    </div>
</div>
</body>
</html>
""".strip()


def save_html(report: DailyReport, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"daily_sales_report_{report.report_date}.html"
    html_path.write_text(build_html(report), encoding="utf-8")
    return html_path


def render_png(report: DailyReport, output_dir: Path) -> Path:
    """Рисует короткий PNG-скрин для README и Telegram."""
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"daily_sales_report_{report.report_date}.png"

    fig = plt.figure(figsize=(12, 7), dpi=160)
    fig.patch.set_facecolor("#f4f7fb")

    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    ax.text(0.06, 0.92, "Ежедневный отчет по продажам", fontsize=24, fontweight="bold", color="#0f172a")
    ax.text(0.06, 0.875, f"Дата отчета: {report.report_date.strftime('%d.%m.%Y')}", fontsize=12, color="#64748b")

    x_positions = [0.06, 0.245, 0.43, 0.615, 0.80]
    for x, kpi in zip(x_positions, report.kpis):
        ax.add_patch(
            plt.Rectangle((x, 0.70), 0.155, 0.12, transform=ax.transAxes, facecolor="white", edgecolor="#e5e7eb")
        )
        delta_color = "#059669" if kpi.delta_raw >= 0 else "#dc2626"
        ax.text(x + 0.015, 0.78, kpi.title, fontsize=10, color="#64748b")
        ax.text(x + 0.015, 0.742, kpi.value, fontsize=16, fontweight="bold", color="#0f172a")
        ax.text(x + 0.015, 0.714, kpi.delta, fontsize=9, color=delta_color)

    def draw_table(title: str, df: pd.DataFrame, y: float, name_col: str) -> None:
        ax.text(0.06, y + 0.20, title, fontsize=15, fontweight="bold", color="#0f172a")
        headers = ["Сегмент", "Выручка", "Заказы", "Средний чек"]
        rows = []
        for _, row in df.head(5).iterrows():
            rows.append([row[name_col], money(row["revenue"]), number(row["orders"]), money(row["avg_check"])])

        table = ax.table(
            cellText=rows,
            colLabels=headers,
            bbox=[0.06, y, 0.88, 0.17],
            cellLoc="left",
            colLoc="left",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        for (row_idx, _), cell in table.get_celld().items():
            cell.set_edgecolor("#e5e7eb")
            if row_idx == 0:
                cell.set_facecolor("#f8fafc")
                cell.set_text_props(weight="bold", color="#64748b")
            else:
                cell.set_facecolor("white")

    draw_table("Продажи по каналам", report.channel_table, 0.45, "channel")
    draw_table("Продажи по категориям", report.category_table, 0.17, "category")

    alert_text = " • ".join(report.alerts)
    ax.text(0.06, 0.08, f"Отклонения: {alert_text}", fontsize=10, color="#0f172a")

    fig.savefig(png_path, bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)
    return png_path


def build_text_message(report: DailyReport) -> str:
    lines = [
        f"Ежедневный отчет по продажам за {report.report_date.strftime('%d.%m.%Y')}",
        "",
    ]

    for kpi in report.kpis:
        lines.append(f"{kpi.title}: {kpi.value} ({kpi.delta} к прошлому дню)")

    lines.append("\nОтклонения:")
    lines.extend(f"- {alert}" for alert in report.alerts)
    return "\n".join(lines)


def send_to_telegram(report: DailyReport, image_path: Path) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        raise RuntimeError("Не заполнены TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID")

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with image_path.open("rb") as image:
        response = requests.post(
            url,
            data={"chat_id": chat_id, "caption": build_text_message(report)},
            files={"photo": image},
            timeout=30,
        )
    response.raise_for_status()


def send_to_email(report: DailyReport, html_path: Path, image_path: Path) -> None:
    required_env = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM", "EMAIL_TO"]
    missed = [name for name in required_env if not os.getenv(name)]
    if missed:
        raise RuntimeError(f"Не заполнены переменные окружения: {', '.join(missed)}")

    msg = EmailMessage()
    msg["Subject"] = f"Ежедневный отчет по продажам — {report.report_date.strftime('%d.%m.%Y')}"
    msg["From"] = os.getenv("EMAIL_FROM")
    msg["To"] = os.getenv("EMAIL_TO")
    msg.set_content(build_text_message(report))
    msg.add_alternative(html_path.read_text(encoding="utf-8"), subtype="html")

    msg.add_attachment(
        image_path.read_bytes(),
        maintype="image",
        subtype="png",
        filename=image_path.name,
    )

    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", "587"))) as smtp:
        smtp.starttls()
        smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        smtp.send_message(msg)


def main() -> None:
    if load_dotenv:
        load_dotenv()

    args = parse_args()
    df = read_sales_data(args.data)
    report_date = get_report_date(df, args.report_date)
    report = build_report(df, report_date)

    output_dir = Path(args.output_dir)
    html_path = save_html(report, output_dir)
    png_path = render_png(report, output_dir)

    print(f"HTML отчет: {html_path}")
    print(f"PNG отчет:  {png_path}")

    if args.send_telegram:
        send_to_telegram(report, png_path)
        print("Отчет отправлен в Telegram")

    if args.send_email:
        send_to_email(report, html_path, png_path)
        print("Отчет отправлен на Email")


if __name__ == "__main__":
    main()
