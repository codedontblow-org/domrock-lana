from app.agent.initialize import AgentState
from app.agent.supervisor import agent_node, keep_loop
from app.agent.initialize import lana_tools
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import InMemorySaver

graph = StateGraph(AgentState)

graph.add_node("agent", agent_node)
tool_node = ToolNode(tools=lana_tools)
graph.add_node("tools", tool_node)
graph.set_entry_point("agent")

graph.add_conditional_edges(
    "agent",
    keep_loop,
    {
        "loop": "tools",
        "end": END
    }
)

graph.add_edge("tools", "agent")

checkpointer = InMemorySaver()

lana = graph.compile(checkpointer=checkpointer)