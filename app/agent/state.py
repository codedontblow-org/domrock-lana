from app.core.config import get_ai_model
from typing import TypedDict, Annotated
from langchain.messages import HumanMessage
from langgraph.graph.message import add_messages
from langchain_openrouter import ChatOpenRouter

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

llm = get_ai_model