from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, UserBannedInChannelError
from telethon.tl.types import InputPeerUser
import asyncio
import logging

# Мы будем создавать клиентов динамически, чтобы не держать все сессии в памяти
async def get_client(api_id, api_hash, session_string):
    client = TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash
    )
    await client.connect()
    return client

class StringSession:
    """Обертка для совместимости с Telethon, если строка пустая (для входа)"""
    def __init__(self, session_string=""):
        self.string = session_string

async def send_comment(account, channel_username, post_id, text):
    """
    Отправляет комментарий от лица аккаунта.
    Возвращает True в случае успеха, False при ошибке.
    """
    client = None
    try:
        # Используем временную сессию в памяти, не сохраняем файлы
        client = TelegramClient(StringSession(account.session_string), account.api_id, account.api_hash)
        await client.connect()
        
        if not await client.is_user_authorized():
            logging.error(f"Account {account.phone} not authorized!")
            return False

        # Получаем entity канала
        entity = await client.get_entity(channel_username)
        
        # Отправляем комментарий (ответ на сообщение)
        await client.send_message(entity, text, reply_to=post_id)
        
        # Обновляем session_string (важно для сохранения авторизации)
        # В telethon 1.x+ session_string обновляется автоматически внутри объекта клиента, 
        # но нам нужно вытащить его.
        # Получаем сохраненную сессию
        new_session_str = client.session.save()
        
        return new_session_str # Возвращаем обновленную сессию

    except FloodWaitError as e:
        logging.warning(f"FloodWait on {account.phone}: wait {e.seconds}s")
        await asyncio.sleep(e.seconds)
        return "flood"
    except Exception as e:
        logging.error(f"Error sending comment from {account.phone}: {e}")
        return False
    finally:
        if client:
            await client.disconnect()