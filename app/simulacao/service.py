"""Orquestra a simulação: valida a regra, apura o baseline, gera e executa o código da regra,
confere o resultado e resume. A LLM só entra na geração do código e na redação final.
"""
from dataclasses import dataclass

import pandas as pd

from app.simulacao.assercoes import AssercaoViolada, conferir_resultado
from app.simulacao.bases import BasesSimulacao, FonteBases, competencias_do_periodo
from app.simulacao.baseline import calcular_baseline
from app.simulacao.dtos import ResultadoSimulacao
from app.simulacao.explicacao import Explicador
from app.simulacao.resumo import avaliar_meta, avaliar_orcamento, calcular_totais, quebrar_por
from app.tools.code_tool.codigo import CodigoInvalidoError
from app.tools.code_tool.dtos import CodigoGerado, ContextoGeracao
from app.tools.code_tool.gerador import GeradorCodigo
from app.tools.code_tool.runner import CodeRunner
from app.tools.regra_tool.dtos import ParametrosSimulacao, RegraCampanha
from app.tools.regra_tool.parametros import ler_parametros

LINHAS_AMOSTRA = 10


class SimulacaoFalhouError(RuntimeError):
    """Nenhuma tentativa produziu resultado válido. Nunca se devolve resultado parcial."""

    def __init__(self, etapa: str, mensagem: str, codigo: str | None = None) -> None:
        super().__init__(f"{etapa}: {mensagem}")
        self.etapa, self.mensagem, self.codigo = etapa, mensagem, codigo


class ExecucaoFalhouError(RuntimeError):
    """O código gerado falhou ao rodar (erro, timeout ou saída inválida)."""


@dataclass(frozen=True)
class TentativaAprovada:
    codigo: CodigoGerado
    comparacao: pd.DataFrame
    numero: int


class SimuladorCampanha:
    """Ex.: SimuladorCampanha(fonte, gerador, SubprocessRunner(), explicador).simular(regra)"""

    def __init__(
        self, fonte_bases: FonteBases, gerador: GeradorCodigo, runner: CodeRunner,
        explicador: Explicador, max_tentativas: int = 2,
    ) -> None:
        self._fonte_bases, self._gerador, self._runner = fonte_bases, gerador, runner
        self._explicador, self._max_tentativas = explicador, max_tentativas

    def simular(self, regra: RegraCampanha) -> ResultadoSimulacao:
        parametros = ler_parametros(regra)
        competencias = competencias_do_periodo(parametros.data_inicio, parametros.data_fim)
        bases = self._carregar(competencias)
        baseline = calcular_baseline(bases)
        contexto = ContextoGeracao(parametros, competencias, _amostras(bases, baseline))
        aprovada = self._gerar_e_executar(contexto, bases, baseline)
        return self._resumir(regra.rule_id, parametros, competencias, bases, aprovada)

    def _carregar(self, competencias: list[str]) -> BasesSimulacao:
        bases = self._fonte_bases.carregar(competencias)
        sem_dados = sorted(set(competencias) - set(bases.rh["competencia"]))
        if sem_dados:
            raise SimulacaoFalhouError("dados", f"Sem base de RH para {sem_dados}; importe essas competências")
        return bases

    def _gerar_e_executar(
        self, contexto: ContextoGeracao, bases: BasesSimulacao, baseline: pd.DataFrame,
    ) -> TentativaAprovada:
        erro: str | None = None
        codigo: CodigoGerado | None = None
        for numero in range(1, self._max_tentativas + 1):
            try:
                codigo = self._gerador.gerar(contexto, erro)
                comparacao = self._executar(codigo, contexto, bases, baseline)
                return TentativaAprovada(codigo, comparacao, numero)
            except (CodigoInvalidoError, AssercaoViolada, ExecucaoFalhouError) as falha:
                erro = str(falha)
        raise SimulacaoFalhouError("geracao_codigo", erro or "sem detalhe", codigo.fonte if codigo else None)

    def _executar(
        self, codigo: CodigoGerado, contexto: ContextoGeracao, bases: BasesSimulacao, baseline: pd.DataFrame,
    ) -> pd.DataFrame:
        execucao = self._runner.executar(codigo.fonte, bases.como_dict(), baseline, contexto.competencias)
        if not execucao.ok or execucao.apuracao_simulada is None or execucao.contribuicoes is None:
            raise ExecucaoFalhouError(f"{execucao.status}: {execucao.mensagem}")
        return conferir_resultado(baseline, execucao.apuracao_simulada, execucao.contribuicoes, contexto.parametros)

    def _resumir(
        self, rule_id: str, parametros: ParametrosSimulacao, competencias: list[str],
        bases: BasesSimulacao, aprovada: TentativaAprovada,
    ) -> ResultadoSimulacao:
        totais = calcular_totais(aprovada.comparacao)
        resultado = ResultadoSimulacao(
            rule_id=rule_id, competencias=competencias, totais=totais,
            por_marca=quebrar_por(aprovada.comparacao, "cod_marca"),
            por_cargo=quebrar_por(aprovada.comparacao, "cod_cargo"),
            orcamento=avaliar_orcamento(totais, parametros.orcamento_limite),
            meta=avaliar_meta(bases.vendas, parametros),
            codigo=aprovada.codigo.fonte, origem_codigo=aprovada.codigo.origem,
            tentativas=aprovada.numero, explicacao="",
        )
        resumo = resultado.model_dump(include={"totais", "por_marca", "por_cargo", "orcamento", "meta"})
        return resultado.model_copy(update={"explicacao": self._explicador.explicar(resumo)})


def _amostras(bases: BasesSimulacao, baseline: pd.DataFrame) -> dict[str, str]:
    tabelas = {**bases.como_dict(), "vendas": _amostra_vendas(bases.vendas), "apuracao_base": baseline}
    return {nome: tabela.head(LINHAS_AMOSTRA).to_csv(index=False) for nome, tabela in tabelas.items()}


def _amostra_vendas(vendas: pd.DataFrame) -> pd.DataFrame:
    """Metade do início e metade do fim por data, para mostrar datas reais além do dia 1º."""
    ordenadas = vendas.sort_values("data_venda")
    metade = LINHAS_AMOSTRA // 2
    return pd.concat([ordenadas.head(metade), ordenadas.tail(metade)])
