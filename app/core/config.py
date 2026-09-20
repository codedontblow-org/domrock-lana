from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from langchain_core.language_models import BaseChatModel
from langchain_openrouter import ChatOpenRouter
from langchain_google_genai import ChatGoogleGenerativeAI
from google import genai

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    GEMINI_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    AI_PROVIDER: str
    AI_MODEL: str
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

def get_ai_model() -> BaseChatModel:
    provider = ENV.AI_PROVIDER
    model = ENV.AI_MODEL
    if provider == 'GEMINI':
        return ChatGoogleGenerativeAI(
            model=model,
            api_key=ENV.GEMINI_API_KEY
        )

    if provider == 'OPENROUTER':
        return ChatOpenRouter(
            model=model,
            api_key=ENV.OPENROUTER_API_KEY
        )

    raise ValueError(
        f"Provedor de IA não suportado: {provider}"
    )