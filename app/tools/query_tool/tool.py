from langchain_core.tools import tool

from app.tools.query_tool.dtos import QueryRequestBody
from app.tools.query_tool.service import executar


@tool
def consultar_banco(pergunta: str) -> dict:
    
    """Essa ferramenta consulta o banco de dados para responder perguntas sobre os registros passados de vendas. 
    ARGS:
        pergunta: str. Uma pergunta em linguagem natural e em português. A ferramenta suporta perguntas sobre vendedores, produtos e vendas realizadas. Retornará [SEM_DADO] caso não consiga responder à pergunta com os dados cadastrados.
    """

    body = QueryRequestBody(pergunta=pergunta)

    resposta = executar(body)

    return resposta.model_dump()