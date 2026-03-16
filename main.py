import asyncio
import logging
from aiogram import Bot, Dispatcher, DefaultBotProperties  # Добавлен импорт
from aiogram.enums import ParseMode
from config import settings
from database import init_db
from bot.handlers import router
from services.worker import worker

# Настройка логирования
logging.basicConfig(level=logging.INFO)

async def main():
    # 1. Инициализация БД
    await init_db()
    
    # 2. Инициализация Бота с новыми параметрами (без предупреждений)
    bot = Bot(
        token=settings.BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    dp.include_router(router)
    
    # 3. Запуск поллера (бот) и воркера (мониторинг) параллельно
    async with bot.session:
        await asyncio.gather(
            dp.start_polling(bot),
            worker()
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")