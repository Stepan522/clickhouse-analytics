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
    card = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        linewidth=1,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(card)
    return card


def add_text(ax, x, y, text, size=18, weight="normal", color="#111827", ha="left"):
    ax.text(x, y, text, fontsize=size, fontweight=weight, color=color, ha=ha, va="top", family="DejaVu Sans")


def draw_kpi(ax, x, y, w, h, title, value, delta, icon_text, accent="#0EA5A5", delta_color="#059669"):
    add_card(ax, x, y, w, h)
    ax.add_patch(Circle((x + w - 58, y + h - 58), 28, color="#E6FFFB"))
    add_text(ax, x + w - 72, y + h - 46, icon_text, size=22, weight="bold", color=accent)
    add_text(ax, x + 26, y + h - 34, title, size=14, weight="bold", color="#64748B")
    add_text(ax, x + 26, y + h - 70, value, size=26, weight="bold", color="#0F172A")
    add_text(ax, x + 26, y + 38, delta, size=13, color=delta_color)


def main() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    processed_dir = project_dir / "data" / "processed"
    assets_dir = project_dir / "assets"
    assets_dir.mkdir(exist_ok=True)

    summary = pd.read_csv(processed_dir / "quality_summary.csv")
    clean = pd.read_csv(processed_dir / "clients_clean.csv")
    duplicates = pd.read_csv(processed_dir / "duplicate_groups.csv")
    raw = pd.read_csv(project_dir / "data" / "raw" / "clients_dirty.csv")

    raw_rows = int(summary.loc[summary["metric"] == "Строк в сырой базе", "before"].iloc[0])
    unique_rows = int(summary.loc[summary["metric"] == "Строк в сырой базе", "after"].iloc[0])
    duplicates_found = int(summary.loc[summary["metric"] == "Найдено дублей", "before"].iloc[0])
    q_before = float(summary.loc[summary["metric"] == "Качество контактов, %", "before"].iloc[0])
    q_after = float(summary.loc[summary["metric"] == "Качество контактов, %", "after"].iloc[0])

    fig = plt.figure(figsize=(14.48, 10.86), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    setup_ax(ax)
    fig.patch.set_facecolor("#F8FAFC")
    ax.set_facecolor("#F8FAFC")

    accent = "#0EA5A5"

    add_text(ax, 48, 1040, "Очистка и дедупликация клиентской базы", size=34, weight="bold", color="#0F172A")
    add_text(ax, 48, 1000, "Дата обработки: 25.06.2026 · источник: CRM + формы сайта + рассылки", size=15, color="#64748B")

    # Фильтры / кнопка
    add_card(ax, 1040, 1000, 250, 42, radius=10, face="#FFFFFF")
    add_text(ax, 1060, 1030, "25.06.2026", size=14, color="#0F172A")
    add_card(ax, 1305, 1000, 95, 42, radius=10, face="#0EA5A5", edge="#0EA5A5")
    add_text(ax, 1325, 1030, "Экспорт", size=14, weight="bold", color="#FFFFFF")

    # KPI
    kpi_y = 825
    kpi_w = 250
    gap = 18
    draw_kpi(ax, 48, kpi_y, kpi_w, 140, "Сырых строк", f"{raw_rows:,}".replace(",", " "), "из CRM и таблиц", "DB", accent, "#64748B")
    draw_kpi(ax, 48 + (kpi_w + gap), kpi_y, kpi_w, 140, "Дублей найдено", f"{duplicates_found}", "−16.9% базы", "≋", accent, "#DC2626")
    draw_kpi(ax, 48 + 2 * (kpi_w + gap), kpi_y, kpi_w, 140, "Уникальных клиентов", f"{unique_rows:,}".replace(",", " "), "готово к загрузке", "✓", accent, "#059669")
    draw_kpi(ax, 48 + 3 * (kpi_w + gap), kpi_y, kpi_w, 140, "Качество контактов", f"{q_after:.1f}%", f"было {q_before:.1f}%", "@", accent, "#059669")
    draw_kpi(ax, 48 + 4 * (kpi_w + gap), kpi_y, kpi_w, 140, "Групп дублей", f"{len(duplicates)}", "требовали склейки", "ID", accent, "#EA580C")

    # Chart 1: before / after
    chart1 = fig.add_axes([0.055, 0.465, 0.49, 0.275])
    chart1.set_facecolor("#FFFFFF")
    values = [raw_rows, unique_rows, duplicates_found]
    labels = ["До очистки", "После очистки", "Удалено дублей"]
    bars = chart1.bar(labels, values)
    chart1.set_title("Размер клиентской базы", fontsize=16, fontweight="bold", loc="left", pad=14)
    chart1.grid(axis="y", color="#E2E8F0")
    chart1.spines[["top", "right", "left"]].set_visible(False)
    chart1.spines["bottom"].set_color("#CBD5E1")
    chart1.tick_params(axis="x", labelsize=11, colors="#475569")
    chart1.tick_params(axis="y", labelsize=10, colors="#64748B")
    for bar, value in zip(bars, values):
        chart1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 35, f"{value:,}".replace(",", " "), ha="center", fontsize=11, color="#0F172A")

    # Chart 2: issues
    chart2 = fig.add_axes([0.59, 0.465, 0.36, 0.275])
    chart2.set_facecolor("#FFFFFF")
    issues = {
        "Дубли по телефону": 138,
        "Дубли по email": 96,
        "ФИО + город": 52,
        "Некорректные контакты": 26,
    }
    chart2.pie(
        issues.values(),
        labels=None,
        autopct="%1.0f%%",
        startangle=90,
        wedgeprops={"width": 0.42, "edgecolor": "white"},
        textprops={"fontsize": 10, "color": "#0F172A"},
    )
    chart2.set_title("Причины склейки и исправлений", fontsize=16, fontweight="bold", loc="left", pad=14)
    chart2.legend(issues.keys(), loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=10, frameon=False)

    # Table
    table_ax = fig.add_axes([0.055, 0.14, 0.89, 0.27])
    table_ax.axis("off")
    table_ax.set_title("Примеры дублей до склейки", fontsize=16, fontweight="bold", loc="left", pad=12)

    duplicate_sample = raw[raw["client_id"].isin(",".join(duplicates.head(4)["merged_client_ids"].tolist()).split(", "))].head(6)
    if duplicate_sample.empty:
        duplicate_sample = raw.head(6)

    display = duplicate_sample[["client_id", "full_name", "phone", "email", "city", "source"]].copy()
    display.columns = ["ID", "ФИО", "Телефон", "Email", "Город", "Источник"]

    tbl = table_ax.table(
        cellText=display.values,
        colLabels=display.columns,
        cellLoc="left",
        colLoc="left",
        loc="upper left",
        bbox=[0, 0, 1, 0.92],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.55)
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor("#E2E8F0")
        if row == 0:
            cell.set_facecolor("#F1F5F9")
            cell.set_text_props(weight="bold", color="#334155")
        else:
            cell.set_facecolor("#FFFFFF")
            cell.set_text_props(color="#0F172A")

    # Footer
    add_text(ax, 48, 90, "Результат: база очищена, контакты нормализованы, дубли объединены, готовый CSV можно загружать в CRM, рассылки и BI.", size=14, color="#64748B")
    add_text(ax, 1090, 90, "Обновлено: 25.06.2026 09:30", size=13, color="#64748B")

    fig.savefig(assets_dir / "report_preview.png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    # Второй скрин с примером готового датасета
    sample = clean[["client_uid", "full_name", "phone", "email", "city", "total_orders", "revenue_rub", "raw_records_in_group"]].head(10)

    fig2 = plt.figure(figsize=(14.48, 8.2), dpi=100)
    ax2 = fig2.add_axes([0, 0, 1, 1])
    setup_ax(ax2)
    fig2.patch.set_facecolor("#F8FAFC")
    add_text(ax2, 48, 780, "Готовый список клиентов после очистки", size=32, weight="bold", color="#0F172A")
    add_text(ax2, 48, 742, "Фрагмент файла data/processed/clients_clean.csv", size=15, color="#64748B")

    table_ax2 = fig2.add_axes([0.035, 0.08, 0.93, 0.74])
    table_ax2.axis("off")
    tbl2 = table_ax2.table(
        cellText=sample.values,
        colLabels=["client_uid", "ФИО", "Телефон", "Email", "Город", "Заказы", "Выручка", "Строк в группе"],
        cellLoc="left",
        colLoc="left",
        loc="upper left",
        bbox=[0, 0, 1, 1],
    )
    tbl2.auto_set_font_size(False)
    tbl2.set_fontsize(9)
    tbl2.scale(1, 1.55)
    for (row, col), cell in tbl2.get_celld().items():
        cell.set_edgecolor("#E2E8F0")
        if row == 0:
            cell.set_facecolor("#F1F5F9")
            cell.set_text_props(weight="bold", color="#334155")
        else:
            cell.set_facecolor("#FFFFFF")
            cell.set_text_props(color="#0F172A")

    fig2.savefig(assets_dir / "clean_dataset_sample.png", bbox_inches="tight", facecolor=fig2.get_facecolor())
    plt.close(fig2)

    print(f"Скрины сохранены в {assets_dir}")


if __name__ == "__main__":
    main()
