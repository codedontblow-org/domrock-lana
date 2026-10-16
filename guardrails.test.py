from app.agent.guardrails import classificar_guardrail, obter_resposta_guardrail

casos = [
    "oi lana",
    "oi lana, tudo bem?",
    "oi lana, pode me ajudar com uma campanha?",
    "oi lana, como calcular comissao do vendedor X?",
    "e ai lana, me diz as vendas de julho",
]
for t in casos:
    print(f"{t!r:55} -> {classificar_guardrail(t)}")