from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import list_force_join

async def force_join_keyboard():
    chats = await list_force_join()
    rows = []
    for chat in chats:
        if chat.get("invite_link"):
            rows.append([InlineKeyboardButton(text=f"🔗 Join {chat['title']}", url=chat["invite_link"])])
        else:
            rows.append([InlineKeyboardButton(text=f"📢 {chat['title']}", callback_data="no_link")])
    rows.append([InlineKeyboardButton(text="🔄 Check Join", callback_data="check_join")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕/🗑️ Force Join Chats", callback_data="admin_forcejoin")],
        [InlineKeyboardButton(text="🔗 Update Registration Link", callback_data="registration")],
        [InlineKeyboardButton(text="📝 Update Welcome Message", callback_data="welcome")],
        [InlineKeyboardButton(text="📢 Broadcast", callback_data="broadcast")],
    ])
