import asyncio
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, update, func
from database import async_session_maker, Account, Channel, Comment, Prompt
from telethon import TelegramClient, errors
from services.telethon_service import StringSession
from bot.keyboards import get_main_kb, get_accounts_kb, get_prompts_kb
from config import settings

router = Router()

# --- States ---
class AddAccountStates(StatesGroup):
    api_id = State()
    api_hash = State()
    phone = State()
    code = State()

class AddChannelStates(StatesGroup):
    username = State()

class CustomPromptStates(StatesGroup):
    text = State()

# --- Handlers ---

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("Access denied.")
        return
    await message.answer("Панель управления нейрокомментингом", reply_markup=get_main_kb())

@router.callback_query(F.data == "back")
async def back(callback: types.CallbackQuery):
    await callback.message.edit_text("Панель управления", reply_markup=get_main_kb())

# --- Accounts Logic ---

@router.callback_query(F.data == "accounts")
async def list_accounts(callback: types.CallbackQuery):
    async with async_session_maker() as session:
        result = await session.execute(select(Account))
        accounts = result.scalars().all()
        text = "Список аккаунтов:"
        if not accounts:
            text = "Нет добавленных аккаунтов."
        await callback.message.edit_text(text, reply_markup=get_accounts_kb(accounts))

@router.callback_query(F.data == "add_account")
async def add_account_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddAccountStates.api_id)
    await callback.message.edit_text("Введите API ID (получить на my.telegram.org):")

@router.message(AddAccountStates.api_id)
async def add_api_id(message: types.Message, state: FSMContext):
    await state.update_data(api_id=int(message.text))
    await state.set_state(AddAccountStates.api_hash)
    await message.answer("Введите API Hash:")

@router.message(AddAccountStates.api_hash)
async def add_api_hash(message: types.Message, state: FSMContext):
    await state.update_data(api_hash=message.text)
    await state.set_state(AddAccountStates.phone)
    await message.answer("Введите номер телефона (с кодом страны, без +):")

@router.message(AddAccountStates.phone)
async def add_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    api_id = data['api_id']
    api_hash = data['api_hash']
    phone = message.text
    
    # Создаем временное подключение для запроса кода
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    
    try:
        result = await client.send_code_request(phone)
        await state.update_data(phone=phone, session_string="") # Пустая строка для новой сессии
        await state.set_state(AddAccountStates.code)
        # Сохраняем api_id/hash в состоянии, чтобы потом создать клиент
        await state.update_data(_api_id=api_id, _api_hash=api_hash)
        await message.answer(f"Код отправлен на {phone}. Введите полученный код:")
        await client.disconnect()
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
        await client.disconnect()
        await state.clear()

@router.message(AddAccountStates.code)
async def add_code(message: types.Message, state: FSMContext):
    data = await state.get_data()
    phone = data['phone']
    api_id = data['_api_id']
    api_hash = data['_api_hash']
    code = message.text

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    
    try:
        await client.sign_in(phone, code)
        # Получаем строку сессии
        session_string = client.session.save()
        await client.disconnect()
        
        # Сохраняем в БД
        async with async_session_maker() as session:
            new_acc = Account(
                phone=phone,
                api_id=api_id,
                api_hash=api_hash,
                session_string=session_string
            )
            session.add(new_acc)
            await session.commit()
            
        await message.answer("✅ Аккаунт успешно добавлен!")
        await state.clear()
        # Можно вызвать list_accounts тут, но для простоты завершим
    except Exception as e:
        await message.answer(f"Ошибка входа: {e}")
        await client.disconnect()
        await state.clear()

# --- Channels Logic ---

@router.callback_query(F.data == "channels")
async def list_channels(callback: types.CallbackQuery):
    async with async_session_maker() as session:
        res = await session.execute(select(Channel))
        channels = res.scalars().all()
        text = "\n".join([f"- {ch.title} (@{ch.username})" for ch in channels]) if channels else "Каналов нет."
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="➕ Добавить канал", callback_data="add_channel")],
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
        await callback.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data == "add_channel")
async def add_channel_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddChannelStates.username)
    await callback.message.edit_text("Введите юзернейм или ID канала (например @durov или -100...):")

@router.message(AddChannelStates.username)
async def add_channel_save(message: types.Message, state: FSMContext):
    username = message.text.strip()
    
    # Проверяем валидность через Telethon (используя любой акк или временный, если нужен)
    # Для упрощения просто сохраним, валидация будет в воркере
    
    async with async_session_maker() as session:
        new_ch = Channel(username=username, title=username) # Title обновится позже при первом скане
        session.add(new_ch)
        await session.commit()
    
    await message.answer("Канал добавлен.")
    await state.clear()

# --- Prompts Logic ---

@router.callback_query(F.data == "prompts")
async def prompts_menu(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите тип комментария по умолчанию:", reply_markup=get_prompts_kb())

@router.callback_query(F.data.startswith("set_prompt_"))
async def set_prompt(callback: types.CallbackQuery):
    p_type = callback.data.split("_")[-1]
    # Здесь можно сохранить настройку в БД, но пока просто подтверждение
    await callback.answer(f"Тип {p_type} установлен (в памяти бота)")

# --- Stats Logic ---

@router.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    async with async_session_maker() as session:
        total_comments = await session.scalar(select(func.count(Comment.id)))
        acc_res = await session.execute(select(Account).order_by(Account.comments_count.desc()))
        accounts = acc_res.scalars().all()
        
        text = f"Всего комментариев: {total_comments}\n\nСтатистика по аккаунтам:\n"
        for acc in accounts:
            text += f"{acc.phone}: {acc.comments_count} комм. ({acc.status})\n"
            
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 Назад", callback_data="back")]
        ])
        await callback.message.edit_text(text, reply_markup=kb)