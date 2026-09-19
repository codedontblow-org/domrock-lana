from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from google import genai

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    OPENROUTER_API_KEY: str | None = None
    PORT: int = 8000
    DATABASE_SQLITE_URL: str = "vendas.db"
    # BACKEND_URL: str = "http://localhost:8080"
    # DATABASE_URL: str = ""

    model_config = SettingsConfigDict(
        
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

ENV = get_settings()

def get_gemini_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(api_key=settings.GEMINI_API_KEY)