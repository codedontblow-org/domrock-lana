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
    """Venda que JÁ aconteceu no período e nas marcas da regra, comparada à meta informada.

    É histórico (backtest), não projeção: a base não permite prever vendas futuras.
    """

    meta_vendas: float
    vendas_periodo: float
    pct_atingimento: float
    atingida: bool


class ImpactoPessoas(BaseModel):
    """Quantas matrículas recebem o acréscimo e quanto, somado no período."""

    pessoas_impactadas: int
    pessoas_total: int
    media_por_pessoa: float
    maior_acrescimo: float


class CenarioAlternativo(BaseModel):
    """Variação da regra já calculada (nunca estimada pela LLM), pronta para aplicar no painel.

    `tipo`: "ajustar_acrescimo" (maior % que cabe no orçamento) ou "sem_marca" (tira a marca
    que mais pesa). `economia` é o custo atual menos o do cenário (negativo = custa mais).
    """

    tipo: str
    titulo: str
    pct_acrescimo: float
    marcas_alvo: list[str]
    custo_incremental: float
    economia: float
    cabe_no_orcamento: bool


class ResultadoSimulacao(BaseModel):
    rule_id: str
    competencias: list[str]
    totais: TotaisSimulacao
    por_marca: list[QuebraDimensao]
    por_cargo: list[QuebraDimensao]
    orcamento: VereditoOrcamento
    meta: AtingimentoMeta
    impacto: ImpactoPessoas
    maiores_lojas: list[QuebraDimensao]
    cenarios: list[CenarioAlternativo]
    ressalvas: list[str]
    codigo: str
    origem_codigo: str
    tentativas: int
    explicacao: str
    # Como o número foi validado (conferido com o cálculo determinístico, ou substituído por ele).
    observacao: str = ""
