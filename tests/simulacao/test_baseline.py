import pytest

from app.simulacao.baseline import BaselineError, calcular_baseline
from app.simulacao.bases import BasesSimulacao, competencias_do_periodo
from tests.fakes import bases_pequenas


def test_baseline_aplica_pct_da_marca_cargo_sobre_a_venda_da_matricula() -> None:
    apuracao = calcular_baseline(bases_pequenas()).set_index("matricula")

    assert apuracao.loc["M1", "comissao"] == 30.0  # 1500 * 2%
    assert apuracao.loc["M2", "comissao"] == 24.0  # 800 * 3%


def test_baseline_paga_o_gerente_sobre_a_venda_total_da_loja() -> None:
    apuracao = calcular_baseline(bases_pequenas()).set_index("matricula")

    assert apuracao.loc["G1", "base_calculo"] == 1700.0  # 1000 + 500 + 200 da loja 1
    assert apuracao.loc["G1", "comissao"] == 17.0


def test_baseline_sem_pct_para_marca_cargo_levanta_erro_com_a_combinacao() -> None:
    bases = bases_pequenas()
    sem_gerente = BasesSimulacao(bases.rh, bases.vendas, bases.comissoes.iloc[[0, 2]])

    with pytest.raises(BaselineError, match=r"\['30', '150'\]"):
        calcular_baseline(sem_gerente)


def test_competencias_do_periodo_cobre_meses_parciais() -> None:
    from datetime import date

    assert competencias_do_periodo(date(2025, 11, 24), date(2025, 12, 5)) == ["2025-11", "2025-12"]
