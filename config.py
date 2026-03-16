from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    ADMIN_ID: int = int(os.getenv("ADMIN_ID", 0))
    
    # Настройки БД
    DB_URL: str = "sqlite+aiosqlite:///./bot_database.db"

settings = Settings()