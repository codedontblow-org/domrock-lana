import pandas as pd

from app.simulacao.resumo import maiores_lojas, medir_impacto

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
