from datetime import date
from typing import Any

from pydantic import BaseModel


class OpcaoParametro(BaseModel):
    id: str
    label: str


class ParametroRegra(BaseModel):
    """Um campo da regra no formato do contrato compartilhado com front e back."""

    key: str
    label: str
    type: str
    categoria: str
    value: Any = None
    options: list[OpcaoParametro] | None = None
    required: bool = True


class RegraCampanha(BaseModel):
    """Contrato da regra (estrutura_parametros_regra.txt): é o que o usuário revisa e edita."""

    rule_id: str
    tipo_regra: str = "BONUS_TEMPORARIO"
    raw_prompt: str = ""
    status: str = "DRAFT_PENDING_REVIEW"
    parametros: list[ParametroRegra]
    faltantes: list[str] = []


class ParametrosSimulacao(BaseModel):
    """Visão tipada e já validada da regra, usada pelo cálculo e pela geração de código."""

    data_inicio: date
    data_fim: date
    pct_acrescimo: float
    marcas_alvo: list[str]
    cargos_alvo: list[str]
    meta_vendas: float
    orcamento_limite: float
