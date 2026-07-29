import asyncio
import logging
import os
from datetime import datetime, timezone

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, ChatJoinRequest, ChatMemberUpdated
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from database import (
    init_db, get_settings, update_setting, add_force_join, remove_force_join,
    list_force_join, get_all_users, save_user, get_user_count,
    set_force_join_title, add_schedule, get_schedules, mark_schedule_run
)
from keyboards import force_join_keyboard, admin_keyboard

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


class AdminState(StatesGroup):
    registration_link = State()
    welcome = State()
    broadcast = State()
    chat_id = State()
    join_title = State()
    schedule = State()


async def is_admin(uid):
    return uid == ADMIN_ID


async def is_member(chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
    except Exception:
        return False


async def all_joined(user_id):
    chats = await list_force_join()
    return all(await is_member(c["chat_id"], user_id) for c in chats) if chats else True


@dp.message(CommandStart())
async def start(message: Message):
    await save_user(message.from_user.id, message.from_user.username or "")
    await bot.send_chat_action(message.chat.id, "typing")
    await asyncio.sleep(1)

    settings = await get_settings()
    welcome = settings.get(
        "welcome_message",
        "🎁 <b>WELCOME BONUS ₹1080</b>\n\n"
        "Welcome! Complete the required join steps to continue."
    )

    if not await all_joined(message.from_user.id):
        await message.answer(
            f"{welcome}\n\n"
            "🔒 <b>Step 1:</b> Join/request to join all required channels and groups.\n"
            "Then press 🟢 <b>CHECK JOIN</b>.",
            reply_markup=await force_join_keyboard()
        )
        return

    link = settings.get("registration_link")
    if link:
        await message.answer(
            f"{welcome}\n\n"
            "🎉 <b>All required joins verified!</b>\n\n"
            f"🔗 <b>Registration Link:</b>\n{link}\n\n"
            "📝 Register using the link above."
        )
    else:
        await message.answer(f"{welcome}\n\n⚠️ Registration link is not configured yet.")


@dp.callback_query(F.data == "check_join")
async def check_join(callback: CallbackQuery):
    await callback.answer("Checking…")
    if not await all_joined(callback.from_user.id):
        await callback.message.answer(
            "❌ <b>Not completed yet.</b>\n\n"
            "Please join all required channels/groups and try again.",
            reply_markup=await force_join_keyboard()
        )
        return

    settings = await get_settings()
    link = settings.get("registration_link")
    await callback.message.edit_text(
        "🎉 <b>VERIFICATION SUCCESSFUL!</b>\n\n"
        "🎁 <b>WELCOME BONUS ₹1080</b>\n\n"
        + (f"🔗 <b>Registration Link:</b>\n{link}\n\n📝 Register using the link above."
           if link else "⚠️ Registration link is not configured yet.")
    )


@dp.chat_join_request()
async def join_request(request: ChatJoinRequest):
    logging.info("Join request: %s -> %s", request.from_user.id, request.chat.id)


@dp.chat_member()
async def member_update(event: ChatMemberUpdated):
    old = event.old_chat_member.status
    new = event.new_chat_member.status
    if old not in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED} and new in {
        ChatMemberStatus.LEFT, ChatMemberStatus.KICKED
    }:
        uid = event.from_user.id
        if uid != ADMIN_ID:
            try:
                await bot.send_message(
                    uid,
                    "⚠️ <b>You left a required channel/group.</b>\n\n"
                    "Please join again and press 🟢 <b>CHECK JOIN</b>.",
                    reply_markup=await force_join_keyboard()
                )
            except Exception:
                logging.exception("Leave reminder failed")


@dp.message(Command("admin"))
async def admin(message: Message):
    if await is_admin(message.from_user.id):
        await message.answer("🔐 <b>Admin Panel</b>", reply_markup=admin_keyboard())


@dp.callback_query(F.data == "admin_forcejoin")
async def forcejoin_panel(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id): return
    chats = await list_force_join()
    text = "📋 <b>Force Join Chats</b>\n\n" + (
        "\n".join(f"• {c['title']} — <code>{c['chat_id']}</code>" for c in chats)
        if chats else "No chats configured."
    )
    kb = __import__("aiogram").types.InlineKeyboardMarkup(inline_keyboard=[
        [__import__("aiogram").types.InlineKeyboardButton(text="➕ Add Chat", callback_data="add_chat")],
        [__import__("aiogram").types.InlineKeyboardButton(text="🗑️ Remove Chat", callback_data="remove_chat")],
        [__import__("aiogram").types.InlineKeyboardButton(text="🏷️ Button Title", callback_data="join_title")],
        [__import__("aiogram").types.InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)


@dp.callback_query(F.data.in_({"add_chat", "remove_chat"}))
async def chat_prompt(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id): return
    await state.set_state(AdminState.chat_id)
    await callback.message.answer("Send the chat ID, e.g. <code>-1001234567890</code>.")


@dp.message(AdminState.chat_id)
async def chat_id_received(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    try:
        cid = int(message.text.strip())
        chats = await list_force_join()
        if any(c["chat_id"] == cid for c in chats):
            await remove_force_join(cid)
            await message.answer("🗑️ Chat removed.", reply_markup=admin_keyboard())
        else:
            chat = await bot.get_chat(cid)
            invite = None
            try:
                invite = await bot.create_chat_invite_link(cid, name="Force Join")
            except Exception:
                pass
            await add_force_join(cid, chat.title or str(cid), invite.invite_link if invite else None, "🔵 JOIN NOW")
            await message.answer(f"✅ Added: <b>{chat.title}</b>", reply_markup=admin_keyboard())
        await state.clear()
    except Exception:
        await message.answer("❌ Invalid chat ID or bot lacks admin permissions.")


@dp.callback_query(F.data == "join_title")
async def title_prompt(callback: CallbackQuery, state: FSMContext):
    if await is_admin(callback.from_user.id):
        await state.set_state(AdminState.join_title)
        await callback.message.answer("Send: <code>CHAT_ID | BUTTON TITLE</code>")


@dp.message(AdminState.join_title)
async def title_received(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    try:
        cid, title = message.text.split("|", 1)
        await set_force_join_title(int(cid.strip()), title.strip())
        await state.clear()
        await message.answer("✅ Button title updated.", reply_markup=admin_keyboard())
    except Exception:
        await message.answer("❌ Use: CHAT_ID | BUTTON TITLE")


@dp.callback_query(F.data == "registration")
async def registration(callback: CallbackQuery, state: FSMContext):
    if await is_admin(callback.from_user.id):
        await state.set_state(AdminState.registration_link)
        await callback.message.answer("Send the new registration link.")


@dp.message(AdminState.registration_link)
async def registration_received(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    await update_setting("registration_link", message.text.strip())
    await state.clear()
    await message.answer("✅ Registration link updated.", reply_markup=admin_keyboard())


@dp.callback_query(F.data == "welcome")
async def welcome_prompt(callback: CallbackQuery, state: FSMContext):
    if await is_admin(callback.from_user.id):
        await state.set_state(AdminState.welcome)
        await callback.message.answer("Send the new welcome message.")


@dp.message(AdminState.welcome)
async def welcome_received(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    await update_setting("welcome_message", message.text)
    await state.clear()
    await message.answer("✅ Welcome message updated.", reply_markup=admin_keyboard())


async def send_broadcast(message: Message):
    sent = failed = 0
    for uid in await get_all_users():
        try:
            await bot.copy_message(uid, message.chat.id, message.message_id)
            sent += 1
        except Exception:
            failed += 1
    return sent, failed


@dp.callback_query(F.data == "broadcast")
async def broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if await is_admin(callback.from_user.id):
        await state.set_state(AdminState.broadcast)
        await callback.message.answer("Send the broadcast message.")


@dp.message(AdminState.broadcast)
async def broadcast_received(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    sent, failed = await send_broadcast(message)
    await state.clear()
    await message.answer(f"📢 <b>Broadcast complete</b>\n\n✅ Sent: {sent}\n❌ Failed: {failed}")


@dp.callback_query(F.data == "schedule")
async def schedule_prompt(callback: CallbackQuery, state: FSMContext):
    if await is_admin(callback.from_user.id):
        await state.set_state(AdminState.schedule)
        await callback.message.answer("Send: <code>HH:MM | MESSAGE</code> (UTC, daily)")


@dp.message(AdminState.schedule)
async def schedule_received(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id): return
    try:
        t, text = message.text.split("|", 1)
        datetime.strptime(t.strip(), "%H:%M")
        await add_schedule(t.strip(), text.strip())
        await state.clear()
        await message.answer("⏰ Daily broadcast scheduled.", reply_markup=admin_keyboard())
    except Exception:
        await message.answer("❌ Use: HH:MM | MESSAGE")


@dp.callback_query(F.data == "stats")
async def stats(callback: CallbackQuery):
    if await is_admin(callback.from_user.id):
        await callback.message.answer(f"👥 <b>Total users:</b> {await get_user_count()}")


@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if await is_admin(callback.from_user.id):
        await callback.message.edit_text("🔐 <b>Admin Panel</b>", reply_markup=admin_keyboard())


async def scheduler():
    last_minute = None
    while True:
        now = datetime.now(timezone.utc)
        minute = now.strftime("%H:%M")
        if minute != last_minute:
            last_minute = minute
            for item in await get_schedules():
                if item["time"] == minute and item["last_run_date"] != now.date().isoformat():
                    for uid in await get_all_users():
                        try:
                            await bot.send_message(uid, item["message"])
                        except Exception:
                            pass
                    await mark_schedule_run(item["id"], now.date().isoformat())
        await asyncio.sleep(20)


async def health(request):
    return web.Response(text="OK")


async def main():
    await init_db()
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "10000"))).start()
    asyncio.create_task(scheduler())
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
