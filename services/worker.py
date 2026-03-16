import asyncio
import random
from sqlalchemy import select, update
from database import async_session_maker, Account, Channel, Comment
from telethon.errors import FloodWaitError
from telethon import TelegramClient, functions
from services.telethon_service import StringSession, send_comment
from services.openai_service import generate_comment
import logging

logging.basicConfig(level=logging.INFO)

async def worker():
    """
    Фоновый процесс, который проверяет каналы и пишет комментарии.
    """
    while True:
        try:
            async with async_session_maker() as session:
                # 1. Получаем активные каналы
                result = await session.execute(select(Channel).where(Channel.is_active == True))
                channels = result.scalars().all()
                
                # 2. Получаем активные аккаунты для ротации
                res_acc = await session.execute(select(Account).where(Account.is_active == True))
                accounts = res_acc.scalars().all()
                
                if not accounts:
                    await asyncio.sleep(60)
                    continue

                for channel in channels:
                    # Выбираем случайный аккаунт (ротация)
                    account = random.choice(accounts)
                    
                    try:
                        client = TelegramClient(
                            StringSession(account.session_string),
                            account.api_id,
                            account.api_hash
                        )
                        await client.connect()
                        
                        if not await client.is_user_authorized():
                            account.is_active = False
                            account.status = "session_expired"
                            await session.commit()
                            await client.disconnect()
                            continue

                        # Получаем последний пост
                        entity = await client.get_entity(channel.username)
                        messages = await client.get_messages(entity, limit=1)
                        
                        if not messages:
                            await client.disconnect()
                            continue
                            
                        last_msg = messages[0]
                        
                        # Если пост новый (ID больше того, что мы записали)
                        if last_msg.id > channel.last_post_id:
                            logging.info(f"New post in {channel.username}: {last_msg.id}")
                            
                            # Генерация комментария
                            # Пример: используем "friendly" по умолчанию, можно вынести в настройки
                            comment_text = await generate_comment(last_msg.text or "Media", "friendly")
                            
                            # Отправка
                            # Функция send_comment сама создаст клиент и отключит его
                            new_session = await send_comment(account, channel.username, last_msg.id, comment_text)
                            
                            if new_session and new_session != "flood":
                                # Успешно отправлено
                                account.session_string = new_session
                                account.comments_count += 1
                                channel.last_post_id = last_msg.id
                                
                                # Логируем комментарий
                                new_comment = Comment(
                                    account_id=account.id,
                                    channel_id=channel.id,
                                    post_id=last_msg.id,
                                    text=comment_text
                                )
                                session.add(new_comment)
                                await session.commit()
                                logging.info(f"Comment sent by {account.phone}")
                                
                                # Случайная задержка, чтобы не спамить бездумно
                                await asyncio.sleep(random.randint(60, 300))
                            elif new_session == "flood":
                                account.is_active = False
                                account.status = "flood_wait"
                                await session.commit()
                                
                        await client.disconnect()

                    except Exception as e:
                        logging.error(f"Worker loop error for channel {channel.username}: {e}")
                        if 'client' in locals() and client.is_connected():
                            await client.disconnect()

            # Пауза перед следующей проверкой всех каналов
            await asyncio.sleep(60) 

        except Exception as e:
            logging.critical(f"Critical worker error: {e}")
            await asyncio.sleep(120)