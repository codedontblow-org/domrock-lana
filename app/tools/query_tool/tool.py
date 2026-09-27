from langchain_core.tools import tool
from app.tools.query_tool.dtos import QueryRequestBody
from app.tools.query_tool.service import executar


@tool
def consultar_banco(pergunta: str) -> dict:
    """
    Consulta informações de comissionamento de funcionários no banco de dados.

    Use esta ferramenta quando a pergunta exigir informações armazenadas
    no banco de dados, como vendas, funcionários, lojas, marcas, cargos,
    valores ou agregações desses dados.

    Não use esta ferramenta para perguntas que não dependam dos dados
    armazenados no banco, nem para cálculos de comissão já processados
    (ainda não existem no banco — apenas dados brutos de venda).

    Args:
        pergunta: Pergunta em linguagem natural sobre os dados de vendas
            e funcionários.
    """

    body = QueryRequestBody(pergunta=pergunta)

    resposta = executar(body)

    return resposta.model_dump()
