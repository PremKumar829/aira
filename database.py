import os
import asyncpg

DATABASE_URL = os.getenv("DATABASE_URL")
_pool = None

async def init_db():
    global _pool
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing")
    _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with _pool.acquire() as conn:
        await conn.execute("""
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
            invite_link TEXT
        );
        """)

async def save_user(user_id, username):
    async with _pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO users(user_id, username) VALUES($1, $2)
        ON CONFLICT(user_id) DO UPDATE SET username=EXCLUDED.username
        """, user_id, username)

async def get_all_users():
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
        return [r["user_id"] for r in rows]

async def get_settings():
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT key, value FROM settings")
        return {r["key"]: r["value"] for r in rows}

async def update_setting(key, value):
    async with _pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO settings(key, value) VALUES($1, $2)
        ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value
        """, key, value)

async def add_force_join(chat_id, title, invite_link=None):
    async with _pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO force_join(chat_id, title, invite_link)
        VALUES($1, $2, $3)
        ON CONFLICT(chat_id) DO UPDATE SET title=EXCLUDED.title, invite_link=EXCLUDED.invite_link
        """, chat_id, title, invite_link)

async def remove_force_join(chat_id):
    async with _pool.acquire() as conn:
        await conn.execute("DELETE FROM force_join WHERE chat_id=$1", chat_id)

async def list_force_join():
    async with _pool.acquire() as conn:
        rows = await conn.fetch("SELECT chat_id, title, invite_link FROM force_join ORDER BY title")
        return [dict(r) for r in rows]
