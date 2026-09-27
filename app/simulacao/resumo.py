"""Números finais da simulação, todos calculados aqui (nenhum vem da LLM)."""
import pandas as pd

from app.simulacao.dtos import AtingimentoMeta, ImpactoPessoas, QuebraDimensao, TotaisSimulacao, VereditoOrcamento
from app.tools.regra_tool.dtos import ParametrosSimulacao

LIMITE_LOJAS = 5

# Limites do método, declarados ao usuário como no Synapse (ESCOPO-SIMULACAO.md §4.2 e §6).
RESSALVAS = [
    "Simulação sobre vendas que já aconteceram: supõe que as pessoas venderiam o mesmo com a regra nova.",
    "A comparação com a comissão atual é o número mais confiável; o total absoluto é apurado por nós, não é a folha oficial.",
    "A comissão atual ainda não aplica proporcional de admissão/demissão nem férias e afastamentos.",
]


def calcular_totais(comparacao: pd.DataFrame) -> TotaisSimulacao:
    baseline = round(float(comparacao["comissao"].sum()), 2)
    simulado = round(float(comparacao["comissao_simulada"].sum()), 2)
    diferenca = round(simulado - baseline, 2)
    pct = round(diferenca / baseline * 100, 2) if baseline else 0.0
    return TotaisSimulacao(baseline=baseline, simulado=simulado, diferenca=diferenca, diferenca_pct=pct)


def quebrar_por(comparacao: pd.DataFrame, coluna: str) -> list[QuebraDimensao]:
    """Ex.: quebrar_por(comparacao, "cod_marca")[0].diferenca"""
    agrupado = comparacao.groupby(coluna, as_index=False)[["comissao", "comissao_simulada"]].sum()
    return [
        QuebraDimensao(
            codigo=str(linha[coluna]),
            baseline=round(float(linha["comissao"]), 2),
            simulado=round(float(linha["comissao_simulada"]), 2),
            diferenca=round(float(linha["comissao_simulada"] - linha["comissao"]), 2),
        )
        for _, linha in agrupado.iterrows()
    ]


def avaliar_orcamento(totais: TotaisSimulacao, orcamento_limite: float) -> VereditoOrcamento:
    folga = round(orcamento_limite - totais.diferenca, 2)
    return VereditoOrcamento(
        orcamento_limite=orcamento_limite, custo_incremental=totais.diferenca,
        folga=folga, cabe_no_orcamento=folga >= 0,
    )


def avaliar_meta(vendas: pd.DataFrame, parametros: ParametrosSimulacao) -> AtingimentoMeta:
    inicio, fim = pd.Timestamp(parametros.data_inicio), pd.Timestamp(parametros.data_fim)
    no_periodo = vendas["data_venda"].between(inicio, fim) & vendas["cod_marca"].isin(parametros.marcas_alvo)
    realizado = round(float(vendas.loc[no_periodo, "vlr_venda"].sum()), 2)
    pct = round(realizado / parametros.meta_vendas * 100, 2)
    return AtingimentoMeta(
        meta_vendas=parametros.meta_vendas, vendas_periodo=realizado,
        pct_atingimento=pct, atingida=realizado >= parametros.meta_vendas,
    )


def medir_impacto(comparacao: pd.DataFrame) -> ImpactoPessoas:
    """Ex.: medir_impacto(comparacao).pessoas_impactadas -> 312"""
    por_pessoa = comparacao[comparacao["diferenca"] > 0].groupby("matricula")["diferenca"].sum()
    vazio = por_pessoa.empty
    return ImpactoPessoas(
        pessoas_impactadas=int(por_pessoa.size), pessoas_total=int(comparacao["matricula"].nunique()),
        media_por_pessoa=0.0 if vazio else round(float(por_pessoa.mean()), 2),
        maior_acrescimo=0.0 if vazio else round(float(por_pessoa.max()), 2),
    )


def maiores_lojas(comparacao: pd.DataFrame, limite: int = LIMITE_LOJAS) -> list[QuebraDimensao]:
    """As lojas onde o custo extra mais pesa. Ex.: maiores_lojas(comparacao)[0].codigo -> "13" """
    afetadas = [loja for loja in quebrar_por(comparacao, "cod_loja") if loja.diferenca > 0]
    return sorted(afetadas, key=lambda loja: loja.diferenca, reverse=True)[:limite]
