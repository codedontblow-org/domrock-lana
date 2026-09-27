from app.simulacao.cenarios import percentual_no_limite, propor_cenarios
from app.simulacao.dtos import QuebraDimensao, VereditoOrcamento
from tests.fakes import FakeSimuladorCusto, parametros_black_friday


def _orcamento(limite: float, custo: float) -> VereditoOrcamento:
    folga = round(limite - custo, 2)
    return VereditoOrcamento(orcamento_limite=limite, custo_incremental=custo, folga=folga, cabe_no_orcamento=folga >= 0)


def _marca(codigo: str, diferenca: float) -> QuebraDimensao:
    return QuebraDimensao(codigo=codigo, baseline=0.0, simulado=diferenca, diferenca=diferenca)


def test_percentual_no_limite_trunca_em_duas_casas() -> None:
    # Black Friday real: +1% custa R$ 23.736,14; com R$ 20.000 cabe no máximo 0,84%.
    assert percentual_no_limite(1.0, 20000.0, 23736.14) == 0.84
    assert percentual_no_limite(1.0, 30000.0, 23736.14) == 1.26
    assert percentual_no_limite(1.0, 20000.0, 0.0) is None


def test_estourou_o_orcamento_propoe_percentual_menor_ja_simulado() -> None:
    simulador = FakeSimuladorCusto(custo_por_ponto=23736.14)

    cenarios = propor_cenarios(parametros_black_friday(), _orcamento(20000.0, 23736.14), [], simulador)

    assert [c.pct_acrescimo for c in cenarios] == [0.84]
    assert cenarios[0].cabe_no_orcamento and cenarios[0].custo_incremental == 19938.36
    assert cenarios[0].economia == 3797.78 and simulador.simulados[0].pct_acrescimo == 0.84


def test_arredondamento_acima_do_limite_recua_um_passo() -> None:
    # Custo não proporcional exato: 0,84% passaria do limite, então tenta 0,83%.
    simulador = FakeSimuladorCusto(custo_por_ponto=23810.0)

    cenarios = propor_cenarios(parametros_black_friday(), _orcamento(20000.0, 23736.14), [], simulador)

    assert [p.pct_acrescimo for p in simulador.simulados] == [0.84, 0.83]
    assert cenarios[0].pct_acrescimo == 0.83


def test_sem_recalculo_nao_inventa_cenario_de_percentual() -> None:
    cenarios = propor_cenarios(
        parametros_black_friday(), _orcamento(20000.0, 23736.14), [], FakeSimuladorCusto(1.0, falhar=True)
    )

    assert cenarios == []


def test_sem_a_marca_que_mais_pesa_usa_a_quebra_aditiva() -> None:
    por_marca = [_marca("10", 19337.86), _marca("30", 4398.28)]

    cenarios = propor_cenarios(
        parametros_black_friday(), _orcamento(30000.0, 23736.14), por_marca, FakeSimuladorCusto(23736.14)
    )

    sem_marca = next(c for c in cenarios if c.tipo == "sem_marca")
    assert sem_marca.titulo == "Sem a marca Preto" and sem_marca.marcas_alvo == ["30"]
    assert sem_marca.custo_incremental == 4398.28 and sem_marca.economia == 19337.86


def test_uma_marca_so_nao_gera_cenario_sem_marca() -> None:
    cenarios = propor_cenarios(
        parametros_black_friday(), _orcamento(30000.0, 100.0), [_marca("30", 100.0)], FakeSimuladorCusto(100.0)
    )

    assert all(c.tipo != "sem_marca" for c in cenarios)
