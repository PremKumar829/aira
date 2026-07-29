import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
_pool = None

async def init_db():
    global _pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is missing")

    _pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=5,
        command_timeout=30
    )

    async with _pool.acquire() as c:
        await c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS force_join (
            chat_id BIGINT PRIMARY KEY,
            title TEXT NOT NULL,
            invite_link TEXT,
            button_title TEXT DEFAULT '🔵 JOIN NOW'
        );
        CREATE TABLE IF NOT EXISTS schedules (
            id SERIAL PRIMARY KEY,
            time TEXT NOT NULL,
            message TEXT NOT NULL,
            last_run_date TEXT
        );
        """)

async def save_user(uid, username):
    async with _pool.acquire() as c:
        await c.execute("""
        INSERT INTO users(user_id, username)
        VALUES($1, $2)
        ON CONFLICT(user_id)
        DO UPDATE SET username=EXCLUDED.username
        """, uid, username)

async def get_all_users():
    async with _pool.acquire() as c:
        rows = await c.fetch("SELECT user_id FROM users")
        return [r["user_id"] for r in rows]

async def get_user_count():
    async with _pool.acquire() as c:
        return await c.fetchval("SELECT COUNT(*) FROM users")

async def get_settings():
    async with _pool.acquire() as c:
        rows = await c.fetch("SELECT key,value FROM settings")
        return {r["key"]: r["value"] for r in rows}

async def update_setting(key, value):
    async with _pool.acquire() as c:
        await c.execute("""
        INSERT INTO settings(key,value)
        VALUES($1,$2)
        ON CONFLICT(key)
        DO UPDATE SET value=EXCLUDED.value
        """, key, value)

async def add_force_join(cid, title, invite_link=None, button_title="🔵 JOIN NOW"):
    async with _pool.acquire() as c:
        await c.execute("""
        INSERT INTO force_join(chat_id,title,invite_link,button_title)
        VALUES($1,$2,$3,$4)
        ON CONFLICT(chat_id)
        DO UPDATE SET title=EXCLUDED.title,
                      invite_link=EXCLUDED.invite_link,
                      button_title=EXCLUDED.button_title
        """, cid, title, invite_link, button_title)

async def remove_force_join(cid):
    async with _pool.acquire() as c:
        await c.execute("DELETE FROM force_join WHERE chat_id=$1", cid)

async def set_force_join_title(cid, title):
    async with _pool.acquire() as c:
        await c.execute(
            "UPDATE force_join SET button_title=$1 WHERE chat_id=$2",
            title, cid
        )

async def list_force_join():
    async with _pool.acquire() as c:
        rows = await c.fetch("""
        SELECT chat_id,title,invite_link,button_title
        FROM force_join ORDER BY title
        """)
        return [dict(r) for r in rows]

async def add_schedule(time_text, message):
    async with _pool.acquire() as c:
        await c.execute(
            "INSERT INTO schedules(time,message) VALUES($1,$2)",
            time_text, message
        )

async def get_schedules():
    async with _pool.acquire() as c:
        rows = await c.fetch(
            "SELECT id,time,message,last_run_date FROM schedules"
        )
        return [dict(r) for r in rows]

async def mark_schedule_run(sid, date_text):
    async with _pool.acquire() as c:
        await c.execute(
            "UPDATE schedules SET last_run_date=$1 WHERE id=$2",
            date_text, sid
        )
