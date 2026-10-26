import json
from uuid import uuid4
from langchain_core.messages import AIMessage, ToolMessage

from app.agent.callbacks import ToolEventsCallbackHandler
from app.agent.router import AgentEvents, AgentResponse
from app.agent.service import get_events


def test_get_events_formata_campos_unificados() -> None:
    ai_msg = AIMessage(
        content="Consultando os vendedores de loja com maior percentual.",
        tool_calls=[{"name": "consultar_banco", "args": {"pergunta": "top vendedores"}, "id": "call-123"}]
    )
    tool_msg = ToolMessage(
        content=json.dumps({
            "situacao": "ok",
            "tempo": 36,
            "tabelas": ["venda", "funcionario"],
            "competencias": ["2025-11"],
            "filtros": "cod_loja = 10",
            "registros": 5,
            "sql": "SELECT * FROM venda WHERE cod_loja = 10",
            "status": "sucesso",
            "dados": [{"id": 1}],
        }),
        name="consultar_banco",
        tool_call_id="call-123"
    )

    eventos = get_events([ai_msg, tool_msg])

    assert len(eventos) == 1
    ev = eventos[0]
    assert ev["descricao_legivel"] == "Consultando os vendedores de loja com maior percentual."
    assert ev["ferramenta"] == "consultar_banco"
    assert ev["tempo"] == 36
    assert isinstance(ev["tempo"], int)
    assert ev["tabelas"] == ["venda", "funcionario"]
    assert ev["competencias"] == ["2025-11"]
    assert ev["filtros"] == "cod_loja = 10"
    assert ev["registros"] == 5
    assert ev["sql"] == "SELECT * FROM venda WHERE cod_loja = 10"
    assert ev["situacao"] == "ok"
    assert ev["args"] == {"pergunta": "top vendedores"}

    # Valida no Pydantic DTO AgentResponse
    resp = AgentResponse(chat_id="chat-1", response="Aqui está", events=eventos)
    assert len(resp.events) == 1
    assert resp.events[0].descricao_legivel == "Consultando os vendedores de loja com maior percentual."
    assert resp.events[0].tempo == 36
    assert isinstance(resp.events[0].tempo, int)
    assert resp.events[0].situacao == "ok"
    assert resp.events[0].tabelas == ["venda", "funcionario"]
    assert resp.events[0].competencias == ["2025-11"]
    assert resp.events[0].filtros == "cod_loja = 10"
    assert resp.events[0].registros == 5
    assert resp.events[0].sql == "SELECT * FROM venda WHERE cod_loja = 10"


def test_get_events_trata_erro_amigavel() -> None:
    ai_msg = AIMessage(
        content="Consultando dados inexistentes.",
        tool_calls=[{"name": "consultar_banco", "args": {"pergunta": "qualquer coisa"}, "id": "call-456"}]
    )
    tool_msg = ToolMessage(
        content=json.dumps({
            "situacao": "erro: dado inexistente no banco",
            "tempo": 12,
            "tabelas": [],
            "competencias": [],
            "filtros": None,
            "registros": 0,
            "sql": None,
            "status": "recusado",
        }),
        name="consultar_banco",
        tool_call_id="call-456"
    )

    eventos = get_events([ai_msg, tool_msg])
    assert eventos[0]["situacao"] == "erro: dado inexistente no banco"
    assert eventos[0]["registros"] == 0
    assert eventos[0]["tempo"] == 12
    assert isinstance(eventos[0]["tempo"], int)


def test_callback_handler_registra_eventos() -> None:
    handler = ToolEventsCallbackHandler()
    run_id = uuid4()

    handler.on_tool_start({"name": "consultar_banco"}, "qual a venda", run_id=run_id)
    handler.on_tool_end(
        json.dumps({
            "situacao": "ok",
            "tempo": 25,
            "tabelas": ["venda"],
            "registros": 10,
        }),
        name="consultar_banco",
        run_id=run_id,
    )

    assert len(handler.events) == 1
    assert handler.events[0]["ferramenta"] == "consultar_banco"
    assert isinstance(handler.events[0]["tempo"], int)
    assert handler.events[0]["situacao"] == "ok"
    assert handler.events[0]["tabelas"] == ["venda"]
    assert handler.events[0]["registros"] == 10


def test_get_events_faz_parse_de_string_com_decimal_e_aspas_simples() -> None:
    # Simula exatamente a saída gerada quando o resultado contém Decimal e aspas simples
    conteudo_com_decimal = (
        "{'situacao': 'ok', 'tempo': 1145, 'tabelas': ['funcionario_loja', 'loja', 'marca', 'venda'], "
        "'competencias': ['2025-07', '2025-12'], 'filtros': \"t1.date_ref BETWEEN '2025-07-01' AND '2025-12-31'\", "
        "'registros': 5, 'sql': 'SELECT 1', "
        "'dados': [{'descr_marca': 'AZUL', 'valor_total_vendas': Decimal('328484.74')}], "
        "'motivo': None, 'erro': None}"
    )

    ai_msg = AIMessage(content="Consultando marcas.", tool_calls=[{"name": "consultar_banco", "args": {}, "id": "call-dec"}])
    tool_msg = ToolMessage(content=conteudo_com_decimal, name="consultar_banco", tool_call_id="call-dec")

    eventos = get_events([ai_msg, tool_msg])
    assert len(eventos) == 1
    ev = eventos[0]
    assert isinstance(ev["result"], dict)
    assert ev["tempo"] == 1145
    assert ev["situacao"] == "ok"
    assert ev["tabelas"] == ["funcionario_loja", "loja", "marca", "venda"]
    assert ev["competencias"] == ["2025-07", "2025-12"]
    assert ev["registros"] == 5
    assert ev["result"]["dados"][0]["valor_total_vendas"] == 328484.74


def test_get_events_usa_a_explicacao_da_chamada_e_nao_o_texto_da_resposta() -> None:
    # A6-70: com o reasoning no argumento `explicacao`, ele sempre vem e não depende do texto da IA.
    ai_msg = AIMessage(
        content="",
        tool_calls=[{
            "name": "consultar_banco", "id": "call-exp",
            "args": {"pergunta": "venda da marca 30 em out/2025", "explicacao": "Consultando as vendas da marca 30 em outubro de 2025"},
        }],
    )
    tool_msg = ToolMessage(content=json.dumps({"situacao": "ok", "tempo": 10}), name="consultar_banco", tool_call_id="call-exp")

    eventos = get_events([ai_msg, tool_msg])

    assert eventos[0]["descricao_legivel"] == "Consultando as vendas da marca 30 em outubro de 2025"
