# Telegram Force Join Bot - Clean Fixed Version

## Render
Build Command:
pip install -r requirements.txt

Start Command:
python bot.py

Environment Variables:
BOT_TOKEN
ADMIN_ID
DATABASE_URL

## Fixed
- /start now always attempts to send a response even if user DB save fails.
- Database errors are logged instead of silently stopping the welcome flow.
- Single clean handler per admin FSM state.
- Add and remove force-join actions are separated internally.
- Registration link and welcome message can be updated from admin panel.
- Multiple force-join chats supported.
- Manual broadcast and daily UTC scheduled broadcast.
- User statistics.
- Leave reminder using Telegram chat_member updates.
- Render health endpoint at /health.
- PostgreSQL persistence.

## Button styling
Join buttons request Telegram `primary` style and Check Join requests `success` style.
Actual visual rendering depends on Telegram Bot API/client support. Buttons remain functional even when a client does not visually render styles.

## Required permissions
For membership checks and leave updates, make the bot an administrator in the required channels/groups.

## Important
Do not commit .env or real bot credentials to GitHub.
