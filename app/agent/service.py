from app.agent.graph import lana

# Função de coleta de eventos da AI
def get_events(messages):
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
                "result": m.content,
            })

    return events


# Função para invocar o grafo via requisição HTTP
def lana_invoke(thread_id: str, user_input: str):     
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    
    result = agent_response = lana.invoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config=config,
    )

    messages = result["messages"]

    events = get_events(messages)

    agent_response = messages[-1]

    return {
        "chat_id": thread_id,
        "response": agent_response.content,
        "events": events,
    }