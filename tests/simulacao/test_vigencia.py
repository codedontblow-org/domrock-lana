"""A6-74: % vigente, trechos, histórico e conflitos no formato do contrato (2.3 e 4.3)."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pandas as pd
import pytest
from pydantic import ValidationError

from app.simulacao.baseline import BaselineError
from app.simulacao.bases import BasesSimulacao
from app.simulacao.dtos import SimulacaoRequest
from app.simulacao.vigencia import (
    CampanhaContexto, calcular_baseline_vigente, calcular_periodos, detectar_conflitos,
)
from app.simulacao.service import SimuladorCampanha
from app.tools.code_tool.gerador import GeradorCodigoModelo
from app.tools.code_tool.runner import SubprocessRunner
from app.tools.regra_tool.parametros import montar_regra
from tests.fakes import FakeCatalogoEspecificacao, FakeExplicador, FakeFonteBases, parametros_black_friday

TAXAS = pd.DataFrame([
    {'cod_marca': '10', 'cod_cargo': '150', 'pct_comiss': 1.0},
    {'cod_marca': '10', 'cod_cargo': '100', 'pct_comiss': 2.5},
    {'cod_marca': '20', 'cod_cargo': '100', 'pct_comiss': 3.0},
])

# O item de `campanhas` do exemplo do contrato 4.3, como o backend manda.
CAMPANHA_A = {
    'campanha_id': 9, 'versao': 1, 'tipo': 'ACRESCIMO', 'nome': 'Campanha A', 'status': 'APROVADA',
    'autor': 'Gabriela', 'aprovador': 'Sérgio', 'aprovada_em': '2026-10-15T14:02:00Z',
    'justificativa': 'Reforço da última semana de novembro',
    'data_inicio': '2025-11-20', 'data_fim': '2025-11-30',
    'pct_acrescimo': 1.0, 'marcas_alvo': ['10'], 'cargos_alvo': ['150'],
}
SEM_DECISAO = {'campanha_id': None, 'versao': None, 'autor': None, 'aprovador': None, 'aprovada_em': None}
ITEM_5G = 'Especificação nov/25, item 5g'


def campanha(nome: str = 'Campanha A', **dados: object) -> CampanhaContexto:
    return CampanhaContexto.model_validate({**CAMPANHA_A, 'nome': nome, **dados})


def item_5g() -> CampanhaContexto:
    return campanha(ITEM_5G, **SEM_DECISAO, pct_acrescimo=.5, data_inicio='2025-11-24',
                    justificativa='Gerentes: +0,5% nas vendas de 24 a 30/11 (Black Friday)')


def contexto() -> list[CampanhaContexto]:
    campanha_b = campanha('Campanha B', campanha_id=10, pct_acrescimo=.5, aprovador='Sílvia',
                          aprovada_em='2026-10-16T10:30:00Z', data_inicio='2025-11-25', data_fim='2025-12-05')
    return [item_5g(), campanha(), campanha_b]


def parametros(**dados: object):
    return parametros_black_friday(**{'marcas_alvo': ['10'], 'cargos_alvo': ['150'], 'pct_acrescimo': .5, **dados})


def test_aceite_1_trechos_com_base_vigente_e_campanha():
    trechos = calcular_periodos(parametros(), TAXAS, contexto())
    assert [(t.data_inicio, t.data_fim, t.pct_base, t.pct_vigente, t.pct_com_campanha) for t in trechos] == [
        (date(2025, 11, 24), date(2025, 11, 24), 1, 2.5, 3),
        (date(2025, 11, 25), date(2025, 11, 30), 1, 3, 3.5),
    ]


def test_aceite_1_historico_explica_a_vigente_com_a_decisao():
    _, trecho = calcular_periodos(parametros(), TAXAS, contexto())
    assert [h.nome for h in trecho.historico] == [ITEM_5G, 'Campanha A', 'Campanha B']
    especificacao, a, _ = trecho.historico
    assert (especificacao.campanha_id, especificacao.versao, especificacao.autor, especificacao.aprovada_em) == (
        None, None, None, None)
    assert (a.campanha_id, a.versao, a.pct_acrescimo, a.pct_novo) == (9, 1, 1.0, None)
    assert (a.autor, a.aprovador, a.justificativa) == ('Gabriela', 'Sérgio', 'Reforço da última semana de novembro')
    assert a.aprovada_em == datetime(2026, 10, 15, 14, 2, tzinfo=timezone.utc)


def test_aceite_2_conflito_traz_a_sobreposicao_de_cada_campanha():
    p = parametros(data_inicio=date(2025, 11, 28), data_fim=date(2025, 12, 5))
    conflitos = {c.nome: c for c in detectar_conflitos(p, contexto())}
    assert {nome: (c.sobreposicao.data_inicio, c.sobreposicao.data_fim) for nome, c in conflitos.items()} == {
        ITEM_5G: (date(2025, 11, 28), date(2025, 11, 30)),
        'Campanha A': (date(2025, 11, 28), date(2025, 11, 30)),
        'Campanha B': (date(2025, 11, 28), date(2025, 12, 5)),
    }
    a = conflitos['Campanha A']
    assert (a.campanha_id, a.versao, a.tipo, a.status, a.autor) == (9, 1, 'ACRESCIMO', 'APROVADA', 'Gabriela')
    assert (a.data_inicio, a.data_fim, a.marcas, a.cargos) == (date(2025, 11, 20), date(2025, 11, 30), ['10'], ['150'])


def test_aceite_3_sem_campanhas_vigente_igual_base_e_sem_conflito():
    p = parametros(data_inicio=date(2025, 10, 1), data_fim=date(2025, 10, 31))
    trecho, = calcular_periodos(p, TAXAS, contexto())
    assert (trecho.pct_base, trecho.pct_vigente, trecho.historico) == (1, 1, [])
    assert detectar_conflitos(p, contexto()) == []


def test_aceite_4_pendente_nao_entra_na_vigente_e_aparece_no_conflito():
    pendente = campanha('Campanha C', campanha_id=11, status='AGUARDANDO_APROVACAO', pct_acrescimo=2,
                        aprovador=None, aprovada_em=None, justificativa=None,
                        data_inicio='2025-12-01', data_fim='2025-12-10')
    p = parametros(data_inicio=date(2025, 12, 1), data_fim=date(2025, 12, 5))
    trecho, = calcular_periodos(p, TAXAS, contexto() + [pendente])
    assert (trecho.pct_vigente, trecho.pct_com_campanha) == (1.5, 2)
    assert [h.nome for h in trecho.historico] == ['Campanha B']
    c = next(c for c in detectar_conflitos(p, contexto() + [pendente]) if c.nome == 'Campanha C')
    assert (c.status, c.sobreposicao.data_fim) == ('AGUARDANDO_APROVACAO', date(2025, 12, 5))


def test_aceite_5_substituicao_pela_marca_de_referencia():
    item_3g = campanha('Especificação set/25, item 3g', **SEM_DECISAO, tipo='SUBSTITUICAO', pct_acrescimo=None,
                       marca_referencia='20', cargos_alvo=['100'], data_inicio='2025-09-01', data_fim='2025-09-30')
    p = parametros(cargos_alvo=['100'], data_inicio=date(2025, 9, 1), data_fim=date(2025, 9, 30))
    trecho, = calcular_periodos(p, TAXAS, [item_3g])
    assert (trecho.pct_base, trecho.pct_vigente, trecho.pct_com_campanha) == (2.5, 3, 3.5)
    historico, = trecho.historico
    assert (historico.tipo, historico.pct_acrescimo, historico.pct_novo) == ('SUBSTITUICAO', None, 3.0)
    assert detectar_conflitos(p, [item_3g])[0].tipo == 'SUBSTITUICAO'


def test_ultima_substituicao_aprovada_vence_e_a_outra_fica_so_no_conflito():
    substituicao = {'tipo': 'SUBSTITUICAO', 'pct_acrescimo': None}
    antiga = campanha('S1', campanha_id=1, pct_novo=4, aprovada_em='2026-10-20T12:00:00Z', **substituicao)
    nova = campanha('S2', campanha_id=2, pct_novo=2, aprovada_em='2026-10-21T12:00:00Z', **substituicao)
    fontes = [nova, campanha(), antiga]
    trecho, = calcular_periodos(parametros(), TAXAS, fontes)
    assert trecho.pct_vigente == 3
    assert [(h.nome, h.pct_novo) for h in trecho.historico] == [('Campanha A', None), ('S2', 2.0)]
    assert {c.nome for c in detectar_conflitos(parametros(), fontes)} == {'S1', 'S2', 'Campanha A'}


def test_conflito_traz_so_as_marcas_e_os_cargos_em_comum():
    fonte = campanha(marcas_alvo=['10', '20'], cargos_alvo=['100', '150'])
    conflito, = detectar_conflitos(parametros(marcas_alvo=['10', '30'], cargos_alvo=['150', '200']), [fonte])
    assert (conflito.marcas, conflito.cargos) == (['10'], ['150'])


def test_conflito_exige_marca_cargo_e_data_em_comum():
    fontes = [campanha('marca', campanha_id=1, marcas_alvo=['20']),
              campanha('cargo', campanha_id=2, cargos_alvo=['100']),
              campanha('data', campanha_id=3, data_fim='2025-11-23')]
    assert detectar_conflitos(parametros(), fontes) == []


def test_mesma_versao_duas_vezes_falha_sem_resultado_parcial():
    with pytest.raises(BaselineError, match='duplicadas'):
        calcular_periodos(parametros(), TAXAS, [campanha(), campanha('Outro nome')])


def test_marca_e_cargo_sem_percentual_base_falha():
    with pytest.raises(BaselineError, match='Sem % base'):
        calcular_periodos(parametros(cargos_alvo=['300']), TAXAS, [])


def test_marca_de_referencia_sem_percentual_falha():
    fonte = campanha('Item', **SEM_DECISAO, tipo='SUBSTITUICAO', pct_acrescimo=None, marca_referencia='60')
    with pytest.raises(BaselineError, match='referência'):
        calcular_periodos(parametros(), TAXAS, [fonte])


@pytest.mark.parametrize('dados', [
    {'pct_acrescimo': -1}, {'pct_acrescimo': Decimal('NaN')}, {'pct_acrescimo': None},
    {'pct_novo': 2},
    {'tipo': 'SUBSTITUICAO', 'pct_acrescimo': None},
    {'tipo': 'SUBSTITUICAO', 'pct_acrescimo': None, 'pct_novo': 2, 'marca_referencia': '20'},
    {'aprovada_em': None}, {'aprovada_em': '2026-10-15T14:02:00'},
    {'data_fim': '2025-11-01'}, {'status': 'REPROVADA'},
])
def test_campanha_invalida_e_rejeitada(dados):
    with pytest.raises(ValidationError):
        campanha(**dados)


def regra_gerente():
    valores = {'periodo': {'data_inicio': '2025-11-24', 'data_fim': '2025-11-30'},
               'pct_acrescimo': .5, 'marcas_alvo': ['10'], 'cargos_alvo': ['150'],
               'meta_vendas': 1000, 'orcamento_limite': 1000}
    return montar_regra(valores, 'teste', 'r1')


def test_pedido_aceita_o_item_do_contrato_4_3():
    pedido = SimulacaoRequest.model_validate({'chat_id': 'c1', 'regra': regra_gerente().model_dump(),
                                              'campanhas': [CAMPANHA_A]})
    assert (pedido.campanhas[0].campanha_id, pedido.campanhas[0].pct_acrescimo) == (9, Decimal('1.0'))


@pytest.mark.parametrize('dados', [
    {'campanha_id': None}, {'versao': None},
    {'tipo': 'SUBSTITUICAO', 'pct_acrescimo': None, 'marca_referencia': '20'},
])
def test_pedido_so_aceita_versao_salva_no_backend(dados):
    with pytest.raises(ValidationError):
        SimulacaoRequest.model_validate({'regra': regra_gerente().model_dump(), 'campanhas': [{**CAMPANHA_A, **dados}]})


def bases_aceite() -> BasesSimulacao:
    rh = pd.DataFrame({
        'matricula': ['G', 'V'], 'competencia': ['2025-11'] * 2,
        'cod_loja': ['1'] * 2, 'cod_marca': ['10'] * 2, 'cod_cargo': ['150', '100'],
        'data_admissao': pd.to_datetime(['2020-01-01'] * 2),
        'data_demissao': pd.to_datetime([None] * 2),
    })
    vendas = pd.DataFrame({
        'matricula': ['V'] * 4, 'competencia': ['2025-11'] * 4,
        'cod_loja': ['1'] * 4, 'cod_marca': ['10'] * 4, 'cod_cargo': ['100'] * 4,
        'data_venda': pd.to_datetime(['2025-11-19', '2025-11-24', '2025-11-25', '2025-11-28']),
        'vlr_venda': [1000.] * 4,
    })
    return BasesSimulacao(rh, vendas, TAXAS.copy())


def pendente_p() -> CampanhaContexto:
    return campanha('Campanha P', campanha_id=12, status='AGUARDANDO_APROVACAO', pct_acrescimo=50,
                    aprovador=None, aprovada_em=None)


def test_comissao_atual_usa_a_data_real_de_cada_venda_e_ignora_pendente():
    baseline = calcular_baseline_vigente(bases_aceite(), contexto() + [pendente_p()]).set_index('matricula')
    # Gerente: 19/11 1%, 24/11 2,5%, 25 e 28/11 3% sobre a venda da loja. Vendedor segue 2,5%.
    assert baseline.loc['G', 'comissao'] == 95
    assert baseline.loc['V', 'comissao'] == 100


def test_simulacao_devolve_vigencia_conflitos_e_trilha_do_contrato():
    simulador = SimuladorCampanha(FakeFonteBases(bases_aceite()), GeradorCodigoModelo(), SubprocessRunner(),
                                  FakeExplicador())
    resultado = simulador.simular(regra_gerente(), contexto() + [pendente_p()])
    assert (resultado.totais.baseline, resultado.totais.simulado, resultado.totais.diferenca) == (195, 210, 15)
    corpo = resultado.model_dump(mode='json')
    assert [t['pct_com_campanha'] for t in corpo['comissao_periodo']] == [3, 3.5]
    assert [c['nome'] for c in corpo['trilha']['campanhas']] == [ITEM_5G, 'Campanha A', 'Campanha B']
    assert 'Campanha P' in {c['nome'] for c in corpo['conflitos']}


def test_campanhas_da_especificacao_vem_do_catalogo_da_lana():
    simulador = SimuladorCampanha(FakeFonteBases(bases_aceite()), GeradorCodigoModelo(), SubprocessRunner(),
                                  FakeExplicador(), especificacao=FakeCatalogoEspecificacao([item_5g()]))
    so_do_backend = contexto()[1:]
    resultado = simulador.simular(regra_gerente(), so_do_backend)
    assert resultado.totais.baseline == 195
    assert [h.nome for h in resultado.comissao_periodo[0].historico] == [ITEM_5G, 'Campanha A']
