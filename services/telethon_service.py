import asyncio
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, UserBannedInChannelError
import random
import config
import database.db as db
from services.openai_service import generate_comment

# Словарь для хранения активных клиентов
# {session_name: TelegramClient}
active_clients = {}
# Список для ротации
rotation_queue = asyncio.Queue()

async def start_clients():
    """Запускает все аккаунты из БД"""
    accounts = await db.get_all_accounts()
    if not accounts:
        print("Нет активных аккаунтов в базе.")
        return

    for acc in accounts:
        _, phone, api_id, api_hash, session_name, _, _, _ = acc
        client = TelegramClient(f"sessions/{session_name}", api_id, api_hash)
        
        try:
            await client.connect()
            if not await client.is_user_authorized():
                print(f"Аккаунт {session_name} не авторизован! Пропуск.")
                await client.disconnect()
                continue
            
            active_clients[session_name] = client
            await rotation_queue.put(session_name) # Добавляем в очередь ротации
            print(f"Аккаунт {session_name} запущен и добавлен в очередь.")
            
        except Exception as e:
            print(f"Ошибка запуска {session_name}: {e}")
            await db.update_account_status(session_name, "error")

    # Если есть клиенты, запускаем мониторинг на первом из них
    if active_clients:
        first_client = list(active_clients.values())[0]
        setup_monitoring(first_client)

# ... ваши импорты

def setup_monitoring(client):
    """Настраивает обработчик новых сообщений на первом клиенте (Listener)"""
    
    # УБИРАЕМ аргумент chats из декоратора, чтобы ловить ВСЕ сообщения
    @client.on(events.NewMessage())
    async def handler(event):
        # 1. Проверяем, что это пост (а не комментарий), по отсутствию reply_to
        if event.message.reply_to:
            return
            
        # 2. Получаем список каналов из БД (чтобы он был актуальным)
        channels = await db.get_all_channels()
        
        # Извлекаем только юзернеймы (предполагаем, что username на индексе 1 в строке БД)
        # Формат строки в БД: id, username, title, is_active -> username это [1]
        monitored_usernames = [ch[1] for ch in channels]
        
        # 3. Проверяем, есть ли чат, в котором произошло событие, в нашем списке
        # event.chat.username может быть None, если это группа без юзернейма
        chat_username = event.chat.username if event.chat else None
        
        if chat_username not in monitored_usernames:
            return

        # Если мы здесь, значит пост в нужном нам канале
        channel_username = chat_username
        post_text = event.message.message
        post_id = event.message.id

        print(f"Новый пост в @{channel_username}: {post_text[:30]}...")

        # Логика комментирования
        await process_new_post(channel_username, post_id, post_text)

async def process_new_post(channel_username, post_id, post_text):
    """
    Выбирает аккаунт, генерирует текст, комментирует.
    """
    # 1. Получаем промпт
    prompt = await db.get_active_prompt()
    
    # 2. Ротация аккаунта (занимаем из очереди, потом вернем)
    try:
        session_name = rotation_queue.get_nowait()
    except asyncio.QueueEmpty:
        print("Очередь аккаунтов пуста.")
        return

    client = active_clients.get(session_name)
    if not client:
        return

    try:
        # Задержка перед генерацией
        await asyncio.sleep(random.uniform(1, 3))

        # 3. Генерация текста
        comment_text = await generate_comment(post_text, prompt)
        print(f"Сгенерирован комментарий: {comment_text}")

        # 4. Случайная задержка перед отправкой (человеческое поведение)
        delay = random.uniform(config.MIN_DELAY, config.MAX_DELAY)
        print(f"Ожидание {delay:.2f} сек...")
        await asyncio.sleep(delay)

        # 5. Отправка комментария
        # Нам нужно получить entity канала
        entity = await client.get_entity(channel_username)
        await client.send_message(
            entity,
            message=comment_text,
            comment_to=post_id
        )
        
        print(f"Комментарий отправлен от {session_name}")
        
        # Обновляем статистику
        await db.increment_account_comments(session_name)
        await db.log_comment(session_name, channel_username, post_id, comment_text)
        
        # Возвращаем аккаунт в конец очереди
        await rotation_queue.put(session_name)

    except FloodWaitError as e:
        print(f"FloodWait на {session_name}: ждем {e.seconds} сек")
        await db.update_account_status(session_name, "restricted")
        # Не возвращаем аккаунт в очередь сразу, ждем
        await asyncio.sleep(e.seconds)
        await db.update_account_status(session_name, "working")
        await rotation_queue.put(session_name)
        
    except UserBannedInChannelError:
        print(f"Аккаунт {session_name} забанен в канале")
        await db.update_account_status(session_name, "banned")
        
    except Exception as e:
        print(f"Ошибка при отправке комментария: {e}")
        # Возвращаем в очередь в любом случае, кроме бана
        await rotation_queue.put(session_name)

async def add_account_process(phone, api_id, api_hash):
    """
    Функция для добавления аккаунта через бота.
    Требует интерактивного ввода кода (заглушка, так как через бота сложно сделать 2FA).
    Мы создадим клиента и попросим пользователя запустить его на ПК для авторизации,
    либо здесь реализуем простейший запрос кода, если бот запущен локально.
    
    Для ПРОСТОТЫ кода: мы будем ожидать, что пользователь скинет session string
    или мы временно переключим консольный ввод (но в телеграм-боте это не работает).
    
    РЕШЕНИЕ: В этом примере мы создадим сессию, но пользователь должен будет ввести код
    в ЛОГИ СЕРВЕРА (консоль), так как aiogram не умеет перехватывать ввод кода из телеграма
    для Telethon легко.
    """
    session_name = f"session_{phone}"
    client = TelegramClient(f"sessions/{session_name}", api_id, api_hash)
    await client.connect()
    
    if not await client.is_user_authorized():
        # В реальном проекте здесь нужен сложный механизмState Machine
        # Здесь мы возвращаем флаг, что требуется код
        return client, "CODE_REQUIRED"
    
    await db.add_account_to_db(phone, api_id, api_hash, session_name)
    await client.disconnect()
    return None, "SUCCESS"

async def send_code_request(client, phone):
    await client.send_code_request(phone)

async def sign_in(client, code, password=None):
    await client.sign_in(code, password=password)