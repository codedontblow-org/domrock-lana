"""Cenários alternativos calculados por código, nunca estimados pela LLM.

O desafio pede que o sistema "faça uma proposta de um cenário que possa ser mais efetivo".
Como no Synapse (docs/SUGESTAO-ADAPTACAO.md), o percentual que cabe no orçamento sai de
`pct × orçamento / custo` e é simulado de novo; tirar a marca que mais pesa sai direto da
quebra por marca, que é aditiva (a soma das marcas dá o custo total).
"""
import math
from collections.abc import Callable

from app.simulacao.dtos import CenarioAlternativo, QuebraDimensao, VereditoOrcamento
from app.simulacao.texto_humano import NOMES_MARCA
from app.tools.regra_tool.dtos import ParametrosSimulacao

# Recebe parâmetros e devolve o custo extra simulado, ou None se o recálculo falhar.
type SimularCusto = Callable[[ParametrosSimulacao], float | None]

PASSO_PCT = 0.01


def propor_cenarios(
    parametros: ParametrosSimulacao, orcamento: VereditoOrcamento,
    por_marca: list[QuebraDimensao], simular_custo: SimularCusto,
) -> list[CenarioAlternativo]:
    """Ex.: propor_cenarios(parametros, orcamento, por_marca, simular_custo)[0].pct_acrescimo -> 1.26"""
    cenarios = [
        _cenario_percentual(parametros, orcamento, simular_custo),
        _cenario_sem_marca(parametros, orcamento, por_marca),
    ]
    return [cenario for cenario in cenarios if cenario is not None]


def _cenario_percentual(
    parametros: ParametrosSimulacao, orcamento: VereditoOrcamento, simular_custo: SimularCusto,
) -> CenarioAlternativo | None:
    pct = percentual_no_limite(parametros.pct_acrescimo, orcamento.orcamento_limite, orcamento.custo_incremental)
    if pct is None or math.isclose(pct, parametros.pct_acrescimo):
        return None
    # O arredondamento por matrícula pode passar do limite por centavos: recua um passo.
    for candidato in (pct, round(pct - PASSO_PCT, 2)):
        custo = simular_custo(parametros.model_copy(update={"pct_acrescimo": candidato}))
        if candidato > 0 and custo is not None and custo <= orcamento.orcamento_limite:
            return _montar("ajustar_acrescimo", _titulo_percentual(orcamento), candidato, parametros.marcas_alvo, custo, orcamento)
    return None


def percentual_no_limite(pct_atual: float, limite: float, custo: float) -> float | None:
    """Maior % (2 casas, truncado) cujo custo cabe no limite; o custo é proporcional ao %.

    Ex.: percentual_no_limite(1.0, 20000, 23736.14) -> 0.84
    """
    if custo <= 0 or limite <= 0:
        return None
    pct = math.floor(pct_atual * limite / custo * 100) / 100
    return pct if pct > 0 else None


def _titulo_percentual(orcamento: VereditoOrcamento) -> str:
    if orcamento.cabe_no_orcamento:
        return "Maior acréscimo que ainda cabe no orçamento"
    return "Acréscimo menor, dentro do orçamento"


def _cenario_sem_marca(
    parametros: ParametrosSimulacao, orcamento: VereditoOrcamento, por_marca: list[QuebraDimensao],
) -> CenarioAlternativo | None:
    afetadas = [marca for marca in por_marca if marca.diferenca > 0]
    if len(afetadas) < 2:
        return None
    maior = max(afetadas, key=lambda marca: marca.diferenca)
    marcas = [codigo for codigo in parametros.marcas_alvo if codigo != maior.codigo]
    custo = round(orcamento.custo_incremental - maior.diferenca, 2)
    titulo = f"Sem a marca {NOMES_MARCA.get(maior.codigo, maior.codigo)}"
    return _montar("sem_marca", titulo, parametros.pct_acrescimo, marcas, custo, orcamento)


def _montar(
    tipo: str, titulo: str, pct: float, marcas: list[str], custo: float, orcamento: VereditoOrcamento,
) -> CenarioAlternativo:
    return CenarioAlternativo(
        tipo=tipo, titulo=titulo, pct_acrescimo=pct, marcas_alvo=marcas, custo_incremental=custo,
        economia=round(orcamento.custo_incremental - custo, 2),
        cabe_no_orcamento=custo <= orcamento.orcamento_limite,
    )
