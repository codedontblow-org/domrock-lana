from pydantic import BaseModel
from typing import Any

class QueryRequestBody(BaseModel):
    pergunta: str

class QueryResponseBody(BaseModel):
    status: str
    sql_gerado: str | None = None
    dados: list[dict[str, Any]] | None = None
    erro: str | None = None
    mensagem: str | None = None