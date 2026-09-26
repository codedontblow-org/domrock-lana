"""Executa o harness de verdade em subprocesso (~1 s por caso, por causa do import do pandas)."""
from app.simulacao.baseline import calcular_baseline
from app.tools.code_tool.runner import SubprocessRunner
from tests.fakes import bases_pequenas, fonte_modelo, parametros_black_friday

CABECALHO = "def aplicar_regra(bases, apuracao_base, competencias):\n"


def _executar(fonte: str, timeout_s: int = 20):
    bases = bases_pequenas()
    return SubprocessRunner(timeout_s=timeout_s).executar(
        fonte, bases.como_dict(), calcular_baseline(bases), ["2025-11"]
    )


def test_runner_executa_o_modelo_e_devolve_as_tabelas() -> None:
    execucao = _executar(fonte_modelo(parametros_black_friday()))

    assert execucao.ok, execucao.mensagem
    assert execucao.apuracao_simulada is not None
    assert sorted(execucao.contribuicoes["matricula"]) == ["M1", "M2"]  # G1 é gerente: fora


def test_runner_reporta_excecao_do_codigo_gerado() -> None:
    execucao = _executar(CABECALHO + "    raise KeyError('coluna_x')\n")

    assert execucao.status == "erro_codigo"
    assert "KeyError" in execucao.mensagem


def test_runner_reporta_retorno_fora_do_contrato() -> None:
    execucao = _executar(CABECALHO + "    return {'apuracao_simulada': 1}\n")

    assert execucao.status == "erro_codigo"
    assert "Esperado DataFrame" in execucao.mensagem


def test_runner_interrompe_loop_infinito_por_timeout() -> None:
    execucao = _executar(CABECALHO + "    while True:\n        pass\n", timeout_s=2)

    assert execucao.status == "timeout"


def test_runner_bloqueia_escrita_em_disco_mesmo_se_passar_pela_validacao() -> None:
    fonte = CABECALHO + "    import pathlib\n    pathlib.Path('x.txt').write_text('a' * 10)\n    return {}\n"

    execucao = _executar(fonte)

    assert not execucao.ok
