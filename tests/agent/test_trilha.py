"""Trilha do chat (contrato 2.2 e 3.1): montada pelo código a partir das ferramentas do turno.

Regressão A6-70: a descrição de cada passo era o texto que a LLM escrevia antes de chamar a
ferramenta, e esse "pensamento" às vezes vazava como resposta.
"""
import json

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from app.agent.trilha import ler_retorno_da_ferramenta, montar_trilha_chat, texto_dos_filtros

SQL_MARCA_30 = "SELECT COUNT(*) AS qtd_vendas, SUM(v.vlr_venda) AS total FROM venda v WHERE v.date_ref BETWEEN '2025-10-01' AND '2025-10-31' LIMIT 50"
CONSULTA_MARCA_30 = {
    "status": "sucesso", "mensagem": "Sucesso.", "situacao": "ok", "tempo": 340,
    "tabelas": ["loja", "marca", "venda"], "competencias": ["2025-10"],
    "filtros": "m.cod_marca = '30'", "registros": 1, "sql": SQL_MARCA_30,
    "dados": [{"qtd_vendas": 188, "total": 333666.01}],
}
CONSULTA_FALHOU = {
    "status": "erro_execucao", "mensagem": "Falha de sintaxe ou execução no banco.", "situacao": "erro ao consultar banco de dados",
    "tempo": 80, "tabelas": ["venda"], "competencias": [], "filtros": None, "registros": 0, "sql": "SELECT x FROM venda LIMIT 50",
    "erro": "Erro do PostgreSQL: column x does not exist. Corrija a query.",
}


def turno_com_consulta(retorno: dict[str, object], pensamento: str = "") -> list[BaseMessage]:
    """O turno como o LangGraph devolve: pergunta, chamada da ferramenta, retorno e resposta final."""
    chamada = {"name": "consultar_banco", "args": {"pergunta": "venda da marca 30 em out/2025"}, "id": "c1"}
    return [
        HumanMessage("Quanto a marca 30 vendeu em outubro de 2025?"),
        AIMessage(content=pensamento, tool_calls=[chamada]),
        ToolMessage(content=json.dumps(retorno), name="consultar_banco", tool_call_id="c1"),
        AIMessage(content="A marca 30 vendeu R$ 333.666,01.", response_metadata={"model_name": "gemini-3.5-flash-lite"}),
    ]


def test_trilha_da_consulta_mostra_tabela_mes_e_registros() -> None:
    trilha = montar_trilha_chat(turno_com_consulta(CONSULTA_MARCA_30), "modelo-padrao")

    assert trilha is not None and trilha["modelo"] == "gemini-3.5-flash-lite"
    passo = trilha["passos"][0]
    assert passo["ordem"] == 1 and passo["ferramenta"] == "consultar_banco"
    assert passo["descricao"] == "Consulta em loja, marca, venda de out/2025: 1 registro"
    assert "venda" in passo["tabelas_acessadas"] and passo["competencias"] == ["2025-10"]
    assert passo["dados"] == [{"qtd_vendas": 188, "total": 333666.01}]
    assert passo["sql_executado"] == SQL_MARCA_30 and passo["tempo_ms"] == 340
    assert passo["situacao"] == "SUCESSO" and passo["mensagem_erro"] is None


def test_descricao_nunca_vem_do_texto_da_llm() -> None:
    pensamento = "Consultando os vendedores de loja com maior % vigente"

    trilha = montar_trilha_chat(turno_com_consulta(CONSULTA_MARCA_30, pensamento), "m")

    assert trilha is not None
    assert pensamento not in json.dumps(trilha, ensure_ascii=False)


def test_resposta_sem_ferramenta_vem_sem_trilha() -> None:
    turno = [HumanMessage("o que você consegue fazer?"), AIMessage(content="Posso consultar vendas e simular campanhas.")]

    assert montar_trilha_chat(turno, "m") is None


def test_consulta_que_falhou_vira_passo_com_erro() -> None:
    passo = montar_trilha_chat(turno_com_consulta(CONSULTA_FALHOU), "m")["passos"][0]

    assert passo["situacao"] == "ERRO"
    assert passo["descricao"] == "Falha ao executar a consulta no banco"
    assert passo["mensagem_erro"] == "Falha de sintaxe ou execução no banco."
    assert passo["registros_retornados"] == 0 and passo["dados"] is None


def test_ficha_registrada_lista_o_que_falta_pelo_rotulo() -> None:
    retorno = {
        "situacao": "ok", "tempo": 12, "competencias": ["2025-11"], "filtros": {"marcas": ["ALL"], "cargos": None},
        "faltantes": ["meta_vendas"],
        "regra": {"parametros": [{"key": "meta_vendas", "label": "Meta de vendas"}]},
    }
    turno = [
        AIMessage(content="", tool_calls=[{"name": "registrar_parametros_regra", "args": {}, "id": "r1"}]),
        ToolMessage(content=json.dumps(retorno), name="registrar_parametros_regra", tool_call_id="r1"),
    ]

    passo = montar_trilha_chat(turno, "m")["passos"][0]

    assert passo["descricao"] == "Ficha da campanha registrada; falta informar: Meta de vendas"
    assert passo["filtros"] == "marcas: ALL" and passo["tempo_ms"] == 12


def test_chamada_sem_retorno_vira_erro() -> None:
    turno = [AIMessage(content="", tool_calls=[{"name": "consultar_banco", "args": {}, "id": "sem"}])]

    passo = montar_trilha_chat(turno, "m")["passos"][0]

    assert passo["situacao"] == "ERRO" and "sem" in passo["mensagem_erro"]


def test_le_retorno_com_decimal_e_aspas_simples() -> None:
    conteudo = "{'status': 'sucesso', 'dados': [{'total': Decimal('328484.74')}], 'erro': None}"

    assert ler_retorno_da_ferramenta(conteudo)["dados"][0]["total"] == 328484.74


def test_filtros_viram_texto() -> None:
    assert texto_dos_filtros({"marcas": ["10", "30"], "cargos": None, "periodo": "nov"}) == "marcas: 10, 30; periodo: nov"
    assert texto_dos_filtros("") is None
