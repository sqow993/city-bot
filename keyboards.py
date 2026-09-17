from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from config import CATEGORIES, STATUSES


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Подать заявку")],
            [KeyboardButton(text="📂 Мои заявки"), KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def categories_kb() -> InlineKeyboardMarkup:
    buttons = []
    for key, label in CATEGORIES.items():
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"cat:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def skip_kb(step: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data=f"skip:{step}")]
    ])


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="confirm:yes")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="confirm:no")],
    ])


def admin_kb(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔧 В работу", callback_data=f"adm:in_work:{req_id}"),
            InlineKeyboardButton(text="✅ Решено", callback_data=f"adm:resolved:{req_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"adm:rejected:{req_id}"),
        ],
    ])


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )


# ---------- Админ-панель ----------

def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
        [InlineKeyboardButton(text="📄 PDF-отчёт за 7 дней", callback_data="admin:report")],
        [InlineKeyboardButton(text="🆕 Последние 10 заявок", callback_data="admin:last")],
        [InlineKeyboardButton(text="✍️ Создать пост", callback_data="admin:post")],
        [InlineKeyboardButton(text="📣 Рассылка пользователям", callback_data="admin:broadcast")],
    ])


def post_target_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 В канал-витрину", callback_data="post_target:channel")],
        [InlineKeyboardButton(text="👥 Всем пользователям бота", callback_data="post_target:broadcast")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="post_target:cancel")],
    ])


def post_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data="post_confirm:yes")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="post_confirm:no")],
    ])