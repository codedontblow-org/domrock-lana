from app.core.config import get_ai_model
from app.tools.query_tool.tool import consultar_banco
from app.tools.regra_tool.tool import registrar_parametros_regra
from typing import TypedDict, Annotated
from langchain.messages import HumanMessage
from langgraph.graph.message import add_messages
from langchain_openrouter import ChatOpenRouter

# Iniciando o Estado do agente
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# Compilando as Tools
lana_tools = [consultar_banco, registrar_parametros_regra]

# Exportando o modelo com Tools
lana_agent = get_ai_model(ferramentas=lana_tools)