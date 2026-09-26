from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from langchain_core.language_models import BaseChatModel
from langchain_openrouter import ChatOpenRouter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from collections.abc import Sequence

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    GEMINI_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    AI_PROVIDER: str
    AI_MODEL: str
    # Cadeia de reserva, em ordem: "PROVEDOR:modelo,PROVEDOR:modelo" (GEMINI, OPENROUTER ou GROQ).
    AI_FALLBACKS: str = ""
    # Tempo máximo por modelo; um provedor lento (ex.: OpenRouter gratuito) passa a vez ao próximo.
    AI_TIMEOUT_S: float = 30
    PORT: int = 8000
    DATABASE_URL: str = ""
    # "llm" gera o código da regra com a IA (A6-37); "modelo" usa o código fixo (plano B da demo).
    CODEGEN_MODO: str = "llm"
    # BACKEND_URL: str = ""

    model_config = SettingsConfigDict(
        
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    return Settings()

ENV = get_settings()

def get_ai_model(ferramentas: Sequence[BaseTool] | None = None) -> Runnable:
    """Modelo principal com a cadeia de fallback (AI_PROVIDER/AI_MODEL, depois AI_FALLBACKS).

    Se o principal falhar (ex.: 429 de cota do Gemini), a mesma chamada vai para o próximo
    da cadeia. Provedores sem chave no .env ficam de fora.
    Ex.: get_ai_model(ferramentas=[consultar_banco]).invoke(mensagens)
    """
    modelos = [_com_ferramentas(_construir_modelo(p, m), ferramentas) for p, m in modelos_configurados()]
    if not modelos:
        raise ValueError(
            f"Nenhum modelo com chave configurada; AI_PROVIDER={ENV.AI_PROVIDER!r}, "
            f"AI_FALLBACKS={ENV.AI_FALLBACKS!r}"
        )
    principal, *reservas = modelos
    return principal.with_fallbacks(reservas) if reservas else principal


def modelos_configurados() -> list[tuple[str, str]]:
    """Ex.: AI_FALLBACKS="GEMINI:gemini-3.1-flash-lite,GROQ:llama" -> [(GEMINI, ...), ...]"""
    cadeia = [(ENV.AI_PROVIDER, ENV.AI_MODEL), *ler_fallbacks(ENV.AI_FALLBACKS)]
    return [(provedor, modelo) for provedor, modelo in cadeia if _chave(provedor)]


def ler_fallbacks(texto: str) -> list[tuple[str, str]]:
    # split(":", 1): nomes do OpenRouter têm ":" (ex.: "meta-llama/llama-3.3-70b-instruct:free").
    itens = [item.strip() for item in texto.split(",") if item.strip()]
    pares = [item.split(":", 1) for item in itens]
    invalidos = [item for item, par in zip(itens, pares) if len(par) != 2]
    if invalidos:
        raise ValueError(f"AI_FALLBACKS inválido: {invalidos}; esperado PROVEDOR:modelo separados por vírgula")
    return [(provedor.strip().upper(), modelo.strip()) for provedor, modelo in pares]


def _chave(provedor: str) -> str | None:
    return {
        "GEMINI": ENV.GEMINI_API_KEY,
        "OPENROUTER": ENV.OPENROUTER_API_KEY,
        "GROQ": ENV.GROQ_API_KEY,
    }.get(provedor)


def _construir_modelo(provedor: str, modelo: str) -> BaseChatModel:
    # Poucas retentativas internas: numa cota estourada, é melhor passar logo para o fallback.
    comum = {
        "model": modelo, "api_key": _chave(provedor), "temperature": 0, "max_retries": 1,
        "timeout": ENV.AI_TIMEOUT_S,
    }
    if provedor == "GEMINI":
        return ChatGoogleGenerativeAI(**comum)
    if provedor == "OPENROUTER":
        # No SDK do OpenRouter o timeout é em milissegundos e cada retentativa pode esperar até 150 s.
        return ChatOpenRouter(**{**comum, "timeout": int(ENV.AI_TIMEOUT_S * 1000), "max_retries": 0})
    if provedor == "GROQ":
        return ChatGroq(**comum)
    raise ValueError(f"Provedor de IA não suportado: {provedor!r}; esperado GEMINI, OPENROUTER ou GROQ")


def _com_ferramentas(modelo: BaseChatModel, ferramentas: Sequence[BaseTool] | None) -> Runnable:
    return modelo.bind_tools(ferramentas) if ferramentas else modelo

def extract_text(response) -> str:
    content = response.content

    if isinstance(content, str):
        return content.strip()

    return "".join(
        block["text"]
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ).strip()