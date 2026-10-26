import pandas as pd

from app.simulacao.dtos import AtingimentoMeta, TotaisSimulacao
from app.simulacao.resumo import (
    avaliar_meta, avaliar_orcamento, avaliar_retorno, maiores_lojas, medir_impacto, vendas_do_periodo,
)
from tests.fakes import bases_pequenas, parametros_black_friday

COMPARACAO = pd.DataFrame({
    "matricula": ["M1", "M1", "M2", "M3"],
    "competencia": ["2025-10", "2025-11", "2025-11", "2025-11"],
    "cod_loja": ["1", "1", "2", "3"],
    "comissao": [10.0, 10.0, 20.0, 30.0],
    "comissao_simulada": [12.0, 13.0, 21.0, 30.0],
    "diferenca": [2.0, 3.0, 1.0, 0.0],
})


def test_medir_impacto_soma_o_periodo_por_matricula() -> None:
    impacto = medir_impacto(COMPARACAO)

    assert (impacto.pessoas_impactadas, impacto.pessoas_total) == (2, 3)
    assert impacto.media_por_pessoa == 3.0 and impacto.maior_acrescimo == 5.0


def test_medir_impacto_sem_ninguem_afetado_devolve_zeros() -> None:
    impacto = medir_impacto(COMPARACAO.assign(diferenca=0.0))

    assert impacto.pessoas_impactadas == 0 and impacto.media_por_pessoa == 0.0


def test_maiores_lojas_ordena_pelo_custo_extra_e_ignora_lojas_sem_efeito() -> None:
    lojas = maiores_lojas(COMPARACAO, limite=5)

    assert [(loja.codigo, loja.diferenca) for loja in lojas] == [("1", 5.0), ("2", 1.0)]


def test_vendas_do_periodo_ficam_entre_inicio_e_fim_nas_marcas_da_campanha() -> None:
    # Regressão A6-70: a trilha contava todas as vendas do mês (4), não as de 24 a 30/11 (2).
    vendas = vendas_do_periodo(bases_pequenas().vendas, parametros_black_friday())

    assert list(vendas["matricula"]) == ["M1", "M2"]


def _meta(meta_vendas: float, vendas_periodo: float) -> AtingimentoMeta:
    return AtingimentoMeta(
        meta_vendas=meta_vendas, vendas_periodo=vendas_periodo, pct_atingimento=0.0,
        atingida=vendas_periodo >= meta_vendas, diferenca=round(vendas_periodo - meta_vendas, 2),
    )


def _totais(custo: float) -> TotaisSimulacao:
    return TotaisSimulacao(baseline=0.0, simulado=custo, diferenca=custo, diferenca_pct=0.0)


def test_avaliar_meta_traz_a_diferenca_em_reais() -> None:
    # Janela 24–30/11: M1 vendeu 500 e M2 800, contra a meta de 1.000.
    meta = avaliar_meta(bases_pequenas().vendas, parametros_black_friday())

    assert meta.vendas_periodo == 1300.0 and meta.diferenca == 300.0


def test_retorno_da_black_friday_com_a_meta_superada() -> None:
    # Critério do A6-72: custo de R$ 23.736,10 sobre a venda de R$ 2.406.125,93 e meta de R$ 2 milhões.
    retorno = avaliar_retorno(_totais(23736.10), _meta(2_000_000.0, 2406125.93))

    assert retorno.provisorio is True
    assert retorno.custo_pct_venda == 0.99 and retorno.custo_por_real_acima_meta == 0.06


def test_retorno_abaixo_da_meta_nao_tem_custo_por_real_acima_dela() -> None:
    retorno = avaliar_retorno(_totais(23736.10), _meta(3_000_000.0, 2406125.93))

    assert retorno.custo_pct_venda == 0.99 and retorno.custo_por_real_acima_meta is None


def test_retorno_sem_venda_no_periodo_nao_divide_por_zero() -> None:
    retorno = avaliar_retorno(_totais(0.0), _meta(1000.0, 0.0))

    assert retorno.custo_pct_venda is None and retorno.custo_por_real_acima_meta is None


def test_sem_orcamento_nao_ha_veredito() -> None:
    assert avaliar_orcamento(_totais(13.0), None) is None
    assert avaliar_orcamento(_totais(13.0), 20.0).folga == 7.0
