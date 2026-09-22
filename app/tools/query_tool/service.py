from app.core.db import executar_select
from app.core.config import get_ai_model
from app.tools.query_tool.guard import validar, SqlInseguro
from app.tools.query_tool.prompts import FULL_SYSTEM_PROMPT
from app.tools.query_tool.dtos import QueryRequestBody, QueryResponseBody

model = get_ai_model()

def gerar_sql(pergunta: str) -> tuple[str | None, str | None]:
    """Retorna (sql, motivo_recusa). Só um dos dois vem preenchido."""
    prompt = f"{FULL_SYSTEM_PROMPT}\n\nPergunta: {pergunta}"

    print("\n===== PROMPT ENVIADO AO MODELO =====")
    print(prompt)
    print("====================================\n")

    resposta = model.invoke(prompt)

    texto = resposta.content[0]["text"].strip()

    print("\n===== RESPOSTA DO MODELO =====")
    print(texto)
    print("==============================\n")

    if texto.startswith("SEM_DADO"):
        motivo = texto.replace("SEM_DADO:", "", 1).strip()
        return None, motivo

    return texto, None

def executar(body: QueryRequestBody) -> QueryResponseBody:
    sql, motivo = gerar_sql(body.pergunta)

    # 1. Trata a recusa de schema pela LLM
    if sql is None:
        return QueryResponseBody(
            status="recusado",
            motivo=motivo,
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