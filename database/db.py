import aiosqlite
import asyncio

DB_NAME = "bot_database.db"

async def init_db():
    """Создание таблиц при первом запуске"""
    async with aiosqlite.connect(DB_NAME) as db:
        # Таблица аккаунтов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT,
                api_id INTEGER,
                api_hash TEXT,
                session_name TEXT UNIQUE,
                is_active BOOLEAN DEFAULT 1,
                status TEXT DEFAULT 'working', -- working, banned, restricted, frozen
                comments_count INTEGER DEFAULT 0
            )
        """)
        
        # Таблица каналов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                title TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        
        # Таблица промптов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prompts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                text TEXT,
                is_default BOOLEAN DEFAULT 0
            )
        """)

        # Таблица статистики (история комментариев)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS comments_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                channel_username TEXT,
                post_id INTEGER,
                comment_text TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await db.commit()

# --- Функции для Аккаунтов ---

async def add_account_to_db(phone, api_id, api_hash, session_name):
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute(
                "INSERT INTO accounts (phone, api_id, api_hash, session_name) VALUES (?, ?, ?, ?)",
                (phone, api_id, api_hash, session_name)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def get_all_accounts():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM accounts WHERE is_active = 1")
        return await cursor.fetchall()

async def get_account_by_session(session_name):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM accounts WHERE session_name = ?", (session_name,))
        return await cursor.fetchone()

async def update_account_status(session_name, status):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE accounts SET status = ? WHERE session_name = ?", (status, session_name))
        await db.commit()

async def increment_account_comments(session_name):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE accounts SET comments_count = comments_count + 1 WHERE session_name = ?",
            (session_name,)
        )
        await db.commit()

# --- Функции для Каналов ---

async def add_channel_to_db(username, title):
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute(
                "INSERT INTO channels (username, title) VALUES (?, ?)",
                (username, title)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def get_all_channels():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM channels WHERE is_active = 1")
        return await cursor.fetchall()

async def delete_channel_from_db(username):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM channels WHERE username = ?", (username,))
        await db.commit()

# --- Функции для Промптов ---

async def add_prompt_to_db(name, text, is_default=False):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO prompts (name, text, is_default) VALUES (?, ?, ?)",
            (name, text, is_default)
        )
        await db.commit()

async def get_active_prompt():
    async with aiosqlite.connect(DB_NAME) as db:
        # Берем последний добавленный кастомный, если нет - дефолтный
        # Для простоты вернем первый попавшийся, в реальном боте нужна настройка "выбранного"
        cursor = await db.execute("SELECT text FROM prompts ORDER BY id DESC LIMIT 1")
        row = await cursor.fetchone()
        if row:
            return row[0]
        return "Напиши интересный комментарий к этому посту." # Fallback

async def init_default_prompts():
    """Заполняем дефолтные промпты, если база пуста"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT count(*) FROM prompts")
        count = (await cursor.fetchone())[0]
        if count == 0:
            defaults = [
                ("Короткий", "Напиши короткий комментарий до 10 слов.", True),
                ("Длинный", "Напиши развернутый и подробный комментарий.", True),
                ("Дружелюбный", "Напиши очень дружелюбный и позитивный комментарий.", True),
                ("Провокационный", "Напиши провокационный комментарий, вызывающий дискуссию.", True),
                ("Интимный", "Напиши легкий флирт или комплимент автору.", True)
            ]
            await db.executemany(
                "INSERT INTO prompts (name, text, is_default) VALUES (?, ?, ?)",
                defaults
            )
            await db.commit()

# --- Статистика ---

async def get_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        # Общая статистика
        cursor = await db.execute("SELECT count(*) FROM comments_log")
        total_comments = (await cursor.fetchone())[0]
        
        # По аккаунтам
        cursor = await db.execute(
            "SELECT session_name, comments_count, status FROM accounts"
        )
        accounts_stats = await cursor.fetchall()
        
        return total_comments, accounts_stats

async def log_comment(account_id, channel_username, post_id, text):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO comments_log (account_id, channel_username, post_id, comment_text) VALUES (?, ?, ?, ?)",
            (account_id, channel_username, post_id, text)
        )
        await db.commit()