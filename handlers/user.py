from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import random

from config import CATEGORIES, CHANNEL_ID, STATUSES, ADMIN_IDS
from database import (
    create_request,
    update_request,
    get_request,
    get_user_requests,
    upsert_user,
)
from keyboards import (
    main_menu,
    categories_kb,
    skip_kb,
    confirm_kb,
    admin_kb,
)

router = Router()


class NewRequest(StatesGroup):
    category = State()
    photo = State()
    location = State()
    address = State()
    comment = State()
    confirm = State()


def gen_ticket() -> str:
    return f"T-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    u = message.from_user
    await upsert_user(u.id, u.username or "", u.full_name or "")
    await message.answer(
        "👋 Привет! Я бот городских проблем.\n\n"
        "Помогу отправить жалобу на ямы, мусор, неработающие фонари и т.д.\n"
        "Все заявки фиксируются и передаются в администрацию.\n\n"
        "Выбери действие в меню ниже 👇",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def help_cmd(message: Message):
    u = message.from_user
    await upsert_user(u.id, u.username or "", u.full_name or "")
    await message.answer(
        "Как подать заявку:\n"
        "1. Нажми «📝 Подать заявку»\n"
        "2. Выбери категорию\n"
        "3. Отправь фото проблемы\n"
        "4. Отправь геолокацию или адрес\n"
        "5. Подтверди отправку\n\n"
        "Ты получишь номер заявки и сможешь следить за её статусом в «📂 Мои заявки»."
    )


@router.message(F.text == "📂 Мои заявки")
async def my_requests(message: Message):
    u = message.from_user
    await upsert_user(u.id, u.username or "", u.full_name or "")
    rows = await get_user_requests(u.id)
    if not rows:
        await message.answer("У тебя пока нет заявок.")
        return
    text = "📂 Твои последние заявки:\n\n"
    for r in rows:
        cat = CATEGORIES.get(r["category"], r["category"] or "—")
        st = STATUSES.get(r["status"], r["status"])
        text += (
            f"№{r['ticket']} — {cat}\n"
            f"   Статус: {st}\n"
            f"   {r['address'] or 'без адреса'}\n\n"
        )
    await message.answer(text)


# ---------- Подача заявки ----------

@router.message(F.text == "📝 Подать заявку")
async def new_request(message: Message, state: FSMContext):
    await state.clear()
    u = message.from_user
    await upsert_user(u.id, u.username or "", u.full_name or "")
    await message.answer("Выбери категорию проблемы:", reply_markup=categories_kb())
    await state.set_state(NewRequest.category)


@router.callback_query(NewRequest.category, F.data.startswith("cat:"))
async def pick_category(call: CallbackQuery, state: FSMContext):
    cat = call.data.split(":")[1]
    await state.update_data(category=cat)
    await call.message.edit_text(
        f"Категория: {CATEGORIES.get(cat, cat)}\n\n"
        "📸 Теперь отправь фото проблемы (или нажми «Пропустить»).",
        reply_markup=skip_kb("photo"),
    )
    await state.set_state(NewRequest.photo)
    await call.answer()


@router.message(NewRequest.photo, F.photo)
async def get_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await ask_location(message, state)


@router.callback_query(NewRequest.photo, F.data == "skip:photo")
async def skip_photo(call: CallbackQuery, state: FSMContext):
    await state.update_data(photo_id=None)
    await call.message.edit_text("Фото пропущено.")
    await ask_location(call.message, state)
    await call.answer()


@router.message(NewRequest.photo, F.text == "❌ Отмена")
async def cancel_from_photo(message: Message, state: FSMContext):
    await cancel_flow(message, state)


async def ask_location(message: Message, state: FSMContext):
    await message.answer(
        "📍 Отправь геолокацию (скрепка → Геопозиция) или напиши адрес текстом.\n"
        "Можно пропустить.",
        reply_markup=skip_kb("location"),
    )
    await state.set_state(NewRequest.location)


@router.message(NewRequest.location, F.location)
async def get_location(message: Message, state: FSMContext):
    loc = message.location
    await state.update_data(lat=loc.latitude, lon=loc.longitude)
    await ask_address(message, state)


@router.message(NewRequest.location, F.text)
async def get_address_as_location(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_flow(message, state)
        return
    await state.update_data(address=message.text)
    await ask_comment(message, state)


@router.callback_query(NewRequest.location, F.data == "skip:location")
async def skip_location(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Геолокация пропущена.")
    await ask_address(call.message, state)
    await call.answer()


async def ask_address(message: Message, state: FSMContext):
    await message.answer(
        "🏠 Напиши адрес (улица, дом) или нажми «Пропустить».",
        reply_markup=skip_kb("address"),
    )
    await state.set_state(NewRequest.address)


@router.message(NewRequest.address, F.text)
async def get_address(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_flow(message, state)
        return
    await state.update_data(address=message.text)
    await ask_comment(message, state)


@router.callback_query(NewRequest.address, F.data == "skip:address")
async def skip_address(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("Адрес пропущен.")
    await ask_comment(call.message, state)
    await call.answer()


async def ask_comment(message: Message, state: FSMContext):
    await message.answer(
        "💬 Добавь комментарий (что именно не так) или нажми «Пропустить».",
        reply_markup=skip_kb("comment"),
    )
    await state.set_state(NewRequest.comment)


@router.message(NewRequest.comment, F.text)
async def get_comment(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_flow(message, state)
        return
    await state.update_data(comment=message.text)
    await show_confirm(message, state)


@router.callback_query(NewRequest.comment, F.data == "skip:comment")
async def skip_comment(call: CallbackQuery, state: FSMContext):
    await state.update_data(comment=None)
    await call.message.edit_text("Комментарий пропущен.")
    await show_confirm(call.message, state)
    await call.answer()


async def show_confirm(message: Message, state: FSMContext):
    data = await state.get_data()
    cat = CATEGORIES.get(data.get("category"), "—")
    text = (
        "📋 Проверь заявку:\n\n"
        f"Категория: {cat}\n"
        f"Фото: {'есть' if data.get('photo_id') else 'нет'}\n"
        f"Координаты: {data.get('lat')}, {data.get('lon')}\n"
        f"Адрес: {data.get('address') or '—'}\n"
        f"Комментарий: {data.get('comment') or '—'}\n\n"
        "Отправляем?"
    )
    await message.answer(text, reply_markup=confirm_kb())
    await state.set_state(NewRequest.confirm)


@router.callback_query(NewRequest.confirm, F.data == "confirm:no")
async def cancel_confirm(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Отменено.")
    await call.message.answer("Возврат в меню.", reply_markup=main_menu())
    await call.answer()


@router.callback_query(NewRequest.confirm, F.data == "confirm:yes")
async def confirm_send(call: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await state.clear()

    ticket = gen_ticket()
    user = call.from_user
    username = f"@{user.username}" if user.username else user.full_name

    req_id = await create_request(ticket, user.id, username)
    await update_request(
        req_id,
        category=data.get("category"),
        photo_id=data.get("photo_id"),
        lat=data.get("lat"),
        lon=data.get("lon"),
        address=data.get("address"),
        comment=data.get("comment"),
    )

    # Публикация в канал-витрину
    if CHANNEL_ID:
        try:
            cat_label = CATEGORIES.get(data.get("category"), "—")
            caption = (
                f"🆕 Заявка №{ticket}\n"
                f"Категория: {cat_label}\n"
                f"Адрес: {data.get('address') or '—'}\n"
                f"Комментарий: {data.get('comment') or '—'}\n\n"
                f"Поддержать: /support_{req_id}"
            )
            if data.get("photo_id"):
                msg = await bot.send_photo(CHANNEL_ID, data["photo_id"], caption=caption)
            else:
                msg = await bot.send_message(CHANNEL_ID, caption)
            await update_request(req_id, channel_msg_id=msg.message_id)
        except Exception as e:
            print(f"Ошибка публикации в канал: {e}")

    # Уведомление админам
    admin_text = (
        f"📥 Новая заявка №{ticket}\n"
        f"От: {username} (id {user.id})\n"
        f"Категория: {CATEGORIES.get(data.get('category'), '—')}\n"
        f"Адрес: {data.get('address') or '—'}\n"
        f"Комментарий: {data.get('comment') or '—'}"
    )
    for admin_id in ADMIN_IDS:
        try:
            if data.get("photo_id"):
                await bot.send_photo(
                    admin_id,
                    data["photo_id"],
                    caption=admin_text,
                    reply_markup=admin_kb(req_id),
                )
            else:
                await bot.send_message(
                    admin_id,
                    admin_text,
                    reply_markup=admin_kb(req_id),
                )
        except Exception as e:
            print(f"Не смог уведомить админа {admin_id}: {e}")

    await call.message.edit_text(
        f"✅ Заявка №{ticket} принята!\n"
        "Следи за статусом в разделе «📂 Мои заявки»."
    )
    await call.message.answer("Меню:", reply_markup=main_menu())
    await call.answer()


async def cancel_flow(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_menu())