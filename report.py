from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from datetime import datetime, timedelta
from config import CATEGORIES, STATUSES
from database import get_requests_for_period, get_top_problems, get_stats, count_users


def build_report(path: str, days: int = 7):
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title="Отчёт по городским заявкам"
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, spaceAfter=12)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, spaceAfter=8)
    body = styles["BodyText"]

    elements = []
    date_from = (datetime.now() - timedelta(days=days)).strftime("%d.%m.%Y")
    date_to = datetime.now().strftime("%d.%m.%Y")

    # Титул
    elements.append(Paragraph("Отчёт по городским заявкам", h1))
    elements.append(Paragraph(f"Период: {date_from} — {date_to}", body))
    elements.append(Paragraph(f"Сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}", body))
    elements.append(Spacer(1, 0.5*cm))

    # Сводка
    stats = _get_stats_sync()
    total = sum(stats.values())
    users = _get_users_sync()

    elements.append(Paragraph("1. Общая сводка", h2))
    summary_data = [["Показатель", "Значение"]]
    summary_data.append(["Всего заявок за период", str(total)])
    summary_data.append(["Пользователей в боте", str(users)])
    for key, label in STATUSES.items():
        summary_data.append([label, str(stats.get(key, 0))])
    elements.append(_make_table(summary_data))
    elements.append(Spacer(1, 0.5*cm))

    # Топ проблем
    elements.append(Paragraph("2. Топ проблем по адресам", h2))
    top = _get_top_sync(days)
    if top:
        top_data = [["#", "Адрес", "Категория", "Кол-во"]]
        for i, row in enumerate(top, 1):
            top_data.append([
                str(i),
                row["address"] or "—",
                CATEGORIES.get(row["category"], row["category"] or "—"),
                str(row["cnt"])
            ])
        elements.append(_make_table(top_data))
    else:
        elements.append(Paragraph("Нет данных за период.", body))
    elements.append(Spacer(1, 0.5*cm))

    # Список заявок
    elements.append(PageBreak())
    elements.append(Paragraph("3. Список заявок за период", h2))
    reqs = _get_requests_sync(days)
    if reqs:
        data = [["№", "Тикет", "Категория", "Адрес", "Статус", "Дата"]]
        for i, r in enumerate(reqs, 1):
            data.append([
                str(i),
                r["ticket"],
                CATEGORIES.get(r["category"], r["category"] or "—"),
                (r["address"] or "—")[:40],
                STATUSES.get(r["status"], r["status"]),
                (r["created_at"] or "")[:16].replace("T", " ")
            ])
        elements.append(_make_table(data, small=True))
    else:
        elements.append(Paragraph("Заявок за период нет.", body))

    doc.build(elements)
    return path


def _make_table(data, small=False):
    font_size = 8 if small else 10
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


# Синхронные обёртки — reportlab не любит async
import asyncio
def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if asyncio.get_event_loop().is_running() is False else asyncio.run(coro)

def _get_stats_sync():
    return asyncio.run(get_stats())

def _get_users_sync():
    return asyncio.run(count_users())

def _get_top_sync(days):
    return asyncio.run(get_top_problems(days))

def _get_requests_sync(days):
    return asyncio.run(get_requests_for_period(days))