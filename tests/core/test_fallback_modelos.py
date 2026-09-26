import os

os.environ.setdefault("AI_PROVIDER", "GEMINI")
os.environ.setdefault("AI_MODEL", "fake-model")

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.core import config


class FakeModeloSemCota(FakeListChatModel):
    """Simula o Gemini com a cota estourada (429)."""

    def invoke(self, *args, **kwargs):  # type: ignore[override]
        raise RuntimeError("429 RESOURCE_EXHAUSTED")


def _configurar(monkeypatch: pytest.MonkeyPatch, fallbacks: str, chaves: dict[str, str | None]) -> None:
    monkeypatch.setattr(config.ENV, "AI_PROVIDER", "GEMINI")
    monkeypatch.setattr(config.ENV, "AI_MODEL", "gemini-principal")
    monkeypatch.setattr(config.ENV, "AI_FALLBACKS", fallbacks)
    for provedor, chave in chaves.items():
        monkeypatch.setattr(config.ENV, f"{provedor}_API_KEY", chave)


def test_ler_fallbacks_aceita_modelo_com_dois_pontos() -> None:
    assert config.ler_fallbacks("OPENROUTER:meta-llama/llama:free, groq:llama-x") == [
        ("OPENROUTER", "meta-llama/llama:free"), ("GROQ", "llama-x"),
    ]


def test_ler_fallbacks_recusa_item_sem_provedor() -> None:
    with pytest.raises(ValueError, match="gemini-sem-provedor"):
        config.ler_fallbacks("gemini-sem-provedor")


def test_modelos_configurados_pula_provedor_sem_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    _configurar(monkeypatch, "GEMINI:gemini-reserva,OPENROUTER:or-x,GROQ:groq-x",
                {"GEMINI": "g", "OPENROUTER": None, "GROQ": "q"})

    assert config.modelos_configurados() == [
        ("GEMINI", "gemini-principal"), ("GEMINI", "gemini-reserva"), ("GROQ", "groq-x"),
    ]


def test_get_ai_model_cai_para_o_proximo_quando_o_principal_estoura_a_cota(monkeypatch: pytest.MonkeyPatch) -> None:
    _configurar(monkeypatch, "GROQ:groq-x", {"GEMINI": "g", "OPENROUTER": None, "GROQ": "q"})
    modelos = {
        "gemini-principal": FakeModeloSemCota(responses=["nunca"]),
        "groq-x": FakeListChatModel(responses=["resposta do groq"]),
    }
    monkeypatch.setattr(config, "_construir_modelo", lambda provedor, modelo: modelos[modelo])

    resposta = config.get_ai_model().invoke("oi")

    assert resposta.content == "resposta do groq"
