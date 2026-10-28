"""Testes de histórico sem estado e regra uma conversa, uma campanha (A6-65)."""
import json
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.prompts import SYSTEM_RULES
from app.agent.service import _converter_historico, _mensagens_de_entrada, lana_invoke


def test_in_memory_saver_removido():
    """Garante que o grafo da Lana é sem estado e não usa InMemorySaver."""
    import app.agent.graph as graph_module
    assert not hasattr(graph_module, "checkpointer"), "checkpointer deve ter sido removido de graph.py"
    assert getattr(graph_module.lana, "checkpointer", None) is None


def test_converter_historico_converte_papeis_corretamente():
    historico = [
        {"papel": "usuario", "texto": "Quero +1%"},
        {"papel": "lana", "texto": "Ficha preenchida", "trilha": {"passos": []}},
        {"papel": "sistema", "texto": "Enviado para análise — v1"},
    ]
    mensagens = _converter_historico(historico)
    assert len(mensagens) == 3
    assert isinstance(mensagens[0], HumanMessage) and mensagens[0].content == "Quero +1%"
    assert isinstance(mensagens[1], AIMessage) and mensagens[1].content == "Ficha preenchida"
    assert isinstance(mensagens[2], HumanMessage)
    assert mensagens[2].content == "[Mensagem do sistema, não do usuário] Enviado para análise — v1"


def test_mensagem_sistema_reprovacao_preserva_posicao_como_human_message():
    historico = [
        {"papel": "usuario", "texto": "Submeti a campanha"},
        {"papel": "sistema", "texto": "Reprovado por Sérgio: meta baixa"},
        {"papel": "usuario", "texto": "Por que reprovou?"},
    ]
    mensagens = _converter_historico(historico)
    assert len(mensagens) == 3
    assert isinstance(mensagens[1], HumanMessage)
    assert mensagens[1].content == "[Mensagem do sistema, não do usuário] Reprovado por Sérgio: meta baixa"


def test_mensagens_de_entrada_monta_contexto_a_partir_do_historico():
    historico_msgs = [HumanMessage(content="anterior"), AIMessage(content="resposta anterior")]
    entrada = _mensagens_de_entrada("mensagem atual", None, historico_msgs)

    # Inicia com as regras de sistema
    assert entrada[:len(SYSTEM_RULES)] == SYSTEM_RULES
    # Segue com as mensagens do histórico
    assert entrada[len(SYSTEM_RULES):len(SYSTEM_RULES) + 2] == historico_msgs
    # Termina com a mensagem atual
    assert entrada[-1].content == "mensagem atual"


def test_lana_responde_usando_historico_sem_estado():
    """Simula a chamada de lana_invoke onde a Lana recebe o histórico explicitamente."""
    historico = [
        {"papel": "usuario", "texto": "Vamos criar a campanha Black Friday"},
        {"papel": "lana", "texto": "Qual o percentual desejado?"},
    ]

    mock_response = AIMessage(content="Perfeito, registrei +1% para a Black Friday.")
    with patch("app.agent.service.lana.invoke") as mock_invoke:
        mock_invoke.return_value = {
            "messages": [
                *SYSTEM_RULES,
                HumanMessage(content="Vamos criar a campanha Black Friday"),
                AIMessage(content="Qual o percentual desejado?"),
                HumanMessage(content="+1%"),
                mock_response,
            ]
        }
        resultado = lana_invoke("chat-123", "+1%", None, historico)

        assert resultado["chat_id"] == "chat-123"
        assert resultado["response"] == "Perfeito, registrei +1% para a Black Friday."
        # Confere que o mock recebeu as mensagens do histórico na entrada
        chamada_messages = mock_invoke.call_args[0][0]["messages"]
        textos = [m.content for m in chamada_messages if isinstance(m, (HumanMessage, AIMessage))]
        assert "Vamos criar a campanha Black Friday" in textos
        assert "Qual o percentual desejado?" in textos
        assert "+1%" in textos


def test_regra_uma_conversa_uma_campanha_no_prompt():
    """Garante que SYSTEM_RULES inclui a regra 'uma conversa, uma campanha' orientando nova conversa."""
    textos_regras = [r.content for r in SYSTEM_RULES]
    regra_encontrada = any(
        "uma conversa, uma campanha" in texto.lower() and "nova conversa" in texto.lower()
        for texto in textos_regras
    )
    assert regra_encontrada, "SYSTEM_RULES deve conter a regra 'uma conversa, uma campanha' sugerindo abrir nova conversa"
