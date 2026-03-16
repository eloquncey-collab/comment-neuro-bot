from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import config
import database.db as db
from bot.keyboards import get_main_keyboard, get_back_keyboard, get_prompts_keyboard
from services.telethon_service import add_account_process, send_code_request, sign_in

router = Router()

# --- States ---
class AddAccount(StatesGroup):
    phone = State()
    api_id = State()
    api_hash = State()
    code = State()

class AddChannel(StatesGroup):
    username = State()

class AddCustomPrompt(StatesGroup):
    text = State()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("Нет доступа.")
        return
    await message.answer("Привет! Выберите действие:", reply_markup=get_main_keyboard())

@router.callback_query(F.data == "main")
async def show_main(callback: types.CallbackQuery):
    await callback.message.edit_text("Меню:", reply_markup=get_main_keyboard())

# --- Управление Аккаунтами ---
@router.callback_query(F.data == "accounts")
async def show_accounts(callback: types.CallbackQuery):
    accounts = await db.get_all_accounts()
    if not accounts:
        text = "Нет добавленных аккаунтов."
    else:
        text = "Список аккаунтов:\n\n"
        for acc in accounts:
            _, phone, _, _, session, status, _, count = acc
            text += f"📱 {phone} ({session})\nСтатус: {status} | Комм: {count}\n\n"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())

# Упрощенная процедура добавления аккаунта (через Console Code)
@router.callback_query(F.data == "add_account_action")
async def add_account_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddAccount.phone)
    await callback.message.edit_text("Введите номер телефона (формат: +7999...):")

@router.message(AddAccount.phone)
async def input_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(AddAccount.api_id)
    await message.answer("Введите API_ID (получить на my.telegram.org):")

@router.message(AddAccount.api_id)
async def input_api_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("API_ID должен быть числом.")
    await state.update_data(api_id=int(message.text))
    await state.set_state(AddAccount.api_hash)
    await message.answer("Введите API_HASH:")

@router.message(AddAccount.api_hash)
async def input_api_hash(message: types.Message, state: FSMContext):
    await state.update_data(api_hash=message.text)
    data = await state.get_data()
    
    # Создаем клиента и запрашиваем код
    from services.telethon_service import TelegramClient # Импорт здесь чтобы избежать цикла, если была бы архитектура иначе
    # В данном файле лучше импортировать сверху, но для примера оставим так.
    
    # Внимание: Для реального бота авторизация должна происходить в фоне или через отдельный скрипт,
    # так как Telethon требует синхронного ввода кода или сложной асинхронной связки.
    # Здесь мы сообщаем пользователю, что код нужно смотреть в ЛОГАХ сервера.
    
    session_name = f"session_{data['phone']}"
    client = TelegramClient(f"sessions/{session_name}", data['api_id'], data['api_hash'])
    
    await client.connect()
    try:
        result = await client.send_code_request(data['phone'])
        await state.update_data(client=client) # Сохраняем клиент в состояние (небезопасно для продакшна, но для примера ок)
        await state.set_state(AddAccount.code)
        await message.answer(f"Код отправлен на телефон. Пожалуйста, введите код который пришел в Telegram.\n\n(Или проверьте консоль/логи сервера, если код не пришел в бот)")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        await state.clear()

@router.message(AddAccount.code)
async def input_code(message: types.Message, state: FSMContext):
    data = await state.get_data()
    client = data.get('client')
    code = message.text.strip()
    
    try:
        await client.sign_in(code=code)
        # Сохраняем в БД
        await db.add_account_to_db(data['phone'], data['api_id'], data['api_hash'], f"session_{data['phone']}")
        await client.disconnect()
        await message.answer("Аккаунт успешно добавлен!", reply_markup=get_main_keyboard())
        await state.clear()
    except Exception as e:
        await message.answer(f"Ошибка входа: {e}")

# --- Управление Каналами ---
@router.callback_query(F.data == "channels")
async def show_channels(callback: types.CallbackQuery):
    channels = await db.get_all_channels()
    if not channels:
        text = "Нет добавленных каналов."
    else:
        text = "Отслеживаемые каналы:\n"
        for ch in channels:
            _, username, _, _ = ch
            text += f"@{username}\n"
    
    kb = [[types.InlineKeyboardButton(text="Добавить канал", callback_data="add_channel_start")]]
    kb.append([types.InlineKeyboardButton(text="Назад", callback_data="main")])
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@router.callback_query(F.data == "add_channel_start")
async def add_channel_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddChannel.username)
    await callback.message.edit_text("Введите юзернейм канала (без @):")

@router.message(AddChannel.username)
async def add_channel_save(message: types.Message, state: FSMContext):
    username = message.text.strip().replace("@", "")
    try:
        # Проверяем существование канала (нужен любой клиент)
        from services.telethon_service import active_clients
        if not active_clients:
            await message.answer("Сначала добавьте хотя бы один рабочий аккаунт.")
            return
        
        client = list(active_clients.values())[0]
        entity = await client.get_entity(username)
        
        await db.add_channel_to_db(username, entity.title)
        await message.answer(f"Канал @{username} ({entity.title}) добавлен.", reply_markup=get_main_keyboard())
        await state.clear()
    except Exception as e:
        await message.answer(f"Ошибка: канал не найден. {e}")

# --- Промпты ---
@router.callback_query(F.data == "prompts")
async def show_prompts(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите тип комментария:", reply_markup=get_prompts_keyboard())

@router.callback_query(F.data.startswith("set_prompt_"))
async def set_prompt(callback: types.CallbackQuery):
    action = callback.data.split("_")[-1]
    
    if action == "custom":
        # Здесь можно было бы FSM для ввода текста, но для краткости просто попросим команду /set_prompt
        await callback.message.edit_text("Чтобы установить свой промпт, отправьте команду /set_prompt <текст>")
        return

    # Маппинг действий на ID или названия в БД (упрощенно)
    # В реальном проекте нужно хранить ID выбранного промпта в настройках юзера
    prompt_names = {
        "short": "Короткий",
        "friendly": "Дружелюбный",
        "provo": "Провокационный"
    }
    
    name = prompt_names.get(action, "Стандартный")
    # В данном упрощенном коде мы не меняем дефолтные промпты, а логика get_active_prompt просто берет последний.
    # Чтобы это работало, нужно добавить таблицу user_settings. 
    # Для примера просто сообщим, что выбран (визуально).
    await callback.answer(f"Выбран тип: {name}")

@router.message(Command("set_prompt"))
async def custom_prompt_command(message: types.Message):
    text = message.text.split("/set_prompt ", 1)[-1]
    if text:
        await db.add_prompt_to_db("Custom", text)
        await message.answer("Ваш кастомный промпт установлен и будет использоваться следующим.")
    else:
        await message.answer("Введите текст после команды.")

# --- Статистика ---
@router.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    total, acc_stats = await db.get_stats()
    text = f"Всего комментариев: {total}\n\nСтатистика по аккаунтам:\n"
    for acc in acc_stats:
        session, count, status = acc
        text += f"{session}: {count} комм. ({status})\n"
    
    await callback.message.edit_text(text, reply_markup=get_back_keyboard())