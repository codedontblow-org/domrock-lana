import pandas as pd
import pytest

from app.simulacao.assercoes import AssercaoViolada, conferir_resultado
from app.simulacao.baseline import calcular_baseline
from tests.fakes import bases_pequenas, parametros_black_friday

COLUNAS = ["matricula", "competencia", "elemento_ref", "delta"]


def _cenario(delta_por_matricula: dict[str, float]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = calcular_baseline(bases_pequenas())
    simulada = base.copy()
    simulada["comissao"] = simulada["comissao"] + simulada["matricula"].map(delta_por_matricula).fillna(0.0)
    contribuicoes = pd.DataFrame(
        [[m, "2025-11", "pct_acrescimo", d] for m, d in delta_por_matricula.items()], columns=COLUNAS
    )
    return base, simulada, contribuicoes


def test_conferir_resultado_aceita_mudanca_dentro_do_escopo() -> None:
    base, simulada, contribuicoes = _cenario({"M1": 5.0, "M2": 8.0})

    comparacao = conferir_resultado(base, simulada, contribuicoes, parametros_black_friday())

    assert comparacao["diferenca"].sum() == 13.0


def test_conferir_resultado_recusa_alterar_gerente_excluido() -> None:
    base, simulada, contribuicoes = _cenario({"G1": 1.0})

    with pytest.raises(AssercaoViolada, match="fora de marcas"):
        conferir_resultado(base, simulada, contribuicoes, parametros_black_friday())


def test_conferir_resultado_recusa_contribuicao_que_nao_soma() -> None:
    base, simulada, _ = _cenario({"M1": 5.0})
    contribuicoes = pd.DataFrame([["M1", "2025-11", "pct_acrescimo", 4.0]], columns=COLUNAS)

    with pytest.raises(AssercaoViolada, match="Soma das contribuicoes"):
        conferir_resultado(base, simulada, contribuicoes, parametros_black_friday())


def test_conferir_resultado_recusa_linha_perdida_e_comissao_negativa() -> None:
    base, simulada, contribuicoes = _cenario({"M1": -100.0})

    with pytest.raises(AssercaoViolada, match="negativa"):
        conferir_resultado(base, simulada, contribuicoes, parametros_black_friday())
    with pytest.raises(AssercaoViolada, match="linhas"):
        conferir_resultado(base, simulada.iloc[1:], contribuicoes, parametros_black_friday())
