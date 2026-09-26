import json

from langchain_core.messages import AIMessage, ToolMessage

from app.tools.regra_tool.tool import NOME_TOOL_REGRA, registrar_parametros_regra


def _chamar(args: dict[str, object]) -> ToolMessage:
    chamada = {"name": NOME_TOOL_REGRA, "args": args, "id": "call-1", "type": "tool_call"}
    return registrar_parametros_regra.invoke(chamada)


def test_tool_devolve_faltantes_para_a_llm_e_contrato_como_artifact() -> None:
    mensagem = _chamar({"comando_original": "+1% na black friday", "pct_acrescimo": 1.0})

    assert json.loads(mensagem.content)["faltantes"][0] == "periodo"
    assert mensagem.artifact["raw_prompt"] == "+1% na black friday"
    assert mensagem.artifact["status"] == "DRAFT_PENDING_REVIEW"


def test_tool_so_monta_periodo_com_as_duas_datas() -> None:
    mensagem = _chamar({"comando_original": "x", "data_inicio": "2025-11-24"})

    periodo = next(p for p in mensagem.artifact["parametros"] if p["key"] == "periodo")
    assert periodo["value"] is None


def test_extrair_regra_pega_o_ultimo_artifact_do_turno() -> None:
    from app.agent.service import extrair_regra

    primeira = _chamar({"comando_original": "a", "pct_acrescimo": 1.0})
    segunda = _chamar({"comando_original": "a", "pct_acrescimo": 2.0})
    turno = [AIMessage("x"), primeira, segunda, AIMessage("fim")]

    regra = extrair_regra(turno)

    assert regra is not None
    assert next(p for p in regra["parametros"] if p["key"] == "pct_acrescimo")["value"] == 2.0
    assert extrair_regra([AIMessage("sem tool")]) is None
