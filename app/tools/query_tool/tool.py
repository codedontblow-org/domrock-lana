from langchain_core.tools import tool
from app.tools.query_tool.dtos import QueryRequestBody
from app.tools.query_tool.service import executar

@tool
def consultar_banco(pergunta: str) -> dict:
    """
    Consulta métricas, vendas e funcionários da empresa convertendo linguagem natural em SQL.

    DIRETRIZES DE USO PARA O AGENTE:
    1. Envie a pergunta de forma clara. A ferramenta irá gerar o SQL e retornar os dados.
    2. ANALISE O STATUS DE RETORNO:
       - Se "sucesso": Use os 'dados' para responder ao usuário.
       - Se "erro_execucao" ou "bloqueado": Leia o campo 'erro'. Ele conterá a falha do banco (ex: coluna inexistente). REFORMULE a sua 'pergunta' para contornar o erro e chame a ferramenta novamente.
       - Se "recusado": Informe ao usuário o que está no campo 'motivo'.
    
    Args:
        pergunta: Pergunta clara e detalhada sobre o que deseja buscar.
    """
    body = QueryRequestBody(pergunta=pergunta)
    return executar(body).model_dump()