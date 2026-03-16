import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, ADMIN_ID
from database.db import init_db, init_default_prompts
from services.telethon_service import start_clients
from bot.handlers import router

# Настройка логирования
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    # Инициализация БД
    if not os.path.exists("bot_database.db"):
        await init_db()
        await init_default_prompts()

    # Инициализация бота
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # Запуск Telethon клиентов в фоне
    asyncio.create_task(start_clients())

    # Удаляем вебхуки и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")