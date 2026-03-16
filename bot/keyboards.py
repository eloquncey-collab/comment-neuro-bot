from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="stats")
    builder.button(text="👤 Аккаунты", callback_data="accounts")
    builder.button(text="📢 Каналы", callback_data="channels")
    builder.button(text="💬 Промпты", callback_data="prompts")
    builder.adjust(2)
    return builder.as_markup()

def get_accounts_kb(accounts):
    builder = InlineKeyboardBuilder()
    for acc in accounts:
        status_icon = "✅" if acc.is_active else "🚫"
        text = f"{status_icon} {acc.phone} ({acc.status})"
        builder.button(text=text, callback_data=f"acc_{acc.id}")
    builder.button(text="➕ Добавить аккаунт", callback_data="add_account")
    builder.button(text="🔙 Назад", callback_data="back")
    builder.adjust(1)
    return builder.as_markup()

def get_prompts_kb():
    builder = InlineKeyboardBuilder()
    types = ["short", "long", "friendly", "provocative", "intimate"]
    for t in types:
        builder.button(text=t.capitalize(), callback_data=f"set_prompt_{t}")
    builder.button(text="🔙 Назад", callback_data="back")
    builder.adjust(1)
    return builder.as_markup()