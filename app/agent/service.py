from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage

from app.agent.graph import lana
from app.agent.prompts import SYSTEM_RULES
from app.core.config import extract_text
from app.tools.regra_tool.tool import NOME_TOOL_REGRA

# Função de coleta de eventos da AI
def get_events(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    events = []

    for m in messages:

        if hasattr(m, "tool_calls") and m.tool_calls:
            for call in m.tool_calls:
                events.append({
                    "type": "tool_call",
                    "tool": call["name"],
                    "args": call["args"],
                })

        elif m.type == "tool":
            events.append({
                "type": "tool_res",
                "tool": m.name,
                "result": str(m.content),
            })

    return events


def extrair_regra(messages: list[BaseMessage]) -> dict[str, Any] | None:
    """Última regra registrada no turno (artifact da tool de parâmetros), ou None."""
    for m in reversed(messages):
        if isinstance(m, ToolMessage) and m.name == NOME_TOOL_REGRA and m.artifact:
            return m.artifact
    return None


def _mensagens_de_entrada(config: dict[str, Any], user_input: str) -> list[BaseMessage]:
    # As regras de sistema entram só no início do thread; antes eram somadas a cada turno.
    historico = lana.get_state(config).values.get("messages", [])
    if historico:
        return [HumanMessage(user_input)]
    return [*SYSTEM_RULES, HumanMessage(user_input)]


# Função para invocar o grafo via requisição HTTP
def lana_invoke(thread_id: str, user_input: str):
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    tamanho_anterior = len(lana.get_state(config).values.get("messages", []))

    result = lana.invoke(
        {"messages": _mensagens_de_entrada(config, user_input)},
        config=config,
    )

    # Só as mensagens deste turno: o checkpointer devolve o histórico inteiro do thread.
    messages = result["messages"][tamanho_anterior:]

    agent_response = messages[-1]

    return {
        "chat_id": thread_id,
        # Gemini 3.x devolve content como lista de blocos (texto + assinatura), não str.
        "response": extract_text(agent_response),
        "events": get_events(messages),
        "regra": extrair_regra(messages),
    }
