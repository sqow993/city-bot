import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0").strip() or 0)

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env")

CATEGORIES = {
    "road": "🛣 Дороги / ямы",
    "garbage": "🗑 Мусор",
    "light": "💡 Освещение",
    "water": "🚰 Вода / канализация",
    "yard": "🏢 Двор / подъезд",
    "other": "❓ Другое",
}

STATUSES = {
    "new": "🆕 Новая",
    "in_work": "🔧 В работе",
    "resolved": "✅ Решена",
    "rejected": "❌ Отклонена",
}