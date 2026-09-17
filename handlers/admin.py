import asyncio
import os
import tempfile
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, STATUSES, CATEGORIES, CHANNEL_ID
from database import (
    update_request,
    get_request,
    get_stats,
    get_last_requests,
    get_all_users,
    count_users,
    get_requests_for_period,
    get_top_problems,
)
from keyboards import (
    admin_kb,
    admin_menu_kb,
    post_target_kb,
    post_confirm_kb,
)

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class PostFlow(StatesGroup):
    waiting_content = State()
    waiting_target = State()
    waiting_confirm = State()


# ---------- /admin ----------

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Нет доступа.")
        return
    await message.answer(
        "🛠 Админ-панель\nВыбери действие:",
        reply_markup=admin_menu_kb(),
    )


@router.callback_query(F.data == "admin:stats")
async def cb_stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    s = await get_stats()
    total = sum(s.values())
    users = await count_users()
    text = "📊 Статистика:\n\n"
    for k, label in STATUSES.items():
        text += f"{label}: {s.get(k, 0)}\n"
    text += f"\nВсего заявок: {total}\nПользователей: {users}"
    await call.message.answer(text)
    await call.answer()


@router.callback_query(F.data == "admin:last")
async def cb_last(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    rows = await get_last_requests(10)
    if not rows:
        await call.message.answer("Заявок нет.")
        await call.answer()
        return
    text = "🆕 Последние 10 заявок:\n\n"
    for r in rows:
        text += (
            f"№{r['ticket']} — {CATEGORIES.get(r['category'], '—')}\n"
            f"   {r['address'] or 'без адреса'}\n"
            f"   Статус: {STATUSES.get(r['status'], r['status'])}\n\n"
        )
    await call.message.answer(text)
    await call.answer()


@router.callback_query(F.data == "admin:report")
async def cb_report(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    await call.message.answer("⏳ Готовлю PDF-отчёт за 7 дней...")
    await call.answer()
    try:
        path = await asyncio.to_thread(_build_pdf_sync, 7)
        await call.message.answer_document(
            FSInputFile(path, filename=f"report_{datetime.now().strftime('%Y%m%d')}.pdf"),
            caption="📄 Отчёт за последние 7 дней",
        )
        os.remove(path)
    except Exception as e:
        await call.message.answer(f"Ошибка при генерации отчёта: {e}")


# ---------- /report ----------

@router.message(Command("report"))
async def cmd_report(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("⏳ Готовлю PDF-отчёт за 7 дней...")
    try:
        path = await asyncio.to_thread(_build_pdf_sync, 7)
        await message.answer_document(
            FSInputFile(path, filename=f"report_{datetime.now().strftime('%Y%m%d')}.pdf"),
            caption="📄 Отчёт за последние 7 дней",
        )
        os.remove(path)
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


def _build_pdf_sync(days: int) -> str:
    """Синхронная генерация PDF в отдельном потоке."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak,
    )
    from reportlab.lib import colors

    # Собираем данные в отдельном event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        stats = loop.run_until_complete(get_stats())
        users = loop.run_until_complete(count_users())
        top = loop.run_until_complete(get_top_problems(days))
        reqs = loop.run_until_complete(get_requests_for_period(days))
    finally:
        loop.close()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.close()
    path = tmp.name

    doc = SimpleDocTemplate(
        path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Отчёт по городским заявкам",
    )
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=18, spaceAfter=12)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, spaceAfter=8)
    body = styles["BodyText"]

    elements = []
    date_from = (datetime.now() - timedelta(days=days)).strftime("%d.%m.%Y")
    date_to = datetime.now().strftime("%d.%m.%Y")

    elements.append(Paragraph("Отчёт по городским заявкам", h1))
    elements.append(Paragraph(f"Период: {date_from} — {date_to}", body))
    elements.append(Paragraph(
        f"Сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}", body
    ))
    elements.append(Spacer(1, 0.5 * cm))

    total = sum(stats.values())
    elements.append(Paragraph("1. Общая сводка", h2))
    summary = [
        ["Показатель", "Значение"],
        ["Всего заявок за период", str(total)],
        ["Пользователей в боте", str(users)],
    ]
    for k, label in STATUSES.items():
        summary.append([label, str(stats.get(k, 0))])
    elements.append(_table(summary))
    elements.append(Spacer(1, 0.5 * cm))

    elements.append(Paragraph("2. Топ проблем по адресам", h2))
    if top:
        data = [["#", "Адрес", "Категория", "Кол-во"]]
        for i, r in enumerate(top, 1):
            data.append([
                str(i),
                r["address"] or "—",
                CATEGORIES.get(r["category"], r["category"] or "—"),
                str(r["cnt"]),
            ])
        elements.append(_table(data))
    else:
        elements.append(Paragraph("Нет данных.", body))
    elements.append(Spacer(1, 0.5 * cm))

    elements.append(PageBreak())
    elements.append(Paragraph("3. Список заявок за период", h2))
    if reqs:
        data = [["#", "Тикет", "Категория", "Адрес", "Статус", "Дата"]]
        for i, r in enumerate(reqs, 1):
            data.append([
                str(i),
                r["ticket"],
                CATEGORIES.get(r["category"], r["category"] or "—"),
                (r["address"] or "—")[:40],
                STATUSES.get(r["status"], r["status"]),
                (r["created_at"] or "")[:16].replace("T", " "),
            ])
        elements.append(_table(data, small=True))
    else:
        elements.append(Paragraph("Заявок за период нет.", body))

    doc.build(elements)
    return path


def _table(data, small: bool = False):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors

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


# ---------- /post ----------

@router.message(Command("post"))
async def cmd_post(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        "✍️ Отправь текст поста. Можно добавить одно фото (подпись к фото).\n\n"
        "Для отмены — /cancel"
    )
    await state.set_state(PostFlow.waiting_content)


@router.message(Command("cancel"))
async def cancel_flow(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.")


@router.callback_query(F.data == "admin:post")
async def cb_post(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    await state.clear()
    await call.message.answer(
        "✍️ Отправь текст поста. Можно добавить одно фото (подпись к фото).\n\n"
        "Для отмены — /cancel"
    )
    await state.set_state(PostFlow.waiting_content)
    await call.answer()


@router.message(PostFlow.waiting_content, F.photo)
async def post_photo(message: Message, state: FSMContext):
    await state.update_data(
        photo_id=message.photo[-1].file_id,
        text=message.caption or "",
    )
    await ask_target(message, state)


@router.message(PostFlow.waiting_content, F.text)
async def post_text(message: Message, state: FSMContext):
    await state.update_data(photo_id=None, text=message.text)
    await ask_target(message, state)


async def ask_target(message: Message, state: FSMContext):
    await message.answer("Куда публикуем?", reply_markup=post_target_kb())
    await state.set_state(PostFlow.waiting_target)


@router.callback_query(PostFlow.waiting_target, F.data.startswith("post_target:"))
async def pick_target(call: CallbackQuery, state: FSMContext):
    target = call.data.split(":")[1]
    if target == "cancel":
        await state.clear()
        await call.message.edit_text("Отменено.")
        await call.answer()
        return
    await state.update_data(target=target)
    data = await state.get_data()
    preview = (data.get("text") or "")[:400]
    label = "в канал-витрину" if target == "channel" else "всем пользователям"
    await call.message.edit_text(
        f"📋 Превью поста ({label}):\n\n{preview}\n\nПубликуем?",
        reply_markup=post_confirm_kb(),
    )
    await state.set_state(PostFlow.waiting_confirm)
    await call.answer()


@router.callback_query(PostFlow.waiting_confirm, F.data == "post_confirm:no")
async def post_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Отменено.")
    await call.answer()


@router.callback_query(PostFlow.waiting_confirm, F.data == "post_confirm:yes")
async def post_publish(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()
    text = data.get("text", "")
    photo_id = data.get("photo_id")
    target = data.get("target")

    if target == "channel":
        if not CHANNEL_ID:
            await call.message.edit_text("❌ CHANNEL_ID не задан в .env")
            await call.answer()
            return
        try:
            if photo_id:
                await bot.send_photo(CHANNEL_ID, photo_id, caption=text)
            else:
                await bot.send_message(CHANNEL_ID, text)
            await call.message.edit_text("✅ Опубликовано в канал.")
        except Exception as e:
            await call.message.edit_text(f"❌ Ошибка публикации: {e}")

    elif target == "broadcast":
        users = await get_all_users()
        sent, failed = 0, 0
        await call.message.edit_text(f"📣 Рассылаю {len(users)} пользователям...")
        for u in users:
            try:
                if photo_id:
                    await bot.send_photo(u["user_id"], photo_id, caption=text)
                else:
                    await bot.send_message(u["user_id"], text)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1
        await call.message.answer(f"✅ Готово. Отправлено: {sent}, ошибок: {failed}")

    await call.answer()


@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    await call.message.answer(
        "✍️ Отправь текст для рассылки всем пользователям (или /cancel)."
    )
    await state.set_state(PostFlow.waiting_content)
    await state.update_data(force_broadcast=True)
    await call.answer()


# ---------- Смена статуса заявки ----------

@router.callback_query(F.data.startswith("adm:"))
async def change_status(call: CallbackQuery, bot: Bot):
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа", show_alert=True)
        return
    _, status, req_id = call.data.split(":")
    req_id = int(req_id)
    req = await get_request(req_id)
    if not req:
        await call.answer("Заявка не найдена", show_alert=True)
        return

    await update_request(req_id, status=status)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(
        f"Заявка №{req['ticket']} → {STATUSES.get(status, status)}"
    )

    try:
        await bot.send_message(
            req["user_id"],
            f"🔔 Статус заявки №{req['ticket']} изменён:\n"
            f"{STATUSES.get(status, status)}",
        )
    except Exception as e:
        print(f"Не смог уведомить пользователя: {e}")

    await call.answer("Готово")