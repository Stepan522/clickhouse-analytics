"""
Автоматический контроль заявок и просрочек в CRM.

Скрипт читает выгрузку заявок, ищет просроченные действия,
заявки без ответственного, зависшие статусы и сделки с риском потери.
На выходе формируется HTML/PNG-отчет и CSV со списком проблемных заявок.
"""

from __future__ import annotations

import argparse
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd
import requests
from dotenv import load_dotenv


CLOSED_STATUSES = {"Закрыта", "Отказ", "Продажа"}
HIGH_PRIORITY = {"Высокий", "Критичный"}
DATE_COLUMNS = ["created_at", "status_updated_at", "next_action_due_at", "close_due_at"]


@dataclass
class ReportResult:
    report_date: pd.Timestamp
    metrics: dict
    alerts: list[str]
    problem_cases: pd.DataFrame
    by_manager: pd.DataFrame
    trend: pd.DataFrame
    html_path: Path
    png_path: Path
    csv_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CRM-контроль заявок и просрочек")
    parser.add_argument("--data", default="data/crm_requests.csv", help="Путь к CSV с заявками")
    parser.add_argument("--output-dir", default="reports", help="Папка для сохранения отчетов")
    parser.add_argument("--report-date", default=None, help="Дата отчета в формате YYYY-MM-DD")
    parser.add_argument("--stale-days", type=int, default=3, help="Через сколько дней без движения считать заявку зависшей")
    parser.add_argument("--send-telegram", action="store_true", help="Отправить краткий отчет в Telegram")
    parser.add_argument("--send-email", action="store_true", help="Отправить краткий отчет на Email")
    return parser.parse_args()


def load_requests(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    for column in DATE_COLUMNS:
        df[column] = pd.to_datetime(df[column], errors="coerce")

    df["manager"] = df["manager"].fillna("").str.strip()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    return df


def get_report_date(df: pd.DataFrame, report_date: str | None) -> pd.Timestamp:
    if report_date:
        return pd.Timestamp(report_date).normalize()

    # Для демо дата берется из данных, чтобы отчет был воспроизводимым.
    max_date = df["created_at"].max()
    return pd.Timestamp(max_date.date())


def add_flags(df: pd.DataFrame, report_date: pd.Timestamp, stale_days: int) -> pd.DataFrame:
    result = df.copy()
    report_end = report_date + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    result["is_open"] = ~result["status"].isin(CLOSED_STATUSES)
    result["is_new_today"] = result["created_at"].dt.normalize().eq(report_date)
    result["is_overdue_action"] = (
        result["is_open"]
        & result["next_action_due_at"].notna()
        & result["next_action_due_at"].le(report_end)
    )
    result["is_overdue_close"] = (
        result["is_open"]
        & result["close_due_at"].notna()
        & result["close_due_at"].le(report_end)
    )
    result["is_without_manager"] = result["is_open"] & result["manager"].eq("")
    result["is_stale"] = (
        result["is_open"]
        & result["status_updated_at"].notna()
        & result["status_updated_at"].lt(report_date - pd.Timedelta(days=stale_days))
    )
    result["is_hot_overdue"] = result["priority"].isin(HIGH_PRIORITY) & result["is_overdue_action"]

    result["days_without_update"] = (
        report_date - result["status_updated_at"].dt.normalize()
    ).dt.days.clip(lower=0)

    result["risk_score"] = 0
    result.loc[result["is_overdue_action"], "risk_score"] += 3
    result.loc[result["is_overdue_close"], "risk_score"] += 2
    result.loc[result["is_without_manager"], "risk_score"] += 2
    result.loc[result["is_stale"], "risk_score"] += 2
    result.loc[result["priority"].isin(HIGH_PRIORITY), "risk_score"] += 1
    result.loc[result["amount"].ge(150_000), "risk_score"] += 1

    return result


def build_problem_reason(row: pd.Series) -> str:
    reasons: list[str] = []

    if row["is_overdue_action"]:
        reasons.append("просрочено следующее действие")
    if row["is_overdue_close"]:
        reasons.append("просрочен дедлайн закрытия")
    if row["is_without_manager"]:
        reasons.append("нет ответственного")
    if row["is_stale"]:
        reasons.append("статус давно не менялся")
    if row["is_hot_overdue"]:
        reasons.append("высокий приоритет")

    return "; ".join(reasons)


def prepare_problem_cases(df: pd.DataFrame) -> pd.DataFrame:
    problem_mask = (
        df["is_overdue_action"]
        | df["is_overdue_close"]
        | df["is_without_manager"]
        | df["is_stale"]
    )

    problem_cases = df.loc[problem_mask].copy()
    problem_cases["problem"] = problem_cases.apply(build_problem_reason, axis=1)
    problem_cases["manager"] = problem_cases["manager"].replace("", "Не назначен")

    columns = [
        "request_id",
        "client",
        "source",
        "manager",
        "status",
        "priority",
        "amount",
        "next_action_due_at",
        "close_due_at",
        "days_without_update",
        "risk_score",
        "problem",
    ]

    return problem_cases[columns].sort_values(
        ["risk_score", "amount", "next_action_due_at"],
        ascending=[False, False, True],
    )


def calc_metrics(df: pd.DataFrame, problem_cases: pd.DataFrame) -> dict:
    open_df = df[df["is_open"]]
    overdue_df = df[df["is_overdue_action"] | df["is_overdue_close"]]

    return {
        "total_open": int(open_df.shape[0]),
        "new_today": int(df["is_new_today"].sum()),
        "overdue_action": int(df["is_overdue_action"].sum()),
        "overdue_close": int(df["is_overdue_close"].sum()),
        "without_manager": int(df["is_without_manager"].sum()),
        "stale": int(df["is_stale"].sum()),
        "hot_overdue": int(df["is_hot_overdue"].sum()),
        "problem_cases": int(problem_cases.shape[0]),
        "risk_amount": int(overdue_df["amount"].sum()),
    }


def calc_by_manager(df: pd.DataFrame) -> pd.DataFrame:
    prepared = df.copy()
    prepared["manager"] = prepared["manager"].replace("", "Не назначен")

    by_manager = (
        prepared[prepared["is_open"]]
        .groupby("manager", as_index=False)
        .agg(
            open_requests=("request_id", "count"),
            overdue_action=("is_overdue_action", "sum"),
            overdue_close=("is_overdue_close", "sum"),
            stale=("is_stale", "sum"),
            risk_amount=("amount", "sum"),
        )
        .sort_values(["overdue_action", "overdue_close", "risk_amount"], ascending=[False, False, False])
    )

    return by_manager


def calc_trend(df: pd.DataFrame, report_date: pd.Timestamp, days: int = 7) -> pd.DataFrame:
    rows = []

    for offset in range(days - 1, -1, -1):
        current_date = report_date - pd.Timedelta(days=offset)
        current_end = current_date + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        current_open = df["is_open"] & df["created_at"].le(current_end)
        current_overdue = current_open & df["next_action_due_at"].notna() & df["next_action_due_at"].le(current_end)
        rows.append({"date": current_date.date(), "overdue": int(current_overdue.sum())})

    return pd.DataFrame(rows)


def build_alerts(metrics: dict) -> list[str]:
    alerts: list[str] = []

    if metrics["hot_overdue"] > 0:
        alerts.append(f"Высокоприоритетных просрочек: {metrics['hot_overdue']}")
    if metrics["without_manager"] > 0:
        alerts.append(f"Заявок без ответственного: {metrics['without_manager']}")
    if metrics["stale"] > 0:
        alerts.append(f"Зависших заявок без движения: {metrics['stale']}")
    if metrics["risk_amount"] > 0:
        alerts.append(f"Сумма в зоне риска: {format_rub(metrics['risk_amount'])}")

    if not alerts:
        alerts.append("Критичных просрочек не найдено")

    return alerts


def format_rub(value: float | int) -> str:
    return f"{int(value):,}".replace(",", " ") + " ₽"


def format_dt(value: pd.Timestamp | str | None) -> str:
    if pd.isna(value):
        return "—"
    return pd.Timestamp(value).strftime("%d.%m.%Y %H:%M")


def build_html(result: ReportResult) -> str:
    metrics = result.metrics
    alert_items = "".join(f"<li>{alert}</li>" for alert in result.alerts)

    table_rows = ""
    for _, row in result.problem_cases.head(12).iterrows():
        table_rows += f"""
        <tr>
            <td>{row['request_id']}</td>
            <td>{row['client']}</td>
            <td>{row['manager']}</td>
            <td>{row['status']}</td>
            <td>{row['priority']}</td>
            <td>{format_rub(row['amount'])}</td>
            <td>{format_dt(row['next_action_due_at'])}</td>
            <td>{row['problem']}</td>
        </tr>
        """

    manager_rows = ""
    for _, row in result.by_manager.iterrows():
        manager_rows += f"""
        <tr>
            <td>{row['manager']}</td>
            <td>{int(row['open_requests'])}</td>
            <td>{int(row['overdue_action'])}</td>
            <td>{int(row['overdue_close'])}</td>
            <td>{int(row['stale'])}</td>
            <td>{format_rub(row['risk_amount'])}</td>
        </tr>
        """

    return f"""
<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <title>Контроль заявок и просрочек</title>
    <style>
        body {{
            margin: 0;
            padding: 32px;
            background: #f5f7fb;
            color: #111827;
            font-family: Arial, sans-serif;
        }}
        .container {{
            max-width: 1180px;
            margin: 0 auto;
        }}
        .header {{
            margin-bottom: 24px;
        }}
        .subtitle {{
            color: #667085;
            font-size: 16px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin: 24px 0;
        }}
        .card {{
            background: #ffffff;
            border-radius: 18px;
            padding: 20px;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.07);
        }}
        .label {{
            color: #94a3b8;
            font-size: 13px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .04em;
        }}
        .value {{
            font-size: 30px;
            font-weight: 800;
            margin-top: 10px;
        }}
        .danger {{ color: #7c3aed; }}
        .warning {{ color: #ef4444; }}
        .section {{
            background: #ffffff;
            border-radius: 18px;
            padding: 24px;
            margin-top: 20px;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.07);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 14px;
            font-size: 14px;
        }}
        th, td {{
            border-bottom: 1px solid #e5e7eb;
            padding: 12px 10px;
            text-align: left;
            vertical-align: top;
        }}
        th {{
            color: #64748b;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: .04em;
        }}
        ul {{ margin-top: 10px; }}
        li {{ margin-bottom: 8px; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>Контроль заявок и просрочек за {result.report_date.strftime('%d.%m.%Y')}</h1>
        <div class="subtitle">Автоматический мониторинг CRM: новые заявки, просроченные действия, заявки без ответственных и зависшие статусы.</div>
    </div>

    <div class="grid">
        <div class="card"><div class="label">Открытых заявок</div><div class="value">{metrics['total_open']}</div></div>
        <div class="card"><div class="label">Новых сегодня</div><div class="value">{metrics['new_today']}</div></div>
        <div class="card"><div class="label">Просрочено действий</div><div class="value warning">{metrics['overdue_action']}</div></div>
        <div class="card"><div class="label">Сумма в риске</div><div class="value danger">{format_rub(metrics['risk_amount'])}</div></div>
    </div>

    <div class="section">
        <h2>Что требует внимания</h2>
        <ul>{alert_items}</ul>
    </div>

    <div class="section">
        <h2>Проблемные заявки</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th><th>Клиент</th><th>Ответственный</th><th>Статус</th><th>Приоритет</th><th>Сумма</th><th>Следующее действие</th><th>Проблема</th>
                </tr>
            </thead>
            <tbody>{table_rows}</tbody>
        </table>
    </div>

    <div class="section">
        <h2>Нагрузка и просрочки по менеджерам</h2>
        <table>
            <thead>
                <tr>
                    <th>Менеджер</th><th>Открыто</th><th>Просрочено действий</th><th>Просрочено закрытий</th><th>Зависло</th><th>Сумма открытых</th>
                </tr>
            </thead>
            <tbody>{manager_rows}</tbody>
        </table>
    </div>
</div>
</body>
</html>
"""


def save_png(result: ReportResult, png_path: Path) -> None:
    metrics = result.metrics
    trend = result.trend

    fig = plt.figure(figsize=(15, 8.5), dpi=150)
    fig.patch.set_facecolor("#f5f7fb")

    fig.text(0.06, 0.93, "Контроль заявок и просрочек", fontsize=24, fontweight="bold", color="#111827")
    fig.text(0.06, 0.89, f"Отчет за {result.report_date.strftime('%d.%m.%Y')}", fontsize=12, color="#667085")

    cards = [
        ("Открытых заявок", metrics["total_open"]),
        ("Новых сегодня", metrics["new_today"]),
        ("Просрочено действий", metrics["overdue_action"]),
        ("Без ответственного", metrics["without_manager"]),
    ]

    x_positions = [0.06, 0.29, 0.52, 0.75]
    for x, (label, value) in zip(x_positions, cards):
        ax = fig.add_axes([x, 0.72, 0.19, 0.12])
        ax.set_facecolor("white")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.text(0.06, 0.68, label, fontsize=10, color="#64748b", fontweight="bold", transform=ax.transAxes)
        ax.text(0.06, 0.2, str(value), fontsize=22, fontweight="bold", transform=ax.transAxes)

    ax_trend = fig.add_axes([0.06, 0.42, 0.52, 0.22])
    ax_trend.plot(trend["date"].astype(str), trend["overdue"], marker="o", linewidth=2.5)
    ax_trend.set_title("Динамика просрочек за 7 дней", loc="left", fontsize=12, fontweight="bold")
    ax_trend.grid(axis="y", alpha=0.25)
    ax_trend.tick_params(axis="x", rotation=30, labelsize=8)
    ax_trend.tick_params(axis="y", labelsize=8)
    ax_trend.spines["top"].set_visible(False)
    ax_trend.spines["right"].set_visible(False)

    ax_alerts = fig.add_axes([0.63, 0.42, 0.31, 0.22])
    ax_alerts.axis("off")
    ax_alerts.text(0, 1, "Алерты", fontsize=12, fontweight="bold", va="top")
    y = 0.78
    for alert in result.alerts[:5]:
        ax_alerts.text(0, y, f"• {alert}", fontsize=10, va="top", wrap=True)
        y -= 0.16

    ax_table = fig.add_axes([0.06, 0.08, 0.88, 0.25])
    ax_table.axis("off")
    top_cases = result.problem_cases.head(6).copy()
    table_data = []
    for _, row in top_cases.iterrows():
        table_data.append([
            str(row["request_id"]),
            row["client"],
            row["manager"],
            row["priority"],
            format_rub(row["amount"]),
            row["problem"][:38] + ("..." if len(row["problem"]) > 38 else ""),
        ])

    table = ax_table.table(
        cellText=table_data,
        colLabels=["ID", "Клиент", "Ответственный", "Приоритет", "Сумма", "Проблема"],
        loc="upper left",
        cellLoc="left",
        colLoc="left",
        colWidths=[0.08, 0.17, 0.17, 0.11, 0.13, 0.34],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.5)
    table.scale(1, 1.55)

    for (row, _), cell in table.get_celld().items():
        cell.set_edgecolor("#e5e7eb")
        if row == 0:
            cell.set_text_props(weight="bold", color="#475569")

    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png_path, bbox_inches="tight")
    plt.close(fig)


def build_message(result: ReportResult) -> str:
    metrics = result.metrics
    alerts = "\n".join(f"- {alert}" for alert in result.alerts)

    return f"""Контроль заявок и просрочек за {result.report_date.strftime('%d.%m.%Y')}

Открытых заявок: {metrics['total_open']}
Новых сегодня: {metrics['new_today']}
Просрочено действий: {metrics['overdue_action']}
Просрочено закрытий: {metrics['overdue_close']}
Без ответственного: {metrics['without_manager']}
Сумма в зоне риска: {format_rub(metrics['risk_amount'])}

Что проверить:
{alerts}
"""


def send_telegram(message: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram не отправлен: не заполнены TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_ID")
        return

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": message},
        timeout=20,
    )
    response.raise_for_status()


def send_email(message: str, subject: str) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_to = os.getenv("EMAIL_TO")

    if not all([smtp_host, smtp_user, smtp_password, email_to]):
        print("Email не отправлен: не заполнены SMTP_HOST, SMTP_USER, SMTP_PASSWORD и EMAIL_TO")
        return

    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = smtp_user
    email["To"] = email_to
    email.set_content(message)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(email)


def make_report(data_path: str | Path, output_dir: str | Path, report_date: str | None, stale_days: int) -> ReportResult:
    df = load_requests(data_path)
    report_day = get_report_date(df, report_date)
    prepared = add_flags(df, report_day, stale_days)

    problem_cases = prepare_problem_cases(prepared)
    metrics = calc_metrics(prepared, problem_cases)
    by_manager = calc_by_manager(prepared)
    trend = calc_trend(prepared, report_day)
    alerts = build_alerts(metrics)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    date_suffix = report_day.strftime("%Y-%m-%d")
    html_path = output / f"crm_control_report_{date_suffix}.html"
    png_path = output / f"crm_control_report_{date_suffix}.png"
    csv_path = output / f"crm_problem_cases_{date_suffix}.csv"

    result = ReportResult(
        report_date=report_day,
        metrics=metrics,
        alerts=alerts,
        problem_cases=problem_cases,
        by_manager=by_manager,
        trend=trend,
        html_path=html_path,
        png_path=png_path,
        csv_path=csv_path,
    )

    html_path.write_text(build_html(result), encoding="utf-8")
    problem_cases.to_csv(csv_path, index=False, encoding="utf-8-sig")
    save_png(result, png_path)

    return result


def main() -> None:
    load_dotenv()
    args = parse_args()

    result = make_report(
        data_path=args.data,
        output_dir=args.output_dir,
        report_date=args.report_date,
        stale_days=args.stale_days,
    )

    message = build_message(result)
    print(message)
    print(f"HTML-отчет: {result.html_path}")
    print(f"PNG-скрин: {result.png_path}")
    print(f"CSV с проблемными заявками: {result.csv_path}")

    if args.send_telegram:
        send_telegram(message)

    if args.send_email:
        send_email(message, subject="Контроль заявок и просрочек")


if __name__ == "__main__":
    main()
