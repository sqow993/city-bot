import aiosqlite
from datetime import datetime, timedelta

DB_PATH = "city_bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket TEXT UNIQUE,
                user_id INTEGER,
                username TEXT,
                category TEXT,
                photo_id TEXT,
                lat REAL,
                lon REAL,
                address TEXT,
                comment TEXT,
                status TEXT DEFAULT 'new',
                channel_msg_id INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                joined_at TEXT,
                last_seen TEXT
            )
        """)
        await db.commit()


# ---------- Пользователи ----------

async def upsert_user(user_id: int, username: str, full_name: str):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, full_name, joined_at, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name,
                last_seen = excluded.last_seen
        """, (user_id, username, full_name, now, now))
        await db.commit()


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT user_id FROM users")
        return await cur.fetchall()


async def count_users() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        row = await cur.fetchone()
        return row[0] if row else 0


# ---------- Заявки ----------

async def create_request(ticket: str, user_id: int, username: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now().isoformat()
        cur = await db.execute("""
            INSERT INTO requests (ticket, user_id, username, status, created_at, updated_at)
            VALUES (?, ?, ?, 'new', ?, ?)
        """, (ticket, user_id, username, now, now))
        await db.commit()
        return cur.lastrowid


async def update_request(req_id: int, **fields):
    if not fields:
        return
    fields["updated_at"] = datetime.now().isoformat()
    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [req_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE requests SET {cols} WHERE id = ?", vals)
        await db.commit()


async def get_request(req_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM requests WHERE id = ?", (req_id,))
        return await cur.fetchone()


async def get_last_request(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT * FROM requests WHERE user_id = ?
            ORDER BY id DESC LIMIT 1
        """, (user_id,))
        return await cur.fetchone()


async def get_user_requests(user_id: int, limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT * FROM requests WHERE user_id = ?
            ORDER BY id DESC LIMIT ?
        """, (user_id, limit))
        return await cur.fetchall()


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT status, COUNT(*) as cnt FROM requests GROUP BY status")
        rows = await cur.fetchall()
        return {r["status"]: r["cnt"] for r in rows}


# ---------- Для отчёта ----------

async def get_requests_for_period(days: int = 7):
    since = (datetime.now() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT * FROM requests
            WHERE created_at >= ?
            ORDER BY created_at DESC
        """, (since,))
        return await cur.fetchall()


async def get_top_problems(days: int = 7, limit: int = 5):
    since = (datetime.now() - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT address, category, COUNT(*) as cnt
            FROM requests
            WHERE created_at >= ? AND address IS NOT NULL AND address != ''
            GROUP BY address, category
            ORDER BY cnt DESC
            LIMIT ?
        """, (since, limit))
        return await cur.fetchall()


async def get_last_requests(limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("""
            SELECT * FROM requests ORDER BY id DESC LIMIT ?
        """, (limit,))
        return await cur.fetchall()