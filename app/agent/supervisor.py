from app.agent.initialize import AgentState, lana_agent

# Node de invocação do agente
def agent_node(state: AgentState) -> AgentState:
    """This is the AI Agent node"""
    agent_res = lana_agent.invoke(state["messages"])

    return {"messages": [agent_res]}

# Node de decisão de uso de ferramentas e loop ReAct
def keep_loop(state: AgentState):
    message = state["messages"]
    last_message = message[-1]
    if not last_message.tool_calls:
        return "end"
    else:
        return "loop"