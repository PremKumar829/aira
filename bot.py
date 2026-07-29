import asyncio
import logging
import os
from datetime import datetime, timezone

import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ChatMemberUpdated,
    ChatJoinRequest,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from database import (
    init_db,
    save_user,
    get_settings,
    update_setting,
    get_all_users,
    get_user_count,
    list_force_join,
    add_force_join,
    remove_force_join,
    set_force_join_title,
    add_schedule,
    get_schedules,
    mark_schedule_run,
)

from keyboards import (
    force_join_keyboard,
    admin_keyboard,
)


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    ""
).strip()

ADMIN_ID = int(
    os.getenv(
        "ADMIN_ID",
        "0"
    ).strip() or "0"
)

# Conversion Tracking API Key
CONVERSION_API_KEY = os.getenv(
    "CONVERSION_API_KEY",
    ""
).strip()

# Conversion Tracking API URL
CONVERSION_URL = os.getenv(
    "CONVERSION_URL",
    "https://ad-veba.onrender.com/api/conversion"
).strip()


# =========================================================
# BASIC VALIDATION
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN environment variable is missing"
    )

if not ADMIN_ID:
    raise RuntimeError(
        "ADMIN_ID environment variable is missing"
    )


# =========================================================
# TELEGRAM BOT
# =========================================================

bot = Bot(
    BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher(
    storage=MemoryStorage()
)


# =========================================================
# ADMIN STATES
# =========================================================

class AdminState(StatesGroup):

    registration = State()

    welcome = State()

    broadcast = State()

    chat = State()

    title = State()

    schedule = State()


# =========================================================
# ADMIN CHECK
# =========================================================

async def is_admin(uid: int) -> bool:

    return uid == ADMIN_ID


# =========================================================
# CONVERSION TRACKING
# =========================================================

async def report_conversion(
    token: str
):

    if not token:
        return

    if not CONVERSION_API_KEY:

        logging.warning(
            "CONVERSION_API_KEY is not configured"
        )

        return

    try:

        async with aiohttp.ClientSession() as session:

            async with session.post(

                CONVERSION_URL,

                headers={
                    "X-API-Key": CONVERSION_API_KEY
                },

                json={
                    "token": token
                },

                timeout=aiohttp.ClientTimeout(
                    total=10
                )

            ) as response:

                response_body = await response.text()

                if 200 <= response.status < 300:

                    logging.info(
                        "Conversion reported successfully: %s",
                        response.status
                    )

                else:

                    logging.error(
                        "Conversion API failed: %s - %s",
                        response.status,
                        response_body
                    )

    except asyncio.TimeoutError:

        logging.error(
            "Conversion API request timed out"
        )

    except Exception:

        logging.exception(
            "Conversion API request failed"
        )


# =========================================================
# SAVE USER SAFELY
# =========================================================

async def safe_save_user(
    message: Message
):

    try:

        await save_user(

            message.from_user.id,

            message.from_user.username or ""

        )

    except Exception:

        logging.exception(

            "Could not save user; "
            "continuing bot flow"

        )


# =========================================================
# CHECK MEMBERSHIP
# =========================================================

async def is_member(
    chat_id: int,
    user_id: int
) -> bool:

    try:

        member = await bot.get_chat_member(

            chat_id,

            user_id

        )

        return member.status in {

            ChatMemberStatus.MEMBER,

            ChatMemberStatus.ADMINISTRATOR,

            ChatMemberStatus.CREATOR,

        }

    except Exception:

        logging.exception(

            "Membership check failed "
            "for chat=%s user=%s",

            chat_id,

            user_id

        )

        return False


# =========================================================
# CHECK ALL FORCE JOIN
# =========================================================

async def all_required_joined(
    user_id: int
) -> bool:

    chats = await list_force_join()

    # If no force join chats exist,
    # consider user verified.
    if not chats:

        return True

    for chat in chats:

        if not await is_member(

            chat["chat_id"],

            user_id

        ):

            return False

    return True


# =========================================================
# WELCOME MESSAGE
# =========================================================

async def send_welcome(
    message: Message
):

    settings = await get_settings()

    welcome = settings.get(

        "welcome_message",

        "🎉 <b>WELCOME BONUS ₹1080</b>\n\n"
        "Welcome! Complete the required "
        "steps below to continue."

    )

    await message.answer(

        f"{welcome}\n\n"

        "🔒 <b>Step 1:</b> "
        "Join all required channels/groups.\n\n"

        "After joining, press "
        "🟢 <b>CHECK JOIN</b>.",

        reply_markup=await force_join_keyboard()

    )


# =========================================================
# START COMMAND
# =========================================================

@dp.message(CommandStart())
async def start(
    message: Message
):

    # Show typing indicator
    try:

        await bot.send_chat_action(

            message.chat.id,

            "typing"

        )

    except Exception:

        pass


    # -----------------------------------------------------
    # GET DEEP LINK TOKEN
    # -----------------------------------------------------

    token = None

    if message.text:

        parts = message.text.split(

            maxsplit=1

        )

        if len(parts) > 1:

            token = parts[1].strip()


    # -----------------------------------------------------
    # REPORT CONVERSION
    # -----------------------------------------------------

    if token:

        asyncio.create_task(

            report_conversion(

                token

            )

        )


    # -----------------------------------------------------
    # SAVE USER
    # -----------------------------------------------------

    await safe_save_user(

        message

    )


    # -----------------------------------------------------
    # MAIN FLOW
    # -----------------------------------------------------

    try:

        # Check Force Join

        if not await all_required_joined(

            message.from_user.id

        ):

            await send_welcome(

                message

            )

            return


        # Get settings

        settings = await get_settings()


        welcome = settings.get(

            "welcome_message",

            "🎉 <b>WELCOME BONUS ₹1080</b>"

        )


        link = settings.get(

            "registration_link"

        )


        # -------------------------------------------------
        # USER VERIFIED
        # -------------------------------------------------

        if link:

            await message.answer(

                f"{welcome}\n\n"

                "✅ <b>All required joins "
                "verified!</b>\n\n"

                f"🔗 <b>Registration Link:</b>\n"

                f"{link}\n\n"

                "📝 Register using the link above."

            )

        else:

            await message.answer(

                f"{welcome}\n\n"

                "⚠️ Registration link is "
                "not configured yet."

            )


    except Exception:

        logging.exception(

            "START HANDLER FAILED"

        )

        # Fallback message

        try:

            await message.answer(

                "🎉 <b>WELCOME BONUS ₹1080</b>\n\n"

                "⚠️ Temporary server issue. "
                "Please press /start again."

            )

        except Exception:

            logging.exception(

                "Could not send fallback message"

            )


# =========================================================
# CHECK JOIN BUTTON
# =========================================================

@dp.callback_query(
    F.data == "check_join"
)
async def check_join(
    callback: CallbackQuery
):

    await callback.answer(

        "Checking…"

    )

    try:

        joined = await all_required_joined(

            callback.from_user.id

        )


        if not joined:

            await callback.message.answer(

                "❌ <b>Not completed yet.</b>\n\n"

                "Please join all required "
                "channels/groups first.",

                reply_markup=await force_join_keyboard()

            )

            return


        settings = await get_settings()


        link = settings.get(

            "registration_link"

        )


        text = (

            "🎉 <b>VERIFICATION SUCCESSFUL!</b>\n\n"

            "🎁 <b>WELCOME BONUS ₹1080</b>\n\n"

        )


        if link:

            text += (

                "🔗 <b>Registration Link:</b>\n"

                f"{link}\n\n"

                "📝 Register using the link above."

            )

        else:

            text += (

                "⚠️ Registration link is "
                "not configured yet."

            )


        await callback.message.edit_text(

            text

        )


    except Exception:

        logging.exception(

            "CHECK JOIN FAILED"

        )

        await callback.message.answer(

            "⚠️ Something went wrong. "
            "Please try again."

        )


# =========================================================
# NO LINK CALLBACK
# =========================================================

@dp.callback_query(
    F.data == "no_link"
)
async def no_link(
    callback: CallbackQuery
):

    await callback.answer(

        "Join link is not configured "
        "by admin.",

        show_alert=True

    )


# =========================================================
# JOIN REQUEST
# =========================================================

@dp.chat_join_request()
async def join_request(
    request: ChatJoinRequest
):

    logging.info(

        "Join request received "
        "user=%s chat=%s",

        request.from_user.id,

        request.chat.id

    )


# =========================================================
# MEMBER UPDATE
# =========================================================

@dp.chat_member()
async def member_update(
    event: ChatMemberUpdated
):

    try:

        old = event.old_chat_member.status

        new = event.new_chat_member.status


        left = {

            ChatMemberStatus.LEFT,

            ChatMemberStatus.KICKED

        }


        # User left required chat

        if (

            old not in left

            and new in left

        ):

            uid = event.from_user.id


            if uid != ADMIN_ID:

                await bot.send_message(

                    uid,

                    "⚠️ <b>You left a required "
                    "channel/group.</b>\n\n"

                    "Please join again and press "
                    "🟢 <b>CHECK JOIN</b>.",

                    reply_markup=await force_join_keyboard()

                )


    except Exception:

        logging.exception(

            "MEMBER UPDATE FAILED"

        )


# =========================================================
# ADMIN COMMAND
# =========================================================

@dp.message(
    Command("admin")
)
async def admin(
    message: Message
):

    if await is_admin(

        message.from_user.id

    ):

        await message.answer(

            "🔐 <b>Admin Panel</b>",

            reply_markup=admin_keyboard()

        )


# =========================================================
# FORCE JOIN PANEL
# =========================================================

@dp.callback_query(
    F.data == "admin_forcejoin"
)
async def forcejoin_panel(
    callback: CallbackQuery
):

    if not await is_admin(

        callback.from_user.id

    ):

        return


    chats = await list_force_join()


    text = (

        "📋 <b>Force Join Chats</b>\n\n"

    )


    if chats:

        text += "\n".join(

            f"• {c['title']} — "
            f"<code>{c['chat_id']}</code>"

            for c in chats

        )

    else:

        text += (

            "No chats configured."

        )


    kb = InlineKeyboardMarkup(

        inline_keyboard=[

            [

                InlineKeyboardButton(

                    text="➕ Add Chat",

                    callback_data="add_chat"

                )

            ],

            [

                InlineKeyboardButton(

                    text="🗑️ Remove Chat",

                    callback_data="remove_chat"

                )

            ],

            [

                InlineKeyboardButton(

                    text="🏷️ Change Button Title",

                    callback_data="join_title"

                )

            ],

            [

                InlineKeyboardButton(

                    text="🔙 Back",

                    callback_data="admin_back"

                )

            ],

        ]

    )


    await callback.message.edit_text(

        text,

        reply_markup=kb

    )


# =========================================================
# ADD / REMOVE CHAT
# =========================================================

@dp.callback_query(
    F.data.in_({

        "add_chat",

        "remove_chat"

    })
)
async def chat_prompt(

    callback: CallbackQuery,

    state: FSMContext

):

    if not await is_admin(

        callback.from_user.id

    ):

        return


    action = (

        "add"

        if callback.data == "add_chat"

        else "remove"

    )


    await state.update_data(

        action=action

    )


    await state.set_state(

        AdminState.chat

    )


    await callback.message.answer(

        "Send chat ID.\n\n"

        "Example:\n"

        "<code>-1001234567890</code>"

    )


# =========================================================
# CHAT RECEIVED
# =========================================================

@dp.message(
    AdminState.chat
)
async def chat_received(

    message: Message,

    state: FSMContext

):

    if not await is_admin(

        message.from_user.id

    ):

        return


    try:

        cid = int(

            message.text.strip()

        )


        data = await state.get_data()


        action = data.get(

            "action"

        )


        # REMOVE CHAT

        if action == "remove":

            await remove_force_join(

                cid

            )


            await state.clear()


            await message.answer(

                "🗑️ Chat removed.",

                reply_markup=admin_keyboard()

            )


            return


        # ADD CHAT

        chat = await bot.get_chat(

            cid

        )


        invite = None


        try:

            invite = (

                await bot.create_chat_invite_link(

                    cid,

                    name="Force Join"

                )

            )

        except Exception:

            logging.exception(

                "Could not create invite link"

            )


        await add_force_join(

            cid,

            chat.title or str(cid),

            invite.invite_link

            if invite

            else None,

            "🔵 JOIN NOW"

        )


        await state.clear()


        await message.answer(

            f"✅ <b>{chat.title}</b> added.",

            reply_markup=admin_keyboard()

        )


    except Exception:

        logging.exception(

            "CHAT ADD/REMOVE FAILED"

        )


        await message.answer(

            "❌ Failed.\n\n"

            "Check chat ID and make sure "
            "bot is admin in that chat."

        )


# =========================================================
# CHANGE BUTTON TITLE
# =========================================================

@dp.callback_query(
    F.data == "join_title"
)
async def title_prompt(

    callback: CallbackQuery,

    state: FSMContext

):

    if await is_admin(

        callback.from_user.id

    ):

        await state.set_state(

            AdminState.title

        )


        await callback.message.answer(

            "Send:\n\n"

            "<code>CHAT_ID | BUTTON TITLE</code>"

        )


# =========================================================
# TITLE RECEIVED
# =========================================================

@dp.message(
    AdminState.title
)
async def title_received(

    message: Message,

    state: FSMContext

):

    if not await is_admin(

        message.from_user.id

    ):

        return


    try:

        cid, title = (

            message.text.split(

                "|",

                1

            )

        )


        await set_force_join_title(

            int(

                cid.strip()

            ),

            title.strip()

        )


        await state.clear()


        await message.answer(

            "✅ Button title updated.",

            reply_markup=admin_keyboard()

        )


    except Exception:

        await message.answer(

            "❌ Format:\n\n"

            "CHAT_ID | BUTTON TITLE"

        )


# =========================================================
# REGISTRATION LINK
# =========================================================

@dp.callback_query(
    F.data == "registration"
)
async def registration_prompt(

    callback: CallbackQuery,

    state: FSMContext

):

    if await is_admin(

        callback.from_user.id

    ):

        await state.set_state(

            AdminState.registration

        )


        await callback.message.answer(

            "Send the new registration link."

        )


# =========================================================
# REGISTRATION RECEIVED
# =========================================================

@dp.message(
    AdminState.registration
)
async def registration_received(

    message: Message,

    state: FSMContext

):

    if not await is_admin(

        message.from_user.id

    ):

        return


    await update_setting(

        "registration_link",

        message.text.strip()

    )


    await state.clear()


    await message.answer(

        "✅ Registration link updated.",

        reply_markup=admin_keyboard()

    )


# =========================================================
# WELCOME MESSAGE
# =========================================================

@dp.callback_query(
    F.data == "welcome"
)
async def welcome_prompt(

    callback: CallbackQuery,

    state: FSMContext

):

    if await is_admin(

        callback.from_user.id

    ):

        await state.set_state(

            AdminState.welcome

        )


        await callback.message.answer(

            "Send the new welcome message."

        )


# =========================================================
# WELCOME RECEIVED
# =========================================================

@dp.message(
    AdminState.welcome
)
async def welcome_received(

    message: Message,

    state: FSMContext

):

    if not await is_admin(

        message.from_user.id

    ):

        return


    await update_setting(

        "welcome_message",

        message.text

    )


    await state.clear()


    await message.answer(

        "✅ Welcome message updated.",

        reply_markup=admin_keyboard()

    )


# =========================================================
# BROADCAST PROMPT
# =========================================================

@dp.callback_query(
    F.data == "broadcast"
)
async def broadcast_prompt(

    callback: CallbackQuery,

    state: FSMContext

):

    if await is_admin(

        callback.from_user.id

    ):

        await state.set_state(

            AdminState.broadcast

        )


        await callback.message.answer(

            "Send the broadcast message."

        )


# =========================================================
# BROADCAST
# =========================================================

@dp.message(
    AdminState.broadcast
)
async def broadcast_received(

    message: Message,

    state: FSMContext

):

    if not await is_admin(

        message.from_user.id

    ):

        return


    sent = 0

    failed = 0


    for uid in await get_all_users():

        try:

            await bot.copy_message(

                uid,

                message.chat.id,

                message.message_id

            )


            sent += 1


        except Exception:

            failed += 1


    await state.clear()


    await message.answer(

        f"📢 <b>Broadcast complete</b>\n\n"

        f"✅ Sent: {sent}\n"

        f"❌ Failed: {failed}"

    )


# =========================================================
# SCHEDULE PROMPT
# =========================================================

@dp.callback_query(
    F.data == "schedule"
)
async def schedule_prompt(

    callback: CallbackQuery,

    state: FSMContext

):

    if await is_admin(

        callback.from_user.id

    ):

        await state.set_state(

            AdminState.schedule

        )


        await callback.message.answer(

            "Send:\n\n"

            "<code>HH:MM | MESSAGE</code>\n\n"

            "Time is UTC."

        )


# =========================================================
# SCHEDULE RECEIVED
# =========================================================

@dp.message(
    AdminState.schedule
)
async def schedule_received(

    message: Message,

    state: FSMContext

):

    if not await is_admin(

        message.from_user.id

    ):

        return


    try:

        t, text = (

            message.text.split(

                "|",

                1

            )

        )


        datetime.strptime(

            t.strip(),

            "%H:%M"

        )


        await add_schedule(

            t.strip(),

            text.strip()

        )


        await state.clear()


        await message.answer(

            "⏰ Daily broadcast scheduled.",

            reply_markup=admin_keyboard()

        )


    except Exception:

        await message.answer(

            "❌ Format:\n\n"

            "HH:MM | MESSAGE"

        )


# =========================================================
# STATISTICS
# =========================================================

@dp.callback_query(
    F.data == "stats"
)
async def stats(

    callback: CallbackQuery

):

    if await is_admin(

        callback.from_user.id

    ):

        count = await get_user_count()


        await callback.message.answer(

            f"👥 <b>Total saved users:</b> "

            f"{count}"

        )


# =========================================================
# ADMIN BACK
# =========================================================

@dp.callback_query(
    F.data == "admin_back"
)
async def admin_back(

    callback: CallbackQuery

):

    if await is_admin(

        callback.from_user.id

    ):

        await callback.message.edit_text(

            "🔐 <b>Admin Panel</b>",

            reply_markup=admin_keyboard()

        )


# =========================================================
# SCHEDULE BROADCAST WORKER
# =========================================================

async def scheduler():

    last_minute = None


    while True:

        try:

            now = datetime.now(

                timezone.utc

            )


            minute = now.strftime(

                "%H:%M"

            )


            if minute != last_minute:

                last_minute = minute


                today = now.date().isoformat()


                schedules = await get_schedules()


                for item in schedules:

                    if (

                        item["time"] == minute

                        and

                        item["last_run_date"]

                        != today

                    ):

                        logging.info(

                            "Running scheduled broadcast ID=%s",

                            item["id"]

                        )


                        for uid in await get_all_users():

                            try:

                                await bot.send_message(

                                    uid,

                                    item["message"]

                                )

                            except Exception:

                                pass


                        await mark_schedule_run(

                            item["id"],

                            today

                        )


        except Exception:

            logging.exception(

                "SCHEDULER FAILED"

            )


        await asyncio.sleep(

            20

        )


# =========================================================
# RENDER HEALTH CHECK
# =========================================================

async def health(

    request

):

    return web.Response(

        text="OK"

    )


# =========================================================
# MAIN
# =========================================================

async def main():

    # Initialize PostgreSQL

    await init_db()


    # Render Web Server

    app = web.Application()


    app.router.add_get(

        "/",

        health

    )


    app.router.add_get(

        "/health",

        health

    )


    runner = web.AppRunner(

        app

    )


    await runner.setup()


    port = int(

        os.getenv(

            "PORT",

            "10000"

        )

    )


    await web.TCPSite(

        runner,

        "0.0.0.0",

        port

    ).start()


    logging.info(

        "Health server started "
        "on port %s",

        port

    )


    # Start scheduler

    asyncio.create_task(

        scheduler()

    )


    logging.info(

        "Starting Telegram polling..."

    )


    # Start bot

    await dp.start_polling(

        bot,

        allowed_updates=

        dp.resolve_used_update_types()

    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    asyncio.run(

        main()

    )
