from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Аккаунты", callback_data="accounts")],
        [InlineKeyboardButton(text="Каналы", callback_data="channels")],
        [InlineKeyboardButton(text="Промпты", callback_data="prompts")],
        [InlineKeyboardButton(text="Статистика", callback_data="stats")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="main")]
    ])

def get_prompts_keyboard():
    # В реальном коде нужно запрашивать промпты из БД
    buttons = [
        [InlineKeyboardButton(text="Короткий", callback_data="set_prompt_short")],
        [InlineKeyboardButton(text="Дружелюбный", callback_data="set_prompt_friendly")],
        [InlineKeyboardButton(text="Провокационный", callback_data="set_prompt_provo")],
        [InlineKeyboardButton(text="Свой промпт", callback_data="set_prompt_custom")],
        [InlineKeyboardButton(text="Назад", callback_data="main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)