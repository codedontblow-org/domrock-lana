from pydantic import BaseModel

from app.tools.regra_tool.dtos import RegraCampanha


class SimulacaoRequest(BaseModel):
    chat_id: str | None = None
    regra: RegraCampanha


class TotaisSimulacao(BaseModel):
    baseline: float
    simulado: float
    diferenca: float
    diferenca_pct: float


class QuebraDimensao(BaseModel):
    codigo: str
    baseline: float
    simulado: float
    diferenca: float


class VereditoOrcamento(BaseModel):
    """Custo incremental da campanha (simulado - baseline) contra o orçamento do incentivo."""

    orcamento_limite: float
    custo_incremental: float
    folga: float
    cabe_no_orcamento: bool


class AtingimentoMeta(BaseModel):
    """Venda realizada no período e nas marcas da regra contra a meta informada."""

    meta_vendas: float
    vendas_periodo: float
    pct_atingimento: float
    atingida: bool


class ResultadoSimulacao(BaseModel):
    rule_id: str
    competencias: list[str]
    totais: TotaisSimulacao
    por_marca: list[QuebraDimensao]
    por_cargo: list[QuebraDimensao]
    orcamento: VereditoOrcamento
    meta: AtingimentoMeta
    codigo: str
    origem_codigo: str
    tentativas: int
    explicacao: str
