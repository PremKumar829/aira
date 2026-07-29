import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from database import init_db, get_settings, update_setting, add_force_join, remove_force_join, list_force_join, get_all_users, save_user
from keyboards import force_join_keyboard, admin_keyboard

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


class AdminState(StatesGroup):
    waiting_registration_link = State()
    waiting_welcome = State()
    waiting_broadcast = State()
    waiting_chat_id = State()


async def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


async def check_member(chat_id: int, user_id: int):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in {
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
    except Exception:
        return False


async def check_all_required(user_id: int):
    chats = await list_force_join()
    if not chats:
        return True
    for chat in chats:
        if not await check_member(chat["chat_id"], user_id):
            return False
    return True


@dp.message(CommandStart())
async def start(message: Message):
    await save_user(message.from_user.id, message.from_user.username or "")
    await message.bot.send_chat_action(message.chat.id, "typing")
    await asyncio.sleep(1)

    settings = await get_settings()
    welcome = settings.get("welcome_message") or "👋 Welcome! Please complete the required join steps below."

    if await check_all_required(message.from_user.id):
        link = settings.get("registration_link")
        if link:
            await message.answer(
                f"{welcome}\n\n"
                "✅ You have completed the required join steps.\n\n"
                f"🔗 <b>Registration Link:</b>\n{link}\n\n"
                "📝 Please register using the link above."
            )
        else:
            await message.answer(f"{welcome}\n\n⚠️ Registration link is not configured yet.")
        return

    await message.answer(
        f"{welcome}\n\n"
        "🔒 <b>First, join/request to join all required channels and groups.</b>\n"
        "After completing them, press <b>🔄 Check Join</b>.",
        reply_markup=await force_join_keyboard()
    )


@dp.callback_query(F.data == "check_join")
async def check_join(callback: CallbackQuery):
    await callback.answer("Checking...", show_alert=False)
    if await check_all_required(callback.from_user.id):
        settings = await get_settings()
        link = settings.get("registration_link")
        if link:
            await callback.message.edit_text(
                "🎉 <b>Verification Successful!</b>\n\n"
                f"🔗 <b>Registration Link:</b>\n{link}\n\n"
                "📝 Please register using the link above."
            )
        else:
            await callback.message.edit_text(
                "✅ Join verification successful.\n\n"
                "⚠️ Registration link is not configured yet."
            )
    else:
        await callback.message.answer(
            "❌ You have not joined/requested all required channels or groups yet.\n"
            "Please complete all required steps and try again.",
            reply_markup=await force_join_keyboard()
        )


@dp.chat_join_request()
async def join_request(request: ChatJoinRequest):
    # Telegram sends this event when a user requests to join a chat.
    # Membership is only considered complete after the user is actually a member.
    logging.info("Join request from %s for %s", request.from_user.id, request.chat.id)


@dp.message(Command("admin"))
async def admin(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("🔐 <b>Admin Panel</b>", reply_markup=admin_keyboard())


@dp.callback_query(F.data == "admin_forcejoin")
async def admin_forcejoin(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    chats = await list_force_join()
    text = "📋 <b>Force Join Chats</b>\n\n"
    if not chats:
        text += "No chats configured."
    else:
        for c in chats:
            text += f"• {c['title']} — <code>{c['chat_id']}</code>\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Chat", callback_data="add_chat")],
        [InlineKeyboardButton(text="🗑️ Remove Chat", callback_data="remove_chat")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="admin_back")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)


@dp.callback_query(F.data == "add_chat")
async def add_chat(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.waiting_chat_id)
    await callback.message.answer(
        "Send the chat ID of the channel/group.\n\n"
        "Example: <code>-1001234567890</code>\n"
        "The bot must be an admin in the chat."
    )


@dp.message(AdminState.waiting_chat_id)
async def receive_chat_id(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    try:
        chat_id = int(message.text.strip())
        chat = await bot.get_chat(chat_id)
        invite = None
        try:
            invite = await bot.create_chat_invite_link(chat_id, name="Force Join")
        except Exception:
            pass
        await add_force_join(chat_id, chat.title or str(chat_id), invite.invite_link if invite else None)
        await state.clear()
        await message.answer(f"✅ Added: <b>{chat.title}</b>", reply_markup=admin_keyboard())
    except Exception as e:
        await message.answer(
            "❌ Could not add this chat. Check the chat ID and ensure the bot is an admin."
        )


@dp.callback_query(F.data == "remove_chat")
async def remove_chat_prompt(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.waiting_chat_id)
    await callback.message.answer("Send the chat ID you want to remove.")


@dp.callback_query(F.data == "registration")
async def registration(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.waiting_registration_link)
    await callback.message.answer("Send the new registration link.")


@dp.message(AdminState.waiting_registration_link)
async def receive_registration_link(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await update_setting("registration_link", message.text.strip())
    await state.clear()
    await message.answer("✅ Registration link updated.", reply_markup=admin_keyboard())


@dp.callback_query(F.data == "welcome")
async def welcome_edit(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.waiting_welcome)
    await callback.message.answer("Send the new welcome message.")


@dp.message(AdminState.waiting_welcome)
async def receive_welcome(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    await update_setting("welcome_message", message.text)
    await state.clear()
    await message.answer("✅ Welcome message updated.", reply_markup=admin_keyboard())


@dp.callback_query(F.data == "broadcast")
async def broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        return
    await state.set_state(AdminState.waiting_broadcast)
    await callback.message.answer("Send the broadcast message.")


@dp.message(AdminState.waiting_broadcast)
async def receive_broadcast(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        return
    users = await get_all_users()
    sent = 0
    failed = 0
    for user_id in users:
        try:
            await bot.copy_message(user_id, message.chat.id, message.message_id)
            sent += 1
        except Exception:
            failed += 1
    await state.clear()
    await message.answer(f"📢 Broadcast complete.\n✅ Sent: {sent}\n❌ Failed: {failed}")


@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        return
    await callback.message.edit_text("🔐 <b>Admin Panel</b>", reply_markup=admin_keyboard())


async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
