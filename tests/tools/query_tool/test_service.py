from unittest.mock import patch
from app.tools.query_tool.dtos import QueryRequestBody
from app.tools.query_tool.service import executar

@patch("app.tools.query_tool.service.gerar_sql")
@patch("app.tools.query_tool.service.validar")
@patch("app.tools.query_tool.service.executar_select")
def test_executar_retorna_erro_do_banco_para_autocorrecao(
    mock_executar_select, mock_validar, mock_gerar_sql
):
    """
    Garante que se o PostgreSQL lançar uma Exception (ex: coluna errada),
    esse erro seja retornado no status 'erro_execucao' para o agente corrigir.
    """
    body = QueryRequestBody(pergunta="Qual o valor total?")
    
    # Simula a LLM retornando uma query com erro na coluna
    mock_gerar_sql.return_value = ("SELECT valor_total FROM venda", None)
    # Simula o Guard aprovando o SQL sintaticamente
    mock_validar.return_value = "SELECT valor_total FROM venda LIMIT 50"
    
    # Simula o Banco de Dados estourando um erro
    mock_executar_select.side_effect = Exception("column 'valor_total' does not exist\nLINE 1: SELECT...")

    # Executa o service
    resultado = executar(body)
    
    # Verificações
    assert resultado.status == "erro_execucao"
    assert "column 'valor_total' does not exist" in resultado.erro
    assert resultado.sql_gerado == "SELECT valor_total FROM venda LIMIT 50"

@patch("app.tools.query_tool.service.gerar_sql")
@patch("app.tools.query_tool.service.validar")
@patch("app.tools.query_tool.service.executar_select")
def test_executar_sucesso(
    mock_executar_select, mock_validar, mock_gerar_sql
):
    """Garante que uma query válida retorne status 'sucesso' e os dados."""
    body = QueryRequestBody(pergunta="Qual a venda do funcionario 1?")
    
    mock_gerar_sql.return_value = ("SELECT vlr_venda FROM venda WHERE funcionario_id = 1", None)
    mock_validar.return_value = "SELECT vlr_venda FROM venda WHERE funcionario_id = 1 LIMIT 50"
    mock_executar_select.return_value = [{"vlr_venda": 150.0}]

    resultado = executar(body)
    
    assert resultado.status == "sucesso"
    assert resultado.dados == [{"vlr_venda": 150.0}]
    assert resultado.erro is None

@patch("app.tools.query_tool.service.gerar_sql")
def test_executar_retorna_recusado_quando_llm_nao_acha_dados(mock_gerar_sql):
    """Garante que se a LLM responder SEM_DADO, o status seja 'recusado'."""
    body = QueryRequestBody(pergunta="Qual a cor do cabelo do funcionario?")
    
    # Simula a LLM retornando (None, motivo)
    mock_gerar_sql.return_value = (None, "Não há dados sobre cor de cabelo no schema.")

    resultado = executar(body)
    
    assert resultado.status == "recusado"
    assert resultado.motivo == "Não há dados sobre cor de cabelo no schema."
    assert resultado.dados is None

@patch("app.tools.query_tool.service.gerar_sql")
@patch("app.tools.query_tool.service.validar")
def test_executar_retorna_bloqueado_quando_guard_rejeita(mock_validar, mock_gerar_sql):
    """Garante que uma tentativa de injeção seja barrada com status 'bloqueado'."""
    body = QueryRequestBody(pergunta="Delete tudo")
    
    mock_gerar_sql.return_value = ("DELETE FROM venda", None)
    
    # Simula o guard levantando a exceção de segurança
    from app.tools.query_tool.guard import SqlInseguro
    mock_validar.side_effect = SqlInseguro("Comando de escrita encontrado")

    resultado = executar(body)
    
    assert resultado.status == "bloqueado"
    assert "Comando de escrita encontrado" in resultado.erro