from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Circle


def setup_ax(ax):
    ax.set_xlim(0, 1448)
    ax.set_ylim(0, 1086)
    ax.axis("off")


def add_card(ax, x, y, w, h, radius=18, face="#FFFFFF", edge="#E4EAF3"):
    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        linewidth=1,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(patch)
    return patch


def add_text(ax, x, y, text, size=18, weight="normal", color="#111827", ha="left"):
    ax.text(x, y, text, fontsize=size, fontweight=weight, color=color, ha=ha, va="top", family="DejaVu Sans")


def draw_kpi(ax, x, y, w, h, title, value, delta, icon_text, accent="#7C3AED", delta_color="#059669"):
    add_card(ax, x, y, w, h)
    ax.add_patch(Circle((x + w - 58, y + h - 58), 28, color="#F1EAFE"))
    add_text(ax, x + w - 72, y + h - 46, icon_text, size=22, weight="bold", color=accent)
    add_text(ax, x + 26, y + h - 34, title, size=14, weight="bold", color="#64748B")
    add_text(ax, x + 26, y + h - 70, value, size=26, weight="bold", color="#0F172A")
    add_text(ax, x + 26, y + 38, delta, size=13, color=delta_color)


def main() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    assets_dir = project_dir / "assets"
    data_dir = project_dir / "data"
    assets_dir.mkdir(exist_ok=True)

    results = pd.read_csv(data_dir / "benchmark_results.csv")
    before = results[results["version"] == "before"].iloc[0]
    after = results[results["version"] == "after"].iloc[0]

    speedup = before["query_time_sec"] / after["query_time_sec"]
    improvement = (1 - after["query_time_sec"] / before["query_time_sec"]) * 100
    rows_drop = (1 - after["rows_read_mln"] / before["rows_read_mln"]) * 100

    fig = plt.figure(figsize=(14.48, 10.86), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    setup_ax(ax)
    fig.patch.set_facecolor("#F8FAFC")
    ax.set_facecolor("#F8FAFC")

    accent = "#7C3AED"

    add_text(ax, 48, 1040, "Оптимизация тяжелого SQL-запроса", size=34, weight="bold", color="#0F172A")
    add_text(ax, 48, 1000, "Анализ плана выполнения, JOIN, фильтров и агрегаций", size=15, color="#64748B")

    add_card(ax, 1040, 1000, 210, 42, radius=10)
    add_text(ax, 1060, 1030, "Июнь 2026", size=14, color="#0F172A")
    add_card(ax, 1270, 1000, 130, 42, radius=10, face=accent, edge=accent)
    add_text(ax, 1292, 1030, "Скачать SQL", size=14, weight="bold", color="#FFFFFF")

    kpi_y = 825
    kpi_w = 250
    gap = 18
    draw_kpi(ax, 48, kpi_y, kpi_w, 140, "Время запроса", f"{after['query_time_sec']:.1f} сек", f"было {before['query_time_sec']:.1f} сек", "SQL", accent)
    draw_kpi(ax, 48 + (kpi_w + gap), kpi_y, kpi_w, 140, "Ускорение", f"{speedup:.1f}×", f"−{improvement:.1f}% времени", "↗", accent)
    draw_kpi(ax, 48 + 2 * (kpi_w + gap), kpi_y, kpi_w, 140, "Прочитано строк", f"{after['rows_read_mln']:.1f} млн", f"−{rows_drop:.1f}% строк", "IO", accent)
    draw_kpi(ax, 48 + 3 * (kpi_w + gap), kpi_y, kpi_w, 140, "JOIN", f"{int(after['joins_count'])}", f"было {int(before['joins_count'])}", "⋈", accent)
    draw_kpi(ax, 48 + 4 * (kpi_w + gap), kpi_y, kpi_w, 140, "Подзапросы", f"{int(after['subqueries_count'])}", f"было {int(before['subqueries_count'])}", "{}", accent)

    chart1 = fig.add_axes([0.055, 0.465, 0.42, 0.275])
    chart1.set_facecolor("#FFFFFF")
    bars = chart1.bar(["До", "После"], [before["query_time_sec"], after["query_time_sec"]])
    chart1.set_title("Время выполнения запроса", fontsize=16, fontweight="bold", loc="left", pad=14)
    chart1.set_ylabel("Секунды", color="#64748B")
    chart1.grid(axis="y", color="#E2E8F0")
    chart1.spines[["top", "right", "left"]].set_visible(False)
    chart1.spines["bottom"].set_color("#CBD5E1")
    chart1.tick_params(axis="x", labelsize=12, colors="#475569")
    chart1.tick_params(axis="y", labelsize=10, colors="#64748B")
    for bar, value in zip(bars, [before["query_time_sec"], after["query_time_sec"]]):
        chart1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8, f"{value:.1f} сек", ha="center", fontsize=11, color="#0F172A")

    chart2 = fig.add_axes([0.54, 0.465, 0.40, 0.275])
    chart2.set_facecolor("#FFFFFF")
    chart2.plot(["До", "После"], [before["rows_read_mln"], after["rows_read_mln"]], marker="o", linewidth=3)
    chart2.set_title("Прочитано строк", fontsize=16, fontweight="bold", loc="left", pad=14)
    chart2.set_ylabel("Млн строк", color="#64748B")
    chart2.grid(axis="y", color="#E2E8F0")
    chart2.spines[["top", "right", "left"]].set_visible(False)
    chart2.spines["bottom"].set_color("#CBD5E1")
    chart2.tick_params(axis="x", labelsize=12, colors="#475569")
    chart2.tick_params(axis="y", labelsize=10, colors="#64748B")
    chart2.text(0, before["rows_read_mln"] + 0.45, f"{before['rows_read_mln']:.1f} млн", ha="center", fontsize=11, color="#0F172A")
    chart2.text(1, after["rows_read_mln"] + 0.45, f"{after['rows_read_mln']:.1f} млн", ha="center", fontsize=11, color="#0F172A")

    table_ax = fig.add_axes([0.055, 0.15, 0.89, 0.25])
    table_ax.axis("off")
    table_ax.set_title("Что изменилось в запросе", fontsize=16, fontweight="bold", loc="left", pad=12)
    rows = [
        ["Фильтр по дате", "toDate(created_at) BETWEEN ...", "created_at >= ... AND created_at < ...", "партиции/индексы работают"],
        ["JOIN", "7 таблиц до фильтрации", "3 нужных JOIN после отбора заказов", "меньше промежуточных строк"],
        ["Агрегация", "после расширения order_items", "сначала order_id, потом справочники", "меньше группировок"],
        ["Подзапросы", "повторяются в SELECT", "CTE с переиспользованием", "запрос читается проще"],
        ["Поля", "SELECT тянет лишнее", "только поля для отчета", "меньше IO"],
    ]
    tbl = table_ax.table(
        cellText=rows,
        colLabels=["Участок", "До", "После", "Эффект"],
        cellLoc="left",
        colLoc="left",
        loc="upper left",
        bbox=[0, 0, 1, 0.92],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1, 1.55)
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor("#E2E8F0")
        if row == 0:
            cell.set_facecolor("#F1F5F9")
            cell.set_text_props(weight="bold", color="#334155")
        else:
            cell.set_facecolor("#FFFFFF")
            cell.set_text_props(color="#0F172A")

    add_text(ax, 48, 92, "Результат: отчет открывается быстрее, запрос стал короче, нагрузка на БД снизилась.", size=14, color="#64748B")
    add_text(ax, 1130, 92, "Обновлено: 25.06.2026 10:00", size=13, color="#64748B")

    fig.savefig(assets_dir / "report_preview.png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    fig2 = plt.figure(figsize=(14.48, 8.2), dpi=100)
    ax2 = fig2.add_axes([0, 0, 1, 1])
    setup_ax(ax2)
    fig2.patch.set_facecolor("#F8FAFC")
    add_text(ax2, 48, 780, "Сравнение старой и оптимизированной логики", size=32, weight="bold", color="#0F172A")
    add_text(ax2, 48, 742, "Ключевые изменения, которые дали ускорение отчета", size=15, color="#64748B")

    before_box = fig2.add_axes([0.055, 0.12, 0.42, 0.58])
    after_box = fig2.add_axes([0.525, 0.12, 0.42, 0.58])
    for box, title, lines in [
        (
            before_box,
            "До",
            [
                "WHERE toDate(created_at) BETWEEN ...",
                "7 JOIN до фильтрации периода",
                "повторные подзапросы в SELECT",
                "агрегация после расширения строк",
                "много лишних полей в промежуточных CTE",
                "38.4 сек выполнения",
            ],
        ),
        (
            after_box,
            "После",
            [
                "WHERE created_at >= ... AND created_at < ...",
                "ранний отбор заказов за период",
                "CTE: params → filtered_orders → order_metrics",
                "агрегация на уровне order_id",
                "только нужные поля для финального отчета",
                "4.8 сек выполнения",
            ],
        ),
    ]:
        box.axis("off")
        box.set_facecolor("#FFFFFF")
        box.text(0.02, 0.96, title, fontsize=22, fontweight="bold", color="#0F172A", va="top")
        y = 0.82
        for line in lines:
            box.text(0.04, y, f"• {line}", fontsize=14, color="#334155", va="top")
            y -= 0.12

    fig2.savefig(assets_dir / "query_comparison.png", bbox_inches="tight", facecolor=fig2.get_facecolor())
    plt.close(fig2)

    print(f"Скрины сохранены в {assets_dir}")


if __name__ == "__main__":
    main()
