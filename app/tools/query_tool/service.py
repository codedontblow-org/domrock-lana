import logging
import re
from datetime import datetime # NOVO
from functools import lru_cache

from app.core.config import extract_text, get_ai_model
from app.core.db import executar_select
from app.tools.query_tool.dtos import QueryRequestBody, QueryResponseBody
from app.tools.query_tool.guard import LIMITE_LINHAS, SqlInseguro, validar
from app.tools.query_tool.prompts import FULL_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
_CERCA_MARKDOWN = re.compile(r"^```(?:sql)?\s*|\s*```$", re.IGNORECASE)

@lru_cache
def _modelo():
    return get_ai_model()

def _limpar_resposta(texto: str) -> str:
    texto = _CERCA_MARKDOWN.sub("", texto.strip())
    return texto.strip().rstrip(";").strip()

def gerar_sql(pergunta: str) -> tuple[str | None, str | None]:
    data_atual = datetime.now().strftime("%Y-%m-%d")
    prompt_com_contexto = f"HOJE É: {data_atual}\n\n{FULL_SYSTEM_PROMPT}"

    resposta = _modelo().invoke([("system", prompt_com_contexto), ("human", pergunta)])
    texto = _limpar_resposta(extract_text(resposta))

    if texto.upper().startswith("SEM_DADO"):
        motivo = texto[len("SEM_DADO"):].lstrip(": ").strip()
        return None, motivo or "Informação não disponível no schema."

    return texto, None

def executar(body: QueryRequestBody) -> QueryResponseBody:
    try:
        sql, motivo = gerar_sql(body.pergunta)
    except Exception as e:
        logger.exception("Falha ao gerar SQL")
        return QueryResponseBody(
            status="erro_geracao",
            mensagem=f"Falha na geração do SQL: {str(e)}"
        )

    if sql is None:
        return QueryResponseBody(status="recusado", motivo=motivo, mensagem="Dado inexistente no banco.")

    try:
        sql_seguro = validar(sql)
    except SqlInseguro as e:
        logger.warning("SQL bloqueado: %s | sql=%s", e, sql)
        return QueryResponseBody(
            status="bloqueado", 
            sql_gerado=sql, 
            erro=f"O Guard de segurança bloqueou o SQL. Motivo: {e}. Reescreva a query.", 
            mensagem="Consulta bloqueada por segurança."
        )

    try:
        dados = executar_select(sql_seguro)
    except Exception as e:
        logger.exception("Falha ao executar SQL: %s", sql_seguro)
        erro_banco = str(e).split('\n')[0]
        return QueryResponseBody(
            status="erro_execucao",
            sql_gerado=sql_seguro,
            erro=f"Erro do PostgreSQL: {erro_banco}. Corrija a query baseando-se no schema e tente novamente.",
            mensagem="Falha de sintaxe ou execução no banco."
        )

    mensagem = "Sucesso."
    if len(dados) >= LIMITE_LINHAS:
        mensagem += f" Exibindo os primeiros {LIMITE_LINHAS} registros."

    return QueryResponseBody(status="sucesso", sql_gerado=sql_seguro, dados=dados, mensagem=mensagem)