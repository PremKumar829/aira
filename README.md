# Telegram Force Join Bot — Render Web Service

## Render
Build Command:
`pip install -r requirements.txt`

Start Command:
`python bot.py`

Environment Variables:
- `BOT_TOKEN`
- `ADMIN_ID`
- `DATABASE_URL`

This version starts a small HTTP health server on Render's PORT and runs Telegram polling in the same process.

## Database
Create Render Postgres and use its Internal Database URL as `DATABASE_URL` where appropriate.

## Telegram
The bot should be an administrator in required channels/groups for membership checks and invite-link creation.

Never commit `.env` or secrets to GitHub.
