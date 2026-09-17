import sqlite3
import logging
from pathlib import Path

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "users.db"


def init_db():
    """Создаёт таблицы, если их нет."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Профиль пользователя
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            weight REAL,
            height REAL,
            age INTEGER,
            gender TEXT,
            activity TEXT,
            daily_calories REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # История приёмов пищи
    cur.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            food_name TEXT,
            weight_grams REAL,
            calories REAL,
            protein REAL,
            fat REAL,
            carbs REAL,
            photo_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    """)

    conn.commit()
    conn.close()
    log.info("БД инициализирована.")


def get_user(user_id: int):
    """Возвращает словарь с данными пользователя или None."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def save_user(user_id: int, username: str = None, **fields):
    """Создаёт или обновляет пользователя. Поля передаются как kwargs."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing = get_user(user_id)

    if existing is None:
        # INSERT
        columns = ["user_id", "username"] + list(fields.keys())
        values = [user_id, username] + list(fields.values())
        placeholders = ",".join(["?"] * len(columns))
        cur.execute(
            f"INSERT INTO users ({','.join(columns)}) VALUES ({placeholders})",
            values,
        )
    else:
        # UPDATE
        if username:
            fields["username"] = username
        if fields:
            set_clause = ", ".join(f"{k} = ?" for k in fields)
            values = list(fields.values()) + [user_id]
            cur.execute(
                f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP "
                f"WHERE user_id = ?",
                values,
            )

    conn.commit()
    conn.close()


def save_meal(user_id: int, food_name: str, weight_grams: float,
              calories: float, protein: float, fat: float, carbs: float,
              photo_path: str = None):
    """Сохраняет приём пищи."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO meals
            (user_id, food_name, weight_grams, calories, protein, fat, carbs, photo_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, food_name, weight_grams, calories, protein, fat, carbs, photo_path))
    conn.commit()
    conn.close()


def get_today_calories(user_id: int) -> float:
    """Сумма калорий за сегодня."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(calories), 0) FROM meals
        WHERE user_id = ? AND DATE(created_at) = DATE('now')
    """, (user_id,))
    total = cur.fetchone()[0]
    conn.close()
    return total