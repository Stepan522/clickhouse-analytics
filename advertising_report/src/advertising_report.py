"""
Ежедневный отчет по рекламе.

Скрипт показывает типовой пайплайн автоматизации маркетинговой отчетности:
1. Забираем расходы, клики и показы из рекламных кабинетов или CSV.
2. Склеиваем рекламные метрики с заявками, заказами и выручкой.
3. Считаем KPI: CTR, CPC, CPL, CPA, ROAS и конверсии.
4. Формируем HTML/PNG-отчет и подсвечиваем кампании, где сливается бюджет.
5. При необходимости отправляем результат в Telegram или Email.

В демо-версии используется файл data/ads_daily.csv.
В реальном проекте функцию read_ads_data можно заменить на чтение из ClickHouse,
Google Sheets, Яндекс Директ, VK Ads, CRM API или другой системы.
"""

from __future__ import annotations

import argparse
import os
import smtplib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import requests

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


TARGET_CPA = 3500
MIN_ROAS = 3.0


@dataclass
class KpiBlock:
    """Один KPI-блок для отчета."""

    title: str
    value: str
    delta: str
    delta_raw: float
    higher_is_better: bool = True

    @property
    def is_good(self) -> bool:
        if self.delta_raw == 0:
            return True
        return self.delta_raw > 0 if self.higher_is_better else self.delta_raw < 0


@dataclass
class AdvertisingReport:
    """Готовая витрина показателей для вывода в HTML, PNG и сообщение."""

    report_date: date
    kpis: list[KpiBlock]
    source_table: pd.DataFrame
    campaign_table: pd.DataFrame
    bad_campaigns: pd.DataFrame
    alerts: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Автоматический отчет по рекламе")
    parser.add_argument("--data", default="data/ads_daily.csv", help="Путь к CSV с рекламными данными")
    parser.add_argument("--output-dir", default="reports", help="Папка для готовых отчетов")
    parser.add_argument(
        "--report-date",
        default=None,
        help="Дата отчета в формате YYYY-MM-DD. По умолчанию берется последняя дата из данных",
    )
    parser.add_argument("--send-telegram", action="store_true", help="Отправить отчет в Telegram")
    parser.add_argument("--send-email", action="store_true", help="Отправить отчет на Email")
    return parser.parse_args()


def read_ads_data(path: str | Path) -> pd.DataFrame:
    """Читает данные и приводит типы.

    Обязательные поля:
    - date
    - source
    - campaign
    - impressions
    - clicks
    - cost
    - leads
    - orders
    - revenue
    """
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.date

    numeric_cols = ["impressions", "clicks", "cost", "leads", "orders", "revenue"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


def get_report_date(df: pd.DataFrame, value: str | None) -> date:
    if value:
        return datetime.strptime(value, "%Y-%m-%d").date()
    return max(df["date"])


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


def percent(value: float) -> str:
    return f"{value:.2f}%"


def ratio(value: float) -> str:
    return f"{value:.2f}x"


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет производные рекламные метрики."""
    result = df.copy()
    result["ctr"] = result.apply(lambda row: safe_div(row["clicks"], row["impressions"]) * 100, axis=1)
    result["cpc"] = result.apply(lambda row: safe_div(row["cost"], row["clicks"]), axis=1)
    result["cpl"] = result.apply(lambda row: safe_div(row["cost"], row["leads"]), axis=1)
    result["cpa"] = result.apply(lambda row: safe_div(row["cost"], row["orders"]), axis=1)
    result["lead_cr"] = result.apply(lambda row: safe_div(row["leads"], row["clicks"]) * 100, axis=1)
    result["order_cr"] = result.apply(lambda row: safe_div(row["orders"], row["leads"]) * 100, axis=1)
    result["roas"] = result.apply(lambda row: safe_div(row["revenue"], row["cost"]), axis=1)
    return result


def aggregate(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    grouped = (
        df.groupby(group_cols, as_index=False)
        .agg(
            impressions=("impressions", "sum"),
            clicks=("clicks", "sum"),
            cost=("cost", "sum"),
            leads=("leads", "sum"),
            orders=("orders", "sum"),
            revenue=("revenue", "sum"),
        )
        .sort_values("cost", ascending=False)
    )
    return add_metrics(grouped)


def build_report(df: pd.DataFrame, report_date: date) -> AdvertisingReport:
    current_day = df[df["date"] == report_date]
    previous_day = df[df["date"] == report_date - timedelta(days=1)]

    current_total = aggregate(current_day, ["date"])
    previous_total = aggregate(previous_day, ["date"])

    current = current_total.iloc[0] if not current_total.empty else pd.Series(dtype=float)
    previous = previous_total.iloc[0] if not previous_total.empty else pd.Series(dtype=float)

    spend = float(current.get("cost", 0))
    prev_spend = float(previous.get("cost", 0))

    leads = float(current.get("leads", 0))
    prev_leads = float(previous.get("leads", 0))

    cpl = float(current.get("cpl", 0))
    prev_cpl = float(previous.get("cpl", 0))

    cpa = float(current.get("cpa", 0))
    prev_cpa = float(previous.get("cpa", 0))

    roas = float(current.get("roas", 0))
    prev_roas = float(previous.get("roas", 0))

    revenue = float(current.get("revenue", 0))
    prev_revenue = float(previous.get("revenue", 0))

    spend_delta, spend_delta_raw = calc_delta(spend, prev_spend)
    leads_delta, leads_delta_raw = calc_delta(leads, prev_leads)
    cpl_delta, cpl_delta_raw = calc_delta(cpl, prev_cpl)
    cpa_delta, cpa_delta_raw = calc_delta(cpa, prev_cpa)
    roas_delta, roas_delta_raw = calc_delta(roas, prev_roas)
    revenue_delta, revenue_delta_raw = calc_delta(revenue, prev_revenue)

    kpis = [
        KpiBlock("Расход", money(spend), spend_delta, spend_delta_raw, higher_is_better=False),
        KpiBlock("Заявки", number(leads), leads_delta, leads_delta_raw),
        KpiBlock("CPL", money(cpl), cpl_delta, cpl_delta_raw, higher_is_better=False),
        KpiBlock("CPA", money(cpa), cpa_delta, cpa_delta_raw, higher_is_better=False),
        KpiBlock("ROAS", ratio(roas), roas_delta, roas_delta_raw),
        KpiBlock("Выручка", money(revenue), revenue_delta, revenue_delta_raw),
    ]

    source_table = aggregate(current_day, ["source"])
    campaign_table = aggregate(current_day, ["source", "campaign"])

    bad_campaigns = campaign_table[
        ((campaign_table["orders"] == 0) & (campaign_table["cost"] >= 10000))
        | ((campaign_table["orders"] > 0) & (campaign_table["cpa"] > TARGET_CPA))
        | ((campaign_table["roas"] < MIN_ROAS) & (campaign_table["cost"] >= 10000))
    ].sort_values(["cost", "cpa"], ascending=False)

    alerts = build_alerts(
        leads_delta_raw=leads_delta_raw,
        cpl_delta_raw=cpl_delta_raw,
        cpa_delta_raw=cpa_delta_raw,
        roas=roas,
        roas_delta_raw=roas_delta_raw,
        bad_campaigns=bad_campaigns,
    )

    return AdvertisingReport(
        report_date=report_date,
        kpis=kpis,
        source_table=source_table,
        campaign_table=campaign_table,
        bad_campaigns=bad_campaigns,
        alerts=alerts,
    )


def build_alerts(
    leads_delta_raw: float,
    cpl_delta_raw: float,
    cpa_delta_raw: float,
    roas: float,
    roas_delta_raw: float,
    bad_campaigns: pd.DataFrame,
) -> list[str]:
    """Формирует список отклонений, на которые стоит обратить внимание."""
    alerts: list[str] = []

    if leads_delta_raw <= -15:
        alerts.append("Количество заявок снизилось больше чем на 15% к предыдущему дню")
    if cpl_delta_raw >= 20:
        alerts.append("CPL вырос больше чем на 20%")
    if cpa_delta_raw >= 20:
        alerts.append("CPA вырос больше чем на 20%")
    if roas < MIN_ROAS:
        alerts.append(f"ROAS ниже целевого значения {MIN_ROAS:.1f}x")
    if roas_delta_raw <= -20:
        alerts.append("ROAS просел больше чем на 20%")
    if not bad_campaigns.empty:
        alerts.append(f"Найдено кампаний с риском слива бюджета: {len(bad_campaigns)}")

    if not alerts:
        alerts.append("Критичных отклонений не найдено")

    return alerts


def format_source_table(df: pd.DataFrame) -> str:
    rows = []
    for _, row in df.iterrows():
        rows.append(
            f"""
            <tr>
                <td>{row['source']}</td>
                <td>{money(row['cost'])}</td>
                <td>{number(row['leads'])}</td>
                <td>{money(row['cpl'])}</td>
                <td>{money(row['cpa'])}</td>
                <td>{ratio(row['roas'])}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def format_campaign_table(df: pd.DataFrame) -> str:
    rows = []
    for _, row in df.head(8).iterrows():
        rows.append(
            f"""
            <tr>
                <td>{row['source']}</td>
                <td>{row['campaign']}</td>
                <td>{money(row['cost'])}</td>
                <td>{number(row['leads'])}</td>
                <td>{money(row['cpl'])}</td>
                <td>{money(row['cpa'])}</td>
                <td>{ratio(row['roas'])}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def build_html(report: AdvertisingReport) -> str:
    kpi_cards = "\n".join(
        f"""
        <div class="card">
            <div class="card-title">{kpi.title}</div>
            <div class="card-value">{kpi.value}</div>
            <div class="card-delta {'good' if kpi.is_good else 'bad'}">{kpi.delta} к прошлому дню</div>
        </div>
        """
        for kpi in report.kpis
    )

    alerts = "".join(f"<li>{alert}</li>" for alert in report.alerts)

    bad_campaigns = ""
    if not report.bad_campaigns.empty:
        bad_campaigns = f"""
        <div class="section danger">
            <h2>Кампании для проверки</h2>
            <table>
                <thead>
                    <tr><th>Источник</th><th>Кампания</th><th>Расход</th><th>Заявки</th><th>CPL</th><th>CPA</th><th>ROAS</th></tr>
                </thead>
                <tbody>{format_campaign_table(report.bad_campaigns)}</tbody>
            </table>
        </div>
        """

    return f"""
<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <title>Отчет по рекламе</title>
    <style>
        body {{
            margin: 0;
            background: #f4f7fb;
            color: #0f172a;
            font-family: Inter, Arial, sans-serif;
        }}
        .wrap {{
            max-width: 1180px;
            margin: 32px auto;
            padding: 0 24px;
        }}
        .header {{
            background: #0f766e;
            color: #fff;
            border-radius: 24px;
            padding: 28px 32px;
            margin-bottom: 20px;
        }}
        .date {{ color: #ccfbf1; font-size: 16px; margin-top: 8px; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(6, 1fr);
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
        .danger {{ border: 1px solid #fecaca; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px 10px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
        th {{ color: #64748b; font-weight: 600; }}
        ul {{ margin-bottom: 0; }}
    </style>
</head>
<body>
<div class="wrap">
    <div class="header">
        <h1>Отчет по рекламе</h1>
        <div class="date">Дата отчета: {report.report_date.strftime('%d.%m.%Y')}</div>
    </div>

    <div class="grid">
        {kpi_cards}
    </div>

    <div class="section">
        <h2>Эффективность по рекламным источникам</h2>
        <table>
            <thead>
                <tr><th>Источник</th><th>Расход</th><th>Заявки</th><th>CPL</th><th>CPA</th><th>ROAS</th></tr>
            </thead>
            <tbody>{format_source_table(report.source_table)}</tbody>
        </table>
    </div>

    <div class="section">
        <h2>Кампании по расходу</h2>
        <table>
            <thead>
                <tr><th>Источник</th><th>Кампания</th><th>Расход</th><th>Заявки</th><th>CPL</th><th>CPA</th><th>ROAS</th></tr>
            </thead>
            <tbody>{format_campaign_table(report.campaign_table)}</tbody>
        </table>
    </div>

    {bad_campaigns}

    <div class="section">
        <h2>Отклонения</h2>
        <ul>{alerts}</ul>
    </div>
</div>
</body>
</html>
""".strip()


def save_html(report: AdvertisingReport, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"advertising_report_{report.report_date}.html"
    html_path.write_text(build_html(report), encoding="utf-8")
    return html_path


def render_png(report: AdvertisingReport, output_dir: Path) -> Path:
    """Рисует короткий PNG-скрин для README и Telegram."""
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"advertising_report_{report.report_date}.png"

    fig = plt.figure(figsize=(13, 7.3), dpi=160)
    fig.patch.set_facecolor("#f4f7fb")

    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    ax.text(0.055, 0.92, "Отчет по рекламе", fontsize=26, fontweight="bold", color="#0f172a")
    ax.text(0.055, 0.875, f"Дата отчета: {report.report_date.strftime('%d.%m.%Y')}", fontsize=12, color="#64748b")

    x_positions = [0.055, 0.205, 0.355, 0.505, 0.655, 0.805]
    for x, kpi in zip(x_positions, report.kpis):
        ax.add_patch(
            plt.Rectangle((x, 0.70), 0.13, 0.12, transform=ax.transAxes, facecolor="white", edgecolor="#e5e7eb")
        )
        delta_color = "#059669" if kpi.is_good else "#dc2626"
        ax.text(x + 0.012, 0.78, kpi.title, fontsize=10, color="#64748b")
        ax.text(x + 0.012, 0.742, kpi.value, fontsize=15, fontweight="bold", color="#0f172a")
        ax.text(x + 0.012, 0.714, kpi.delta, fontsize=9, color=delta_color)

    def draw_table(title: str, df: pd.DataFrame, y: float, is_campaign: bool = False) -> None:
        ax.text(0.055, y + 0.20, title, fontsize=15, fontweight="bold", color="#0f172a")
        if is_campaign:
            headers = ["Источник", "Кампания", "Расход", "Заявки", "CPL", "CPA", "ROAS"]
            rows = []
            for _, row in df.head(5).iterrows():
                rows.append([
                    row["source"],
                    row["campaign"],
                    money(row["cost"]),
                    number(row["leads"]),
                    money(row["cpl"]),
                    money(row["cpa"]),
                    ratio(row["roas"]),
                ])
        else:
            headers = ["Источник", "Расход", "Клики", "Заявки", "CPL", "CPA", "ROAS"]
            rows = []
            for _, row in df.head(5).iterrows():
                rows.append([
                    row["source"],
                    money(row["cost"]),
                    number(row["clicks"]),
                    number(row["leads"]),
                    money(row["cpl"]),
                    money(row["cpa"]),
                    ratio(row["roas"]),
                ])

        table = ax.table(
            cellText=rows,
            colLabels=headers,
            bbox=[0.055, y, 0.89, 0.17],
            cellLoc="left",
            colLoc="left",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(8.5)
        for (row_idx, _), cell in table.get_celld().items():
            cell.set_edgecolor("#e5e7eb")
            if row_idx == 0:
                cell.set_facecolor("#f8fafc")
                cell.set_text_props(weight="bold", color="#64748b")
            else:
                cell.set_facecolor("white")

    draw_table("Эффективность по рекламным источникам", report.source_table, 0.45)
    draw_table("Кампании для проверки", report.bad_campaigns if not report.bad_campaigns.empty else report.campaign_table, 0.17, True)

    alert_text = " • ".join(report.alerts)
    ax.text(0.055, 0.08, f"Отклонения: {alert_text}", fontsize=10, color="#0f172a")

    fig.savefig(png_path, bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)
    return png_path


def build_text_message(report: AdvertisingReport) -> str:
    lines = [
        f"Отчет по рекламе за {report.report_date.strftime('%d.%m.%Y')}",
        "",
    ]

    for kpi in report.kpis:
        lines.append(f"{kpi.title}: {kpi.value} ({kpi.delta} к прошлому дню)")

    lines.append("\nОтклонения:")
    lines.extend(f"- {alert}" for alert in report.alerts)
    return "\n".join(lines)


def send_to_telegram(report: AdvertisingReport, image_path: Path) -> None:
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


def send_to_email(report: AdvertisingReport, html_path: Path, image_path: Path) -> None:
    required_env = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM", "EMAIL_TO"]
    missed = [name for name in required_env if not os.getenv(name)]
    if missed:
        raise RuntimeError(f"Не заполнены переменные окружения: {', '.join(missed)}")

    msg = EmailMessage()
    msg["Subject"] = f"Отчет по рекламе — {report.report_date.strftime('%d.%m.%Y')}"
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
    df = read_ads_data(args.data)
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
