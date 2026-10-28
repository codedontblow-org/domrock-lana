"""Número sem fonte é recusado (A6-70): valor em reais sem consulta que o sustente não vira fato."""
from decimal import Decimal

from app.agent.fonte_dos_valores import RESPOSTA_SEM_FONTE, conferir_fonte_dos_valores, valores_em_reais

PASSO_OK = {"ferramenta": "consultar_banco", "situacao": "SUCESSO"}
PASSO_ERRO = {"ferramenta": "consultar_banco", "situacao": "ERRO"}
FICHA = {"parametros": [{"key": "meta_vendas", "value": 2000000.0}, {"key": "pct_acrescimo", "value": 1.0}]}


def test_consulta_falhou_e_a_resposta_cita_reais_entao_e_recusada() -> None:
    resposta = "Em outubro de 2025 a marca 30 vendeu R$ 333.666,01."

    assert conferir_fonte_dos_valores(resposta, {"passos": [PASSO_ERRO]}, [], []) == RESPOSTA_SEM_FONTE


def test_sem_nenhuma_consulta_numero_inventado_e_recusado() -> None:
    assert conferir_fonte_dos_valores("A loja 2 vendeu R$ 10.000,00.", None, ["oi"], []) == RESPOSTA_SEM_FONTE


def test_consulta_com_sucesso_sustenta_a_resposta() -> None:
    resposta = "A marca 30 vendeu R$ 333.666,01."

    assert conferir_fonte_dos_valores(resposta, {"passos": [PASSO_ERRO, PASSO_OK]}, [], []) == resposta


def test_valor_da_ficha_ou_do_usuario_nao_precisa_de_consulta() -> None:
    resposta = "Registrei a meta de R$ 2 milhões e o orçamento de R$ 50 mil."

    assert conferir_fonte_dos_valores(resposta, None, ["orçamento de R$ 50.000"], [None, FICHA]) == resposta


def test_resposta_sem_reais_passa_como_veio() -> None:
    assert conferir_fonte_dos_valores("Posso consultar vendas por marca.", None, [], []) == "Posso consultar vendas por marca."


def test_le_valores_no_formato_brasileiro_e_por_extenso() -> None:
    texto = "R$ 2.406.125,93, R$ 2,4 milhões, R$ 50 mil e R$ 13."

    assert valores_em_reais(texto) == {
        Decimal("2406125.93"), Decimal("2400000.00"), Decimal("50000.00"), Decimal("13.00"),
    }


def test_valor_de_consulta_anterior_na_trilha_do_historico_passa_na_conferencia() -> None:
    trilha_turno_3 = {
        "passos": [
            {
                "ordem": 1,
                "ferramenta": "consultar_banco",
                "situacao": "SUCESSO",
                "dados": [{"total": 333666.01, "qtd_vendas": 188}],
            }
        ]
    }
    resposta = "Como vimos na consulta anterior, a marca 30 vendeu R$ 333.666,01."
    assert conferir_fonte_dos_valores(resposta, None, ["qual foi o valor mesmo?"], [], trilhas_historico=[trilha_turno_3]) == resposta


def test_valor_em_reais_nao_presente_na_trilha_do_historico_e_recusado() -> None:
    trilha_turno_3 = {
        "passos": [
            {
                "ordem": 1,
                "ferramenta": "consultar_banco",
                "situacao": "SUCESSO",
                "dados": [{"total": 1000.00}],
            }
        ]
    }
    resposta = "A marca 30 vendeu R$ 333.666,01."
    assert conferir_fonte_dos_valores(resposta, None, ["qual foi o valor?"], [], trilhas_historico=[trilha_turno_3]) == RESPOSTA_SEM_FONTE
