from app.agent.graph import lana

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