from langchain_core.tools import tool
from app.tools.query_tool.dtos import QueryRequestBody
from app.tools.query_tool.service import executar


@tool
def consultar_banco(pergunta: str) -> dict:
    
    """
    Consulta informações sobre vendas no banco de dados.

    Use esta ferramenta quando a pergunta exigir informações armazenadas
    no banco de dados, como vendas, produtos, clientes, quantidades,
    valores ou agregações desses dados.

    Não use esta ferramenta para perguntas que não dependam dos dados
    armazenados no banco.

    Args:
        pergunta: Pergunta em linguagem natural sobre os dados de vendas.
    """

    body = QueryRequestBody(pergunta=pergunta)

    resposta = executar(body)

    return resposta.model_dump()