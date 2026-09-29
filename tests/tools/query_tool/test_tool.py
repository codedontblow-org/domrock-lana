from unittest.mock import patch
from app.tools.query_tool.dtos import QueryResponseBody
from app.tools.query_tool.tool import consultar_banco

def test_consultar_banco_repassa_pergunta_e_devolve_resposta() -> None:    

    retorno_esperado = QueryResponseBody(
        status="sucesso", 
        sql_gerado="SELECT 1", 
        dados=[{"total": 1}],
        mensagem="Sucesso.",
        motivo=None,
        erro=None
    )
    
    # CORREÇÃO AQUI: Deve ser uma string apontando para o módulo onde 'executar' foi importado (tool.py)
    with patch("app.tools.query_tool.tool.executar", return_value=retorno_esperado) as mock_executar:
        resposta = consultar_banco.invoke({"pergunta": "Quantas vendas em outubro?"})
        
        mock_executar.assert_called_once()
        body_recebido = mock_executar.call_args[0][0]
        assert body_recebido.pergunta == "Quantas vendas em outubro?"

        assert resposta["status"] == "sucesso"
        assert resposta["dados"] == [{"total": 1}]