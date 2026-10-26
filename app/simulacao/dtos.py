from pydantic import BaseModel, Field

from app.core.trilha import PassoTrilha
from app.simulacao.vigencia import CampanhaDoSistema, ComissaoPeriodo, ConflitoCampanha, HistoricoComissao

from app.tools.regra_tool.dtos import RegraCampanha


class SimulacaoRequest(BaseModel):
    chat_id: str | None = None
    regra: RegraCampanha
    # Contrato 4.3: só as versões salvas no sistema; as da especificação a Lana carrega sozinha.
    campanhas: list[CampanhaDoSistema] = Field(default_factory=list)


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
    # Venda do período − meta (A6-72): positivo = acima da meta, negativo = abaixo.
    diferenca: float


class RetornoCampanha(BaseModel):
    """Retorno da campanha pela conta provisória do A6-72 (ADR-004), até a Dom Rock definir "retorno".

    Vai no resultado, mas a tela e a explicação só o usam na Sprint 3 (decisão do PO, 26/10).

    `custo_pct_venda`: custo adicional ÷ venda do período × 100; None sem venda no período.
    `custo_por_real_acima_meta`: custo adicional ÷ (venda − meta); None se a venda não passou da meta.
    """

    provisorio: bool = True
    custo_pct_venda: float | None
    custo_por_real_acima_meta: float | None


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
    `cabe_no_orcamento` é None quando a ficha não tem orçamento (A6-72).
    """

    tipo: str
    titulo: str
    pct_acrescimo: float
    marcas_alvo: list[str]
    custo_incremental: float
    economia: float
    cabe_no_orcamento: bool | None


class TrilhaSimulacao(BaseModel):
    """Trilha da simulação (2.2). Preenchido com modelo, tentativas, premissas, passos (A6-70) e campanhas (A6-74)."""

    modelo: str = ""
    tentativas: int = 1
    premissas: list[str] = Field(default_factory=list)
    passos: list[PassoTrilha] = Field(default_factory=list)
    campanhas: list[HistoricoComissao] = Field(default_factory=list)


class ResultadoSimulacao(BaseModel):
    rule_id: str
    competencias: list[str]
    totais: TotaisSimulacao
    por_marca: list[QuebraDimensao]
    por_cargo: list[QuebraDimensao]
    # None quando a ficha não tem orçamento (A6-72: orçamento é opcional).
    orcamento: VereditoOrcamento | None
    meta: AtingimentoMeta
    retorno: RetornoCampanha
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
    comissao_periodo: list[ComissaoPeriodo] = Field(default_factory=list)
    conflitos: list[ConflitoCampanha] = Field(default_factory=list)
    trilha: TrilhaSimulacao = Field(default_factory=TrilhaSimulacao)
