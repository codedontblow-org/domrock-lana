import asyncio
import json
import time
import traceback
from collections.abc import Callable
from typing import Any

import grpc

from app.agent.router import limite_de_cota, MENSAGEM_COTA
from app.agent.service import lana_invoke
from app.proto import ia_service_pb2, ia_service_pb2_grpc
from app.agent.guardrails import classificar_guardrail, obter_resposta_guardrail

# Mesma assinatura de lana_invoke: (chat_id, mensagem, ficha do painel) -> turno do agente.
InvocarAgente = Callable[[str, str, dict[str, Any] | None], dict[str, Any]]


class IAServiceServicer(ia_service_pb2_grpc.IAServiceServicer):

    def __init__(self, invocar: InvocarAgente = lana_invoke) -> None:
        self._invocar = invocar

    async def InvokeAgent(self, request, context):
        print(f"Recebido | chat={request.chat_id} | prompt={request.prompt!r}", flush=True)
        inicio = time.perf_counter()

        # Guardrail de entrada (custo zero de tokens)
        tipo = classificar_guardrail(request.prompt)
        print(f"Guardrail: {tipo} | chat={request.chat_id}", flush=True)
        if tipo:
            resposta = obter_resposta_guardrail(tipo)
            if resposta:
                print(f"Respondido pelo guardrail em {time.perf_counter() - inicio:.3f}s", flush=True)
                return ia_service_pb2.InvokeResponse(resposta=resposta)

        try:
            regra = ler_regra(request.regra_json)
            resultado = await asyncio.wait_for(
                asyncio.to_thread(self._invocar, request.chat_id, request.prompt, regra),
                timeout=100,
            )
            print(f"Respondido em {time.perf_counter() - inicio:.1f}s", flush=True)
            return montar_resposta(resultado)

        except asyncio.TimeoutError:
            print(f"Lana passou de 100s (chat={request.chat_id})", flush=True)
            await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "A Lana demorou demais para responder.")
        except Exception as e:
            traceback.print_exc()
            if limite_de_cota(e):
                await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, MENSAGEM_COTA)
            await context.abort(grpc.StatusCode.INTERNAL, f"Erro no agente: {e}")


def ler_regra(regra_json: str) -> dict[str, Any] | None:
    """Ficha do painel que o backend manda (com as edições do usuário); vazio = sem ficha.

    Ex.: ler_regra('{"rule_id": "bf-1", "parametros": []}')["rule_id"] -> "bf-1"
    """
    if not regra_json:
        return None
    try:
        return json.loads(regra_json)
    except json.JSONDecodeError as erro:
        raise ValueError(f"regra_json inválido, esperado o objeto JSON da ficha: {regra_json[:200]!r}") from erro


def montar_resposta(turno: dict[str, Any]) -> ia_service_pb2.InvokeResponse:
    """Texto, eventos e ficha do turno. Eventos e ficha viajam como JSON, porque o .proto os leva como string.

    Ex.: montar_resposta({"response": "oi", "events": [], "regra": None}).regra_json -> ""
    """
    regra = turno.get("regra")
    return ia_service_pb2.InvokeResponse(
        resposta=turno["response"],
        events_json=json.dumps(turno.get("events", []), ensure_ascii=False, default=str),
        regra_json=json.dumps(regra, ensure_ascii=False) if regra is not None else "",
    )
