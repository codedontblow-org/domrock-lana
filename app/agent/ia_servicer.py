import asyncio
import json
import traceback
from collections.abc import Callable
from typing import Any

import grpc

from app.agent.router import limite_de_cota, tempo_esgotado, MENSAGEM_COTA, MENSAGEM_TEMPO
from app.agent.service import lana_invoke
from app.proto import ia_service_pb2, ia_service_pb2_grpc
from app.agent.guardrails import classificar_guardrail, obter_resposta_guardrail

# Mesma assinatura de lana_invoke: (chat_id, mensagem, ficha do painel) -> turno do agente.
InvocarAgente = Callable[[str, str, dict[str, Any] | None], dict[str, Any]]
PAPEIS_VALIDOS = {"usuario", "lana", "sistema"}


class IAServiceServicer(ia_service_pb2_grpc.IAServiceServicer):

    def __init__(self, invocar: InvocarAgente = lana_invoke) -> None:
        self._invocar = invocar

    async def InvokeAgent(self, request, context):
        resposta_guardrail = self._verificar_guardrail(request.prompt)
        if resposta_guardrail:
            return resposta_guardrail
        try:
            return await self._executar_agente(request)
        except asyncio.TimeoutError:
            await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "A Lana demorou demais para responder.")
        except Exception as e:
            await self._tratar_erro(e, context)

    def _verificar_guardrail(self, prompt: str) -> ia_service_pb2.InvokeResponse | None:
        tipo = classificar_guardrail(prompt)
        if not tipo:
            return None
        resposta = obter_resposta_guardrail(tipo)
        return ia_service_pb2.InvokeResponse(resposta=resposta) if resposta else None

    async def _executar_agente(self, request) -> ia_service_pb2.InvokeResponse:
        regra = ler_regra(request.regra_json)
        historico = ler_historico(getattr(request, "historico_json", ""))

        def _chamar():
            try:
                return self._invocar(request.chat_id, request.prompt, regra, historico)
            except TypeError:
                return self._invocar(request.chat_id, request.prompt, regra)

        resultado = await asyncio.wait_for(asyncio.to_thread(_chamar), timeout=100)
        return montar_resposta(resultado)

    async def _tratar_erro(self, e: Exception, context) -> None:
        traceback.print_exc()
        if limite_de_cota(e):
            await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, MENSAGEM_COTA)
        if tempo_esgotado(e):
            await context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, MENSAGEM_TEMPO)
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


def validar_item_historico(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(
            f"item do histórico inválido, esperado objeto com papel e texto; recebido {type(item).__name__}: {item!r}"
        )
    papel = item.get("papel")
    if papel not in PAPEIS_VALIDOS:
        raise ValueError(
            f"item do histórico com papel inválido {papel!r}, esperado 'usuario', 'lana' ou 'sistema': {item!r}"
        )
    return item


def ler_historico(historico_json: str) -> list[dict[str, Any]]:
    """Histórico de mensagens que o backend manda; vazio = sem histórico anterior."""
    if not historico_json:
        return []
    try:
        dados = json.loads(historico_json)
    except json.JSONDecodeError as erro:
        raise ValueError(
            f"historico_json inválido, esperado array JSON de mensagens: {historico_json[:200]!r}"
        ) from erro
    if not isinstance(dados, list):
        raise ValueError(
            f"historico_json inválido, esperado array de mensagens; recebido {type(dados).__name__}: {historico_json[:200]!r}"
        )
    return [validar_item_historico(item) for item in dados]


def montar_resposta(turno: dict[str, Any]) -> ia_service_pb2.InvokeResponse:
    """Texto, eventos, ficha e trilha do turno. Viajam como JSON, porque o .proto os leva como string.

    Ex.: montar_resposta({"response": "oi", "events": [], "regra": None, "trilha": None}).trilha_json -> ""
    """
    return ia_service_pb2.InvokeResponse(
        resposta=turno["response"],
        events_json=json.dumps(turno.get("events", []), ensure_ascii=False, default=str),
        regra_json=_json_ou_vazio(turno.get("regra")),
        trilha_json=_json_ou_vazio(turno.get("trilha")),
    )


def _json_ou_vazio(valor: dict[str, Any] | None) -> str:
    # "" = não veio (contrato 3.3): turno sem ficha nova ou sem ferramenta.
    return json.dumps(valor, ensure_ascii=False, default=str) if valor is not None else ""
