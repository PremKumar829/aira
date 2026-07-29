from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database import list_force_join

async def force_join_keyboard():
    rows=[]
    for c in await list_force_join():
        title=c.get("button_title") or f"🔵 JOIN {c['title']}"
        rows.append([InlineKeyboardButton(text=title,url=c["invite_link"]) if c.get("invite_link")
                     else InlineKeyboardButton(text=title,callback_data="no_link")])
    rows.append([InlineKeyboardButton(text="🟢 CHECK JOIN",callback_data="check_join")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Force Join Chats",callback_data="admin_forcejoin")],
        [InlineKeyboardButton(text="🔗 Registration Link",callback_data="registration")],
        [InlineKeyboardButton(text="📝 Welcome Message",callback_data="welcome")],
        [InlineKeyboardButton(text="📢 Broadcast Now",callback_data="broadcast")],
        [InlineKeyboardButton(text="⏰ Schedule Broadcast",callback_data="schedule")],
        [InlineKeyboardButton(text="👥 User Statistics",callback_data="stats")]
    ])
