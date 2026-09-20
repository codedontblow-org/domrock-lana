from app.agent.state import AgentState, llm

def agent_node(state: AgentState) -> AgentState:
    """This is the AI Agent node"""
    AgentRes = llm.stream(state["messages"])

    # Iterando sob os chunks da resposta da AI
    full = None
    for chunk in AgentRes:
        full = chunk if full is None else full + chunk

        if chunk.content:
            print(chunk.content, end="", flush=True)

    return {"messages": [full]}

def keep_loop(state: AgentState):
    message = state["messages"]
    last_message = message[-1]
    if not last_message.tool_calls:
        return "end"
    else:
        return "loop"