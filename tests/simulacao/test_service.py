import pytest

from app.simulacao.service import SimulacaoFalhouError, SimuladorCampanha
from app.tools.code_tool.gerador import GeradorCodigoModelo
from app.tools.code_tool.runner import SubprocessRunner
from app.tools.regra_tool.parametros import RegraInvalidaError, montar_regra
from tests.fakes import (
    FakeExplicador, FakeFonteBases, FakeGeradorLlmIndisponivel, FakeGeradorSequencial, bases_pequenas, fonte_modelo,
    parametros_black_friday,
)

VALORES = {
    "periodo": {"data_inicio": "2025-11-24", "data_fim": "2025-11-30"},
    "pct_acrescimo": 1.0, "marcas_alvo": ["10", "30"], "cargos_alvo": ["100", "200", "300"],
    "meta_vendas": 1000.0, "orcamento_limite": 20.0,
}
CODIGO_QUEBRADO = "def aplicar_regra(bases, apuracao_base, competencias):\n    raise ValueError('bug')\n"


def _simulador(gerador: FakeGeradorSequencial | FakeGeradorLlmIndisponivel) -> SimuladorCampanha:
    return SimuladorCampanha(FakeFonteBases(bases_pequenas()), gerador, SubprocessRunner(), FakeExplicador())


def test_simular_black_friday_calcula_totais_orcamento_e_meta() -> None:
    gerador = FakeGeradorSequencial([fonte_modelo(parametros_black_friday())])

    resultado = _simulador(gerador).simular(montar_regra(VALORES, "bf", "draft-1"))

    # Janela 24–30/11: M1 vendeu 500 (+5,00) e M2 800 (+8,00); G1 (gerente) fora.
    assert resultado.totais.diferenca == 13.0
    assert resultado.orcamento.cabe_no_orcamento and resultado.orcamento.folga == 7.0
    assert resultado.meta.vendas_periodo == 1300.0 and resultado.meta.atingida
    assert resultado.tentativas == 1 and resultado.explicacao == "explicação fake"


def test_simular_tenta_de_novo_com_o_erro_da_primeira_tentativa() -> None:
    gerador = FakeGeradorSequencial([CODIGO_QUEBRADO, fonte_modelo(parametros_black_friday())])

    resultado = _simulador(gerador).simular(montar_regra(VALORES, "bf", "draft-1"))

    assert resultado.tentativas == 2
    assert gerador.erros_recebidos[0] is None
    assert "ValueError: bug" in (gerador.erros_recebidos[1] or "")


def test_simular_falha_sem_resultado_parcial_quando_as_tentativas_acabam() -> None:
    gerador = FakeGeradorSequencial([CODIGO_QUEBRADO])

    with pytest.raises(SimulacaoFalhouError) as erro:
        _simulador(gerador).simular(montar_regra(VALORES, "bf", "draft-1"))

    assert erro.value.etapa == "geracao_codigo" and erro.value.codigo == CODIGO_QUEBRADO


def test_simular_recusa_regra_incompleta_antes_de_gerar_codigo() -> None:
    gerador = FakeGeradorSequencial([CODIGO_QUEBRADO])

    with pytest.raises(RegraInvalidaError):
        _simulador(gerador).simular(montar_regra({**VALORES, "orcamento_limite": None}, "bf", "d"))

    assert gerador.erros_recebidos == []


def test_simular_recusa_competencia_sem_dados() -> None:
    periodo_sem_dados = {"data_inicio": "2025-12-01", "data_fim": "2025-12-31"}

    with pytest.raises(SimulacaoFalhouError, match="2025-12"):
        _simulador(FakeGeradorSequencial([CODIGO_QUEBRADO])).simular(
            montar_regra({**VALORES, "periodo": periodo_sem_dados}, "dez", "d")
        )


def test_simular_tenta_de_novo_quando_a_llm_falha() -> None:
    gerador = FakeGeradorLlmIndisponivel(fonte_modelo(parametros_black_friday()))

    resultado = _simulador(gerador).simular(montar_regra(VALORES, "bf", "draft-1"))

    assert resultado.tentativas == 2


def test_simular_trata_comissao_em_texto_como_tentativa_falha() -> None:
    comissao_texto = fonte_modelo(parametros_black_friday()).replace(
        '    return {"apuracao_simulada"', '    simulada["comissao"] = simulada["comissao"].astype(str)\n    return {"apuracao_simulada"'
    )

    with pytest.raises(SimulacaoFalhouError) as erro:
        _simulador(FakeGeradorSequencial([comissao_texto])).simular(montar_regra(VALORES, "bf", "d"))

    assert erro.value.etapa == "geracao_codigo"


# Gerente sobre a própria venda em vez da venda da loja: passa nas asserções de escopo,
# mas diverge do cálculo determinístico (caso real visto na LLM em 2026-09-26).
GERENTE_SOBRE_PROPRIA_VENDA = """import pandas as pd

def aplicar_regra(bases, apuracao_base, competencias):
    simulada = apuracao_base.copy()
    vendas = bases["vendas"]
    janela = vendas[(vendas["data_venda"] >= pd.Timestamp("2025-11-24")) & (vendas["cod_cargo"] == "150")]
    propria = janela.groupby("matricula")["vlr_venda"].sum()
    delta = simulada["matricula"].map(propria).fillna(0.0).mul(0.01).round(2)
    simulada["comissao"] = (simulada["comissao"] + delta).round(2)
    contrib = simulada[["matricula", "competencia"]].copy()
    contrib["elemento_ref"] = "pct_acrescimo"
    contrib["delta"] = delta
    return {"apuracao_simulada": simulada, "contribuicoes": contrib[contrib["delta"] != 0]}
"""
VALORES_GERENTE = {**VALORES, "cargos_alvo": ["150"]}


def _simulador_conferido(gerador: FakeGeradorSequencial) -> SimuladorCampanha:
    return SimuladorCampanha(
        FakeFonteBases(bases_pequenas()), gerador, SubprocessRunner(), FakeExplicador(),
        referencia=GeradorCodigoModelo(),
    )


def test_simular_conferido_aceita_codigo_da_ia_que_bate_com_a_referencia() -> None:
    fonte = fonte_modelo(parametros_black_friday(cargos_alvo=["150"]))

    resultado = _simulador_conferido(FakeGeradorSequencial([fonte])).simular(montar_regra(VALORES_GERENTE, "g", "d"))

    assert resultado.totais.diferenca == 5.0  # G1: 500 da loja 1 na janela * 1%
    assert resultado.origem_codigo == "fake" and "conferido" in resultado.observacao


def test_simular_conferido_devolve_a_divergencia_para_a_ia_e_usa_a_referencia_no_fim() -> None:
    gerador = FakeGeradorSequencial([GERENTE_SOBRE_PROPRIA_VENDA])

    resultado = _simulador_conferido(gerador).simular(montar_regra(VALORES_GERENTE, "g", "d"))

    assert "venda TOTAL da loja" in (gerador.erros_recebidos[1] or "")
    assert resultado.totais.diferenca == 5.0
    assert resultado.origem_codigo == "modelo" and "divergiu" in resultado.observacao
