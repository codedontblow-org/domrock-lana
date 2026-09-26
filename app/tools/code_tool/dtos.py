from dataclasses import dataclass

from app.tools.regra_tool.dtos import ParametrosSimulacao


@dataclass(frozen=True)
class ContextoGeracao:
    """O que o gerador recebe: parâmetros confirmados e amostras (formato, nunca as linhas todas)."""

    parametros: ParametrosSimulacao
    competencias: list[str]
    amostras: dict[str, str]


@dataclass(frozen=True)
class CodigoGerado:
    fonte: str
    origem: str  # "llm" | "modelo"
