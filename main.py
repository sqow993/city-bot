import os
import logging
from pathlib import Path
from datetime import datetime

import telebot
from dotenv import load_dotenv

from database import init_db, get_user, save_user, save_meal, get_today_calories
from nutrition import calc_daily_calories, calc_nutrition, get_recommendation

# ==== Настройки ====
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
TEMP_DIR = Path(os.getenv("TEMP_DIR", "temp"))
TEMP_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN)

# Храним состояние диалога в памяти (для простоты).
# Для продакшена лучше Redis или FSM из aiogram.
user_states = {}

# ==== Вспомогательное: спросить вес еды ====
def ask_food_weight(chat_id: int, user_id: int):
    user_states[user_id] = "waiting_food_weight"
    bot.send_message(chat_id, "⚖️ Сколько примерно грамм еды на фото? Напиши число (например, 250).")


# ==== Команды ====
@bot.message_handler(commands=["start"])
def cmd_start(message):
    user_id = message.from_user.id
    user = get_user(user_id)

    if user and user.get("daily_calories"):
        bot.reply_to(
            message,
            f"С возвращением! Твоя норма: *{user['daily_calories']} ккал/день*.\n"
            f"Отправь фото еды или напиши /profile, чтобы изменить данные.",
            parse_mode="Markdown"
        )
        return

    # Новый пользователь — начинаем сбор профиля
    user_states[user_id] = "waiting_weight"
    bot.reply_to(
        message,
        "👋 Привет! Я помогу следить за калориями.\n\n"
        "Сначала настроим профиль.\n\n"
        "📏 Какой у тебя *вес* (в кг)? Напиши число.",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["profile"])
def cmd_profile(message):
    user_id = message.from_user.id
    user_states[user_id] = "waiting_weight"
    bot.reply_to(message, "📏 Введи свой *вес* (кг):", parse_mode="Markdown")


# ==== Шаги сбора профиля ====
@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_weight")
def step_weight(message):
    try:
        weight = float(message.text.replace(",", "."))
        if not (20 <= weight <= 400):
            raise ValueError
    except ValueError:
        bot.reply_to(message, "❌ Введи корректный вес числом (например, 75).")
        return

    save_user(message.from_user.id, message.from_user.username, weight=weight)
    user_states[message.from_user.id] = "waiting_height"
    bot.reply_to(message, "📐 Теперь *рост* (в см):", parse_mode="Markdown")


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_height")
def step_height(message):
    try:
        height = float(message.text.replace(",", "."))
        if not (100 <= height <= 250):
            raise ValueError
    except ValueError:
        bot.reply_to(message, "❌ Введи корректный рост числом (например, 180).")
        return

    save_user(message.from_user.id, height=height)
    user_states[message.from_user.id] = "waiting_age"
    bot.reply_to(message, "🎂 Сколько тебе лет?")


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_age")
def step_age(message):
    try:
        age = int(message.text)
        if not (10 <= age <= 120):
            raise ValueError
    except ValueError:
        bot.reply_to(message, "❌ Введи возраст числом.")
        return

    save_user(message.from_user.id, age=age)
    user_states[message.from_user.id] = "waiting_gender"
    bot.reply_to(message, "⚧ Пол: напиши *м* или *ж*.", parse_mode="Markdown")


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_gender")
def step_gender(message):
    g = message.text.strip().lower()
    if g not in ("м", "ж", "m", "f"):
        bot.reply_to(message, "❌ Напиши *м* или *ж*.", parse_mode="Markdown")
        return

    gender = "m" if g in ("м", "m") else "f"
    save_user(message.from_user.id, gender=gender)
    user_states[message.from_user.id] = "waiting_activity"
    bot.reply_to(
        message,
        "🏃 Уровень активности:\n"
        "• *низкий* — сидячая работа\n"
        "• *средний* — тренировки 3-4 раза в неделю\n"
        "• *высокий* — ежедневные тренировки\n\n"
        "Напиши: *низкий*, *средний* или *высокий*.",
        parse_mode="Markdown"
    )


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == "waiting_activity")
def step_activity(message):
    a = message.text.strip().lower()
    mapping = {"низкий": "low", "средний": "medium", "высокий": "high"}
    if a not in mapping:
        bot.reply_to(message, "❌ Выбери: *низкий*, *средний* или *высокий*.", parse_mode="Markdown")
        return

    activity = mapping[a]
    user = get_user(message.from_user.id)
    save_user(message.from_user.id, activity=activity)

    # Считаем норму
    daily = calc_daily_calories(
        weight=user["weight"],
        height=user["height"],
        age=user["age"],
        gender=user["gender"],
        activity=activity,
    )
    save_user(message.from_user.id, daily_calories=daily)

    user_states.pop(message.from_user.id, None)
    bot.reply_to(
        message,
        f"✅ Готово! Твоя дневная норма: *{daily} ккал*.\n\n"
        f"Теперь отправь фото еды, и я посчитаю калории.",
        parse_mode="Markdown"
    )


# ==== Обработка фото ====
@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    user_id = message.from_user.id
    user = get_user(user_id)

    if not user or not user.get("daily_calories"):
        bot.reply_to(message, "Сначала заполни профиль: /start")
        return

    # Скачиваем фото
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded = bot.download_file(file_info.file_path)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    img_path = TEMP_DIR / f"{user_id}_{ts}.jpg"
    with open(img_path, "wb") as f:
        f.write(downloaded)

    # Определяем блюдо по имени файла или спрашиваем пользователя
    # (YOLO здесь не используем — просим подтвердить, что это)
    user_states[user_id] = {
        "state": "waiting_food_name",
        "photo_path": str(img_path),
    }
    bot.reply_to(
        message,
        "🍽 Что это за блюдо? Напиши название (например, *pizza*, *apple*, *chicken*, *rice*, *salad*).",
        parse_mode="Markdown"
    )


@bot.message_handler(func=lambda m: isinstance(user_states.get(m.from_user.id), dict)
                     and user_states[m.from_user.id].get("state") == "waiting_food_name")
def step_food_name(message):
    food = message.text.strip().lower()
    state_data = user_states[message.from_user.id]
    state_data["food"] = food
    state_data["state"] = "waiting_food_weight"
    user_states[message.from_user.id] = state_data

    bot.reply_to(message, "⚖️ Сколько примерно грамм? Напиши число.")


@bot.message_handler(func=lambda m: isinstance(user_states.get(m.from_user.id), dict)
                     and user_states[m.from_user.id].get("state") == "waiting_food_weight")
def step_food_weight(message):
    try:
        weight = float(message.text.replace(",", "."))
    except ValueError:
        bot.reply_to(message, "❌ Введи число.")
        return

    user_id = message.from_user.id
    state_data = user_states[user_id]
    food = state_data["food"]
    photo_path = state_data.get("photo_path")

    # Считаем
    nutr = calc_nutrition(food, weight)
    user = get_user(user_id)
    eaten_today = get_today_calories(user_id)

    # Сохраняем приём
    save_meal(user_id, food, weight,
              nutr["kcal"], nutr["protein"], nutr["fat"], nutr["carbs"],
              photo_path)

    # Рекомендация
    rec = get_recommendation(user["daily_calories"], eaten_today, nutr)

    text = (
        f"🍽 *{food.capitalize()}*, {weight} г\n"
        f"🔥 Калории: *{nutr['kcal']} ккал*\n"
        f"• Белки: {nutr['protein']} г\n"
        f"• Жиры: {nutr['fat']} г\n"
        f"• Углеводы: {nutr['carbs']} г\n\n"
        f"{rec}"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

    # Удаляем временное фото
    if photo_path and Path(photo_path).exists():
        Path(photo_path).unlink()

    user_states.pop(user_id, None)


@bot.message_handler(content_types=["text"])
def fallback(message):
    bot.reply_to(message, "Я понимаю фото еды и команды. Напиши /start для начала.")


# ==== Запуск ====
if __name__ == "__main__":
    init_db()
    log.info("Бот запущен.")
    bot.infinity_polling(timeout=30, long_polling_timeout=30)