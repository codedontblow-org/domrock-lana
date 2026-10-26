"""InvokeAgent (gRPC): a ficha e os eventos do turno precisam chegar ao backend, e a ficha do painel ao agente.

Regressão: no merge do gRPC (lana #5) o servicer devolvia só o texto e passava None como ficha; o painel do
front nunca abria, porque o backend recebia regra vazia.
"""
import asyncio
import json
from typing import Any

import pytest

from app.agent.ia_servicer import IAServiceServicer, ler_regra, montar_resposta
from app.proto import ia_service_pb2

REGRA = {"rule_id": "bf-1", "parametros": [{"key": "pct_acrescimo", "value": 1.0}], "faltantes": []}
EVENTOS = [{"type": "tool_call", "tool": "registrar_parametros_regra", "args": {"pct_acrescimo": 1.0}}]


class AgenteFalso:
    """Faz as vezes do lana_invoke: guarda cada pedido e devolve um turno pronto, sem LLM."""

    def __init__(self, turno: dict[str, Any]) -> None:
        self.turno = turno
        self.pedidos: list[tuple[str, str, dict[str, Any] | None]] = []

    def __call__(self, chat_id: str, mensagem: str, regra: dict[str, Any] | None) -> dict[str, Any]:
        self.pedidos.append((chat_id, mensagem, regra))
        return self.turno


class ContextoFalso:
    """Contexto do gRPC: abort encerra a chamada, como no servidor real."""

    async def abort(self, codigo: object, detalhe: str) -> None:
        raise RuntimeError(f"{codigo}: {detalhe}")


def invocar(agente: AgenteFalso, pedido: ia_service_pb2.InvokeRequest) -> ia_service_pb2.InvokeResponse:
    return asyncio.run(IAServiceServicer(agente).InvokeAgent(pedido, ContextoFalso()))


def test_devolve_ficha_e_eventos_do_turno_como_json() -> None:
    agente = AgenteFalso({"chat_id": "c1", "response": "Registrei a campanha.", "events": EVENTOS, "regra": REGRA})

    resposta = invocar(agente, ia_service_pb2.InvokeRequest(prompt="Black Friday +1%", chat_id="c1"))

    assert resposta.resposta == "Registrei a campanha."
    assert json.loads(resposta.regra_json) == REGRA
    assert json.loads(resposta.events_json) == EVENTOS


def test_repassa_ao_agente_a_ficha_editada_no_painel() -> None:
    agente = AgenteFalso({"chat_id": "c1", "response": "Ajustei.", "events": [], "regra": None})

    invocar(agente, ia_service_pb2.InvokeRequest(prompt="mude para 2%", chat_id="c1", regra_json=json.dumps(REGRA)))

    assert agente.pedidos == [("c1", "mude para 2%", REGRA)]


def test_turno_sem_ficha_nova_devolve_regra_json_vazio() -> None:
    resposta = montar_resposta({"response": "A marca 30 vendeu R$ 333.666,01.", "events": [], "regra": None})

    assert resposta.regra_json == ""
    assert json.loads(resposta.events_json) == []


def test_sem_ficha_do_painel_o_agente_recebe_none() -> None:
    assert ler_regra("") is None


def test_ficha_invalida_mostra_o_que_chegou() -> None:
    with pytest.raises(ValueError, match=r"regra_json inválido.*\{quebrado"):
        ler_regra("{quebrado")


def test_trilha_do_turno_vai_em_trilha_json() -> None:
    trilha = {"modelo": "m", "tentativas": None, "premissas": [], "passos": [{"ordem": 1, "ferramenta": "consultar_banco"}]}

    resposta = montar_resposta({"response": "ok", "events": [], "regra": None, "trilha": trilha})

    assert json.loads(resposta.trilha_json) == trilha


def test_turno_sem_ferramenta_devolve_trilha_json_vazio() -> None:
    assert montar_resposta({"response": "Posso simular campanhas.", "events": [], "regra": None}).trilha_json == ""
