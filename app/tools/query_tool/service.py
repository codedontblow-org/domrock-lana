from app.core.db import executar_select
from app.core.config import get_gemini_client
from app.tools.query_tool.guard import validar, SqlInseguro
from app.tools.query_tool.prompts import FULL_SYSTEM_PROMPT
from app.tools.query_tool.dtos import QueryRequestBody, QueryResponseBody

client = get_gemini_client()

def gerar_sql(pergunta: str) -> str | None:
    prompt = f"{FULL_SYSTEM_PROMPT}\n\nPergunta: {pergunta}"
    resposta = client.models.generate_content(model="gemini-3.5-flash-lite", contents=prompt)
    texto = resposta.text.strip()

    if texto.startswith("SEM_DADO"):
        return None

    return texto


def executar(body: QueryRequestBody) -> QueryResponseBody:
    sql = gerar_sql(body.pergunta)

    # 1. Trata a recusa de schema pela LLM
    if sql is None:
        return QueryResponseBody(
            status="recusado",
            mensagem="A informação solicitada não consta no banco de dados.",
        )

    # 2. Validação via Guard
    try:
        sql_seguro = validar(sql)
    except SqlInseguro as e:
        return QueryResponseBody(
            status="bloqueado",
            sql_gerado=sql,
            erro=str(e),
            mensagem="Consulta SQL bloqueada por motivos de segurança.",
        )

    # 3. Execução
    try:
        resultados = executar_select(sql_seguro)
        return QueryResponseBody(
            status="sucesso",
            sql_gerado=sql_seguro,
            dados=resultados,
            mensagem="Consulta executada com sucesso.",
        )
    except Exception as e:
        return QueryResponseBody(
            status="erro_execucao",
            sql_gerado=sql_seguro,
            erro=str(e),
            mensagem="Falha ao executar a consulta no banco de dados.",
        )