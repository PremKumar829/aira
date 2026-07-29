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

        # USERS TABLE
        await c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # SETTINGS TABLE
        await c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # FORCE JOIN TABLE
        # Existing table ko delete nahi karega
        await c.execute("""
            CREATE TABLE IF NOT EXISTS force_join (
                chat_id BIGINT PRIMARY KEY,
                title TEXT NOT NULL,
                invite_link TEXT
            )
        """)

        # IMPORTANT:
        # Purane database mein ye column nahi tha.
        # Ye command sirf missing column add karegi.
        # Existing data safe rahega.
        await c.execute("""
            ALTER TABLE force_join
            ADD COLUMN IF NOT EXISTS button_title
            TEXT DEFAULT '🔵 JOIN NOW'
        """)

        # SCHEDULE TABLE
        await c.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                id SERIAL PRIMARY KEY,
                time TEXT NOT NULL,
                message TEXT NOT NULL,
                last_run_date TEXT
            )
        """)

        # Existing rows mein agar button_title NULL ho
        # to default title set kar do.
        await c.execute("""
            UPDATE force_join
            SET button_title = '🔵 JOIN NOW'
            WHERE button_title IS NULL
        """)

    print("✅ Database initialised successfully")
    print("✅ Existing data preserved")
    print("✅ Force join database migration completed")


# =========================
# USER FUNCTIONS
# =========================

async def save_user(uid, username):
    async with _pool.acquire() as c:
        await c.execute("""
            INSERT INTO users (user_id, username)
            VALUES ($1, $2)
            ON CONFLICT (user_id)
            DO UPDATE SET username = EXCLUDED.username
        """, uid, username)


async def get_all_users():
    async with _pool.acquire() as c:
        rows = await c.fetch("""
            SELECT user_id
            FROM users
            ORDER BY created_at ASC
        """)
        return [row["user_id"] for row in rows]


async def get_user_count():
    async with _pool.acquire() as c:
        return await c.fetchval("""
            SELECT COUNT(*)
            FROM users
        """)


# =========================
# SETTINGS FUNCTIONS
# =========================

async def get_settings():
    async with _pool.acquire() as c:
        rows = await c.fetch("""
            SELECT key, value
            FROM settings
        """)

        return {
            row["key"]: row["value"]
            for row in rows
        }


async def update_setting(key, value):
    async with _pool.acquire() as c:
        await c.execute("""
            INSERT INTO settings (key, value)
            VALUES ($1, $2)
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value
        """, key, value)


# =========================
# FORCE JOIN FUNCTIONS
# =========================

async def add_force_join(
    cid,
    title,
    invite_link=None,
    button_title="🔵 JOIN NOW"
):
    async with _pool.acquire() as c:

        await c.execute("""
            INSERT INTO force_join (
                chat_id,
                title,
                invite_link,
                button_title
            )
            VALUES ($1, $2, $3, $4)

            ON CONFLICT (chat_id)
            DO UPDATE SET
                title = EXCLUDED.title,
                invite_link = EXCLUDED.invite_link,
                button_title = EXCLUDED.button_title
        """,
        cid,
        title,
        invite_link,
        button_title
        )


async def remove_force_join(cid):
    async with _pool.acquire() as c:
        await c.execute("""
            DELETE FROM force_join
            WHERE chat_id = $1
        """, cid)


async def set_force_join_title(cid, title):
    async with _pool.acquire() as c:
        await c.execute("""
            UPDATE force_join
            SET button_title = $1
            WHERE chat_id = $2
        """, title, cid)


async def list_force_join():
    async with _pool.acquire() as c:

        rows = await c.fetch("""
            SELECT
                chat_id,
                title,
                invite_link,
                button_title
            FROM force_join
            ORDER BY title ASC
        """)

        return [
            dict(row)
            for row in rows
        ]


# =========================
# SCHEDULE FUNCTIONS
# =========================

async def add_schedule(time_text, message):
    async with _pool.acquire() as c:
        await c.execute("""
            INSERT INTO schedules (
                time,
                message
            )
            VALUES ($1, $2)
        """, time_text, message)


async def get_schedules():
    async with _pool.acquire() as c:

        rows = await c.fetch("""
            SELECT
                id,
                time,
                message,
                last_run_date
            FROM schedules
            ORDER BY id ASC
        """)

        return [
            dict(row)
            for row in rows
        ]


async def mark_schedule_run(
    schedule_id,
    date_text
):
    async with _pool.acquire() as c:

        await c.execute("""
            UPDATE schedules
            SET last_run_date = $1
            WHERE id = $2
        """,
        date_text,
        schedule_id
        )
