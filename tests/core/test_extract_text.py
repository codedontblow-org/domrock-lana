"""Regressão: com Gemini 3.x o `content` da resposta vem como lista de blocos e
`POST /agent/invoke` falhava com ResponseValidationError ao devolvê-lo cru."""
import os

os.environ.setdefault("AI_PROVIDER", "GEMINI")
os.environ.setdefault("AI_MODEL", "fake-model")

from langchain_core.messages import AIMessage

from app.core.config import extract_text


def test_extract_text_junta_blocos_de_texto_e_ignora_assinatura() -> None:
    resposta = AIMessage(content=[
        {"type": "text", "text": "Total: R$ 10,00.", "extras": {"signature": "abc"}},
    ])

    assert extract_text(resposta) == "Total: R$ 10,00."


def test_extract_text_mantem_content_em_string() -> None:
    assert extract_text(AIMessage(content="  olá  ")) == "olá"
