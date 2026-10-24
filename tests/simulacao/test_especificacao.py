"""O catálogo real da especificação aplica os itens do PDF na % vigente, como aprovados (estudo A6-73)."""
from datetime import date

import pandas as pd

from app.simulacao.especificacao import ArquivoEspecificacao
from app.simulacao.vigencia import calcular_periodos, detectar_conflitos
from tests.fakes import parametros_black_friday

TAXAS = pd.DataFrame([
    {'cod_marca': '10', 'cod_cargo': '100', 'pct_comiss': 2.5},
    {'cod_marca': '10', 'cod_cargo': '150', 'pct_comiss': 1.0},
    {'cod_marca': '10', 'cod_cargo': '300', 'pct_comiss': 2.0},
    {'cod_marca': '20', 'cod_cargo': '100', 'pct_comiss': 3.0},
    {'cod_marca': '30', 'cod_cargo': '100', 'pct_comiss': 2.0},
])


def vigencia(marca: str, cargo: str, inicio: date, fim: date) -> tuple[float, list[str]]:
    p = parametros_black_friday(marcas_alvo=[marca], cargos_alvo=[cargo], pct_acrescimo=.5,
                                data_inicio=inicio, data_fim=fim)
    trecho, = calcular_periodos(p, TAXAS, ArquivoEspecificacao().campanhas())
    return trecho.pct_vigente, [h.nome for h in trecho.historico]


def test_2h_troca_o_cargo_300_da_marca_10_em_agosto():
    assert vigencia('10', '300', date(2025, 8, 1), date(2025, 8, 31)) == (
        1.75, ['Especificação ago/25, item 2h'])


def test_3g_usa_a_marca_20_na_marca_10_em_setembro():
    assert vigencia('10', '100', date(2025, 9, 1), date(2025, 9, 30)) == (
        3.0, ['Especificação set/25, item 3g'])


def test_4g_soma_meio_ponto_na_marca_30_em_outubro():
    assert vigencia('30', '100', date(2025, 10, 1), date(2025, 10, 31)) == (
        2.5, ['Especificação out/25, item 4g'])


def test_5g_soma_meio_ponto_para_gerentes_na_black_friday():
    assert vigencia('10', '150', date(2025, 11, 24), date(2025, 11, 30)) == (
        1.5, ['Especificação nov/25, item 5g'])


def test_black_friday_simulada_conflita_com_o_5f_e_nao_com_o_5g():
    p = parametros_black_friday(marcas_alvo=['10'], cargos_alvo=['100'])
    assert [c.nome for c in detectar_conflitos(p, ArquivoEspecificacao().campanhas())] == [
        'Especificação nov/25, item 5f']
