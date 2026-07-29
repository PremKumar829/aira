# Telegram Force Join Bot

A simple Telegram bot built with Python, aiogram 3, PostgreSQL, GitHub and Render.

## Features

- Welcome message with typing indicator
- Multiple force-join channels/groups
- Join verification before showing registration link
- Admin panel inside Telegram
- Add force-join chats
- Remove force-join chats
- Update registration link without redeploying
- Update welcome message
- Broadcast to saved users
- Persistent PostgreSQL database
- Render worker deployment
- `.env` support for local development

## 1. Create a Telegram Bot

Use @BotFather to create a bot and copy the bot token.

Get your Telegram numeric user ID and use it as `ADMIN_ID`.

## 2. Create PostgreSQL on Render

Create a PostgreSQL database on Render and copy its Internal Database URL (or External URL if required by your setup).

## 3. Local `.env`

Copy `.env.example` to `.env`:

```env
BOT_TOKEN=your_bot_token
ADMIN_ID=your_telegram_id
DATABASE_URL=your_postgresql_url
```

Never commit `.env` to GitHub.

## 4. GitHub

Create a repository and upload all project files.

## 5. Render

Create a new Background Worker from the GitHub repository.

Set:

- Build Command: `pip install -r requirements.txt`
- Start Command: `python bot.py`

Add Environment Variables:

- `BOT_TOKEN`
- `ADMIN_ID`
- `DATABASE_URL`

## 6. Telegram permissions

For membership checks, add the bot as an administrator in the required channels/groups with suitable permissions.

For private chats, the bot needs a usable invite link. Join-request workflows also require appropriate administrator permissions.

## 7. Admin

Open the bot and send:

`/admin`

Only the Telegram ID configured as `ADMIN_ID` can access the admin panel.

## Important

Telegram does not provide a universal way for a bot to silently detect every user leaving every chat. The bot verifies membership when the user starts or presses Check Join. For private groups/channels, make sure the bot has the necessary admin permissions.

## Security

Do not publish `BOT_TOKEN`, `ADMIN_ID`, or database credentials in public GitHub repositories.
