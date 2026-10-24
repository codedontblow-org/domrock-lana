from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
from pydantic import ValidationError

from app.simulacao.baseline import BaselineError
from app.simulacao.bases import BasesSimulacao
from app.simulacao.vigencia import (
    CampanhaContexto, calcular_baseline_vigente, calcular_periodos, detectar_conflitos,
)
from app.simulacao.service import SimuladorCampanha
from app.tools.code_tool.gerador import GeradorCodigoModelo
from app.tools.code_tool.runner import SubprocessRunner
from app.tools.regra_tool.parametros import montar_regra
from tests.fakes import FakeExplicador, FakeFonteBases, parametros_black_friday

TAXAS = pd.DataFrame([
    {'cod_marca': '10', 'cod_cargo': '150', 'pct_comiss': 1.0},
    {'cod_marca': '10', 'cod_cargo': '100', 'pct_comiss': 2.5},
    {'cod_marca': '20', 'cod_cargo': '100', 'pct_comiss': 3.0},
])


def campanha(id='A', **dados):
    return CampanhaContexto.model_validate({
        'id': id, 'nome': id, 'tipo': 'ACRESCIMO', 'status': 'APROVADA',
        'data_inicio': '2025-11-20', 'data_fim': '2025-11-30',
        'marcas_alvo': ['10'], 'cargos_alvo': ['150'], 'percentual': 1,
        'autor': 'Gabriela', 'aprovador': 'Sérgio', 'aprovada_em': '2025-10-20T12:00:00Z',
        'justificativa': 'Meta aprovada', **dados,
    })


def contexto():
    return [
        campanha('5g', percentual=.5, data_inicio='2025-11-24', origem='ESPECIFICACAO',
                 aprovador=None, aprovada_em=None),
        campanha(),
        campanha('B', percentual=.5, data_inicio='2025-11-25', data_fim='2025-12-05'),
    ]


def parametros(**dados):
    return parametros_black_friday(marcas_alvo=['10'], cargos_alvo=dados.pop('cargos_alvo', ['150']),
                                   pct_acrescimo=.5, **dados)


def test_aceite_1_percentuais_trechos_e_fontes():
    trechos = calcular_periodos(parametros(), TAXAS, contexto())
    assert [(t.inicio.day, t.fim.day, t.base, t.vigente, t.comCampanha) for t in trechos] == [
        (24, 24, 1, 2.5, 3), (25, 30, 1, 3, 3.5),
    ]
    assert {h.id for h in trechos[1].historico} == {'5g', 'A', 'B'}
    a = next(h for h in trechos[1].historico if h.id == 'A')
    assert a.aprovador == 'Sérgio' and a.autor == 'Gabriela'
    assert a.aprovadoEm is not None and a.justificativa == 'Meta aprovada'
    assert all(t.avisos for t in trechos)


def test_aceite_2_intersecoes_inclusivas_dos_conflitos():
    p = parametros(data_inicio=date(2025, 11, 28), data_fim=date(2025, 12, 5))
    conflitos = {c.id: c for c in detectar_conflitos(p, contexto())}
    for id in ('5g', 'A'):
        assert conflitos[id].inicio == date(2025, 11, 28)
        assert conflitos[id].fim == date(2025, 11, 30)
    assert conflitos['B'].fim == date(2025, 12, 5)
    assert all(c.tipo == 'ACRESCIMO' and c.cargos == ['150'] for c in conflitos.values())


def test_aceite_3_sem_campanhas_vigente_igual_base():
    p = parametros(data_inicio=date(2025, 10, 1), data_fim=date(2025, 10, 31))
    trecho, = calcular_periodos(p, TAXAS, contexto())
    assert trecho.base == trecho.vigente == 1
    assert trecho.historico == trecho.avisos == detectar_conflitos(p, contexto()) == []


def test_aceite_4_pendente_nao_altera_vigente():
    fontes = contexto() + [campanha('C', percentual=2, status='AGUARDANDO_APROVACAO',
        data_inicio='2025-12-01', data_fim='2025-12-10', aprovada_em=None, aprovador=None)]
    p = parametros(data_inicio=date(2025, 12, 1), data_fim=date(2025, 12, 5))
    trecho, = calcular_periodos(p, TAXAS, fontes)
    assert trecho.vigente == 1.5 and trecho.comCampanha == 2
    assert [h.id for h in trecho.historico] == ['B']
    conflitos = {c.id: c for c in detectar_conflitos(p, fontes)}
    assert conflitos['C'].status == 'AGUARDANDO_APROVACAO'
    assert conflitos['C'].fim == date(2025, 12, 5)


def test_aceite_5_substituicao_por_marca_de_referencia():
    fonte = campanha('3g', tipo='SUBSTITUICAO', percentual=None, marca_referencia='20',
        cargos_alvo=['100'], data_inicio='2025-09-01', data_fim='2025-09-30',
        origem='ESPECIFICACAO', aprovada_em=None)
    p = parametros(cargos_alvo=['100'], data_inicio=date(2025, 9, 1), data_fim=date(2025, 9, 30))
    trecho, = calcular_periodos(p, TAXAS, [fonte])
    assert (trecho.base, trecho.vigente, trecho.comCampanha) == (2.5, 3, 3.5)
    assert trecho.historico[0].tipo == 'SUBSTITUICAO'
    assert trecho.historico[0].acrescimo is None
    assert detectar_conflitos(p, [fonte])[0].tipo == 'SUBSTITUICAO'


def test_ultima_substituicao_aprovada_vence_e_soma_acrescimos():
    antiga = campanha('S1', tipo='SUBSTITUICAO', percentual=4)
    nova = campanha('S2', tipo='SUBSTITUICAO', percentual=2, aprovada_em='2025-10-21T12:00:00Z')
    trechos = calcular_periodos(parametros(), TAXAS, [nova, campanha(), antiga])
    assert trechos[0].vigente == 3
    assert {h.id: h.aplicada for h in trechos[0].historico} == {'S1': False, 'S2': True, 'A': True}
    assert any('último' in a for a in trechos[0].avisos)


def test_conflito_exige_marca_e_cargo_e_data_em_comum():
    fontes = [campanha('marca', marcas_alvo=['20']), campanha('cargo', cargos_alvo=['100']),
              campanha('data', data_fim='2025-11-23')]
    assert detectar_conflitos(parametros(), fontes) == []


def test_duplicatas_e_base_ausente_falham_sem_resultado_parcial():
    with pytest.raises(BaselineError, match='duplicadas'):
        calcular_periodos(parametros(), TAXAS, [campanha(), campanha()])
    with pytest.raises(BaselineError, match='Sem % base'):
        calcular_periodos(parametros(cargos_alvo=['300']), TAXAS, [])
    fonte = campanha(tipo='SUBSTITUICAO', percentual=None, marca_referencia='60')
    with pytest.raises(BaselineError, match='referência'):
        calcular_periodos(parametros(), TAXAS, [fonte])


@pytest.mark.parametrize('dados', [
    {'percentual': -1}, {'percentual': Decimal('NaN')}, {'aprovada_em': None},
    {'aprovada_em': '2025-10-20T12:00:00'}, {'data_fim': '2025-11-01'},
    {'tipo': 'SUBSTITUICAO', 'marca_referencia': '20'}, {'status': 'REPROVADA'},
])
def test_contexto_invalido_e_rejeitado(dados):
    with pytest.raises(ValidationError):
        campanha(**dados)


def bases_aceite():
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


def test_datas_reais_e_custo_incremental_no_executor_com_pendente():
    fontes = contexto() + [campanha('P', status='AGUARDANDO_APROVACAO', percentual=50, aprovada_em=None)]
    bases = bases_aceite()
    baseline = calcular_baseline_vigente(bases, fontes).set_index('matricula')
    # Gerente: 19/11 1%, 24/11 2.5%, 25 e 28/11 3%. Vendedor segue 2.5%.
    assert baseline.loc['G', 'comissao'] == 95
    assert baseline.loc['V', 'comissao'] == 100
    valores = {'periodo': {'data_inicio': '2025-11-24', 'data_fim': '2025-11-30'},
               'pct_acrescimo': .5, 'marcas_alvo': ['10'], 'cargos_alvo': ['150'],
               'meta_vendas': 1000, 'orcamento_limite': 1000}
    simulador = SimuladorCampanha(FakeFonteBases(bases), GeradorCodigoModelo(), SubprocessRunner(), FakeExplicador())
    resultado = simulador.simular(montar_regra(valores, 'teste', 'r1'), fontes)
    assert resultado.totais.baseline == 195
    assert resultado.totais.simulado == 210
    assert resultado.totais.diferenca == 15  # Apenas os novos .5% de 3000.
    assert {c['id'] for c in resultado.trilha['campanhas']} == {'5g', 'A', 'B'}
    assert 'P' in {c.id for c in resultado.conflitos}
    assert resultado.model_dump(mode='json')['comissoes_periodo'][0]['comCampanha'] == 3
