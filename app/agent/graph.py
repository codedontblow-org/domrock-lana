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

# Código da CLI alocado nesse arquivo temporariamente para fase de testes:
def print_stream(stream):
    for s in stream:
        message = s["messages"][-1]
        if isinstance(message, tuple):
            print(message)
        else:
            message.pretty_print()

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

        print_stream(lana.stream(
            {"messages": [{"role": "user", "content": user_input}]},
            stream_mode="values",
            config=config,
        ))