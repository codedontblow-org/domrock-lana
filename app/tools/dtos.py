import time
from collections.abc import Callable
from functools import wraps
from typing import Any
from pydantic import BaseModel, Field, model_validator


class ToolResultBase(BaseModel):
    """DTO base para padronizar o retorno unificado de todas as ferramentas do agente."""

    situacao: str = Field(
        default="ok",
        description="Situação amigável da ferramenta: 'ok' em caso de sucesso, ou 'erro ao ...'"
    )
    tempo: int = Field(
        default=0,
        description="Duração da execução em milissegundos"
    )
    tabelas: list[str] | None = Field(
        default=None,
        description="Lista de tabelas consultadas no banco de dados"
    )
    competencias: list[str] | None = Field(
        default=None,
        description="Lista de competências consultadas ou afetadas (ex: ['2025-11'])"
    )
    filtros: Any | None = Field(
        default=None,
        description="Filtros aplicados na consulta ou na regra"
    )
    registros: int | None = Field(
        default=None,
        description="Quantidade de registros retornados na consulta"
    )
    sql: str | None = Field(
        default=None,
        description="SQL gerado/executado (quando aplicável)"
    )

    @model_validator(mode="after")
    def _padronizar_metadados(self) -> "ToolResultBase":
        if self.registros is None and hasattr(self, "dados") and getattr(self, "dados") is not None:
            self.registros = len(getattr(self, "dados"))
        if self.sql is None and hasattr(self, "sql_gerado") and getattr(self, "sql_gerado"):
            self.sql = getattr(self, "sql_gerado")
        return self


def calcular_tempo_ms(inicio: float) -> int:
    """Calcula tempo decorrido em ms como inteiro."""
    return int(round((time.perf_counter() - inicio) * 1000))


def medir_tempo(func: Callable) -> Callable:
    """Função/decorador reutilizável para ferramentas que calcula o tempo de execução em ms."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        inicio = time.perf_counter()
        resultado = func(*args, **kwargs)
        duracao = calcular_tempo_ms(inicio)
        if isinstance(resultado, dict):
            resultado.setdefault("tempo", duracao)
        elif hasattr(resultado, "tempo"):
            if getattr(resultado, "tempo", 0) == 0:
                resultado.tempo = duracao
        return resultado
    return wrapper

