from typing import Any, Literal
from pydantic import BaseModel, Field

StatusConsulta = Literal["sucesso", "recusado", "bloqueado", "erro_geracao", "erro_execucao"]

class QueryRequestBody(BaseModel):
    pergunta: str = Field(min_length=3, max_length=500) 

class QueryResponseBody(BaseModel):
    status: StatusConsulta
    mensagem: str
    sql_gerado: str | None = None
    dados: list[dict[str, Any]] | None = None
    motivo: str | None = None  
    erro: str | None = None  