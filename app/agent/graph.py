from app.agent.state import AgentState
from app.agent.supervisor import agent_node, keep_loop
from app.tools.query_tool.tool import consultar_banco
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import InMemorySaver

graph = StateGraph(AgentState)
tools = [consultar_banco]

graph.add_node("agent", agent_node)
tool_node = ToolNode(tools=tools)
graph.add_node("tools", tool_node)
graph.set_entry_point("agent")

graph.add_conditional_edges(
    "agent",
    agent_node,
    {
        "loop": "agent",
        "end": END
    }
)

checkpointer = InMemorySaver()

lana = graph.compile(checkpointer=checkpointer)

# Código da CLI alocado temporariamente para fase de testes:
while True:
    print("\nHOMEPAGE")
    thread_id = input("ID da conversa: ").strip()

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    print(f"\nCHAT {thread_id}. | '!q' para voltar.")
    while True:
        user_input = input("\nVocê: ")

        if user_input == "!q":
            break

        print("AI: ", end="")

        lana.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config=config,
        )