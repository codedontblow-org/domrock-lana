"""Passo da trilha (contrato 2.2), comum ao chat e à simulação.

A trilha é montada pelo código, nunca escrita pela LLM (A6-70): cada campo sai do resultado da
ferramenta ou do passo da simulação.
"""
from typing import Any, Literal

from pydantic import BaseModel, Field

SituacaoPasso = Literal["SUCESSO", "ERRO"]

MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


class PassoTrilha(BaseModel):
    """Um item de `trilha.passos`. Ex.: PassoTrilha(ordem=1, ferramenta="consultar_banco", descricao="...")"""

    ordem: int
    ferramenta: str
    descricao: str
    tabelas_acessadas: list[str] = Field(default_factory=list)
    competencias: list[str] = Field(default_factory=list)
    filtros: str | None = None
    sql_executado: str | None = None
    registros_retornados: int = 0
    dados: list[dict[str, Any]] | None = None
    tempo_ms: int = 0
    situacao: SituacaoPasso = "SUCESSO"
    mensagem_erro: str | None = None


def competencia_por_extenso(competencia: str) -> str:
    """Ex.: competencia_por_extenso("2025-10") -> "out/2025"; fora de YYYY-MM volta igual."""
    ano, _, mes = competencia.partition("-")
    if not (ano.isdigit() and mes.isdigit() and 1 <= int(mes) <= 12):
        return competencia
    return f"{MESES[int(mes) - 1]}/{ano}"


def competencias_por_extenso(competencias: list[str]) -> str:
    """Ex.: competencias_por_extenso(["2025-10", "2025-11"]) -> "out/2025, nov/2025" """
    return ", ".join(competencia_por_extenso(c) for c in competencias)
