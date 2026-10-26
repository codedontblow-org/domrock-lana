"""Orquestra a simulação: valida a regra, apura o baseline, gera e executa o código da regra,
confere o resultado e resume. A LLM só entra na geração do código e na redação final.
"""
from dataclasses import dataclass, replace

import pandas as pd

from app.core.config import get_settings
from app.simulacao.assercoes import AssercaoViolada, conferir_contra_referencia, conferir_resultado
from app.simulacao.bases import BasesSimulacao, FonteBases, competencias_do_periodo
from app.simulacao.vigencia import (
    CampanhaContexto, calcular_baseline_vigente, calcular_periodos, detectar_conflitos, fontes_da_vigente,
)
from app.simulacao.cenarios import SimularCusto, propor_cenarios
from app.simulacao.dtos import ResultadoSimulacao
from app.simulacao.especificacao import CatalogoEspecificacao
from app.simulacao.explicacao import Explicador
from app.simulacao.resumo import (
    RESSALVAS, avaliar_meta, avaliar_orcamento, calcular_totais, maiores_lojas, medir_impacto, quebrar_por,
)
from app.simulacao.trilha import Cronometro, ExecucaoSimulada, montar_trilha_simulacao
from app.tools.code_tool.dtos import CodigoGerado, ContextoGeracao
from app.tools.code_tool.gerador import GeradorCodigo, GeradorCodigoModelo
from app.tools.code_tool.runner import CodeRunner
from app.tools.regra_tool.dtos import ParametrosSimulacao, RegraCampanha
from app.tools.regra_tool.parametros import ler_parametros

LINHAS_AMOSTRA = 10
CAMPOS_EXPLICACAO = {"totais", "por_marca", "por_cargo", "orcamento", "meta", "impacto", "maiores_lojas", "cenarios"}


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
    observacao: str = ""


CONFERIDO = "Resultado da IA conferido com o cálculo determinístico."
USOU_REFERENCIA = (
    "O código da IA divergiu do cálculo determinístico em todas as tentativas; "
    "o resultado mostrado é o do cálculo determinístico."
)


class SimuladorCampanha:
    """Ex.: SimuladorCampanha(fonte, gerador, SubprocessRunner(), explicador, referencia).simular(regra)

    `referencia` gera o código determinístico do mesmo contrato; quando existe, todo resultado
    da IA é conferido contra ele. O contrato da Sprint 1 tem forma fixa, então sempre há referência.
    `recalculo` gera o código determinístico que simula de novo os cenários alternativos.
    `especificacao` traz as campanhas da especificação, que somam às do sistema na % vigente.
    """

    def __init__(
        self, fonte_bases: FonteBases, gerador: GeradorCodigo, runner: CodeRunner,
        explicador: Explicador, referencia: GeradorCodigo | None = None, max_tentativas: int = 2,
        recalculo: GeradorCodigo | None = None, especificacao: CatalogoEspecificacao | None = None,
    ) -> None:
        self._fonte_bases, self._gerador, self._runner = fonte_bases, gerador, runner
        self._explicador, self._referencia, self._max_tentativas = explicador, referencia, max_tentativas
        self._recalculo = recalculo or GeradorCodigoModelo()
        self._especificacao = especificacao

    def simular(self, regra: RegraCampanha, campanhas: list[CampanhaContexto] | None = None) -> ResultadoSimulacao:
        parametros = ler_parametros(regra)
        competencias = competencias_do_periodo(parametros.data_inicio, parametros.data_fim)
        cronometro = Cronometro()
        with cronometro.medir("carregar_bases"):
            bases = self._carregar(competencias)
        fontes = self._campanhas_da_especificacao() + list(campanhas or [])
        periodos = calcular_periodos(parametros, bases.comissoes, fontes)
        conflitos = detectar_conflitos(parametros, fontes)
        with cronometro.medir("comissao_atual"):
            baseline = calcular_baseline_vigente(bases, fontes)
        contexto = ContextoGeracao(parametros, competencias, _amostras(bases, baseline))
        with cronometro.medir("conferir"):
            conferencia = self._executar_referencia(contexto, bases, baseline)
        aprovada = self._gerar_e_executar(contexto, bases, baseline, conferencia, cronometro)
        with cronometro.medir("resumir"):
            resultado = self._resumir(regra.rule_id, contexto, bases, baseline, aprovada)
        trilha = montar_trilha_simulacao(ExecucaoSimulada(
            parametros=parametros, competencias=competencias, bases=bases, baseline=baseline,
            modelo=_modelo_da_ia(aprovada), tentativas=aprovada.numero,
            conferido=CONFERIDO in aprovada.observacao, usou_referencia=USOU_REFERENCIA in aprovada.observacao,
            linhas_executadas=len(aprovada.comparacao), totais=resultado.totais,
            campanhas=fontes_da_vigente(fontes, periodos), tempos=cronometro.tempos,
        ))
        return resultado.model_copy(update={"comissao_periodo": periodos, "conflitos": conflitos, "trilha": trilha})

    def _campanhas_da_especificacao(self) -> list[CampanhaContexto]:
        return self._especificacao.campanhas() if self._especificacao else []

    def _carregar(self, competencias: list[str]) -> BasesSimulacao:
        bases = self._fonte_bases.carregar(competencias)
        sem_dados = sorted(set(competencias) - set(bases.rh["competencia"]))
        if sem_dados:
            raise SimulacaoFalhouError("dados", f"Sem base de RH para {sem_dados}; importe essas competências")
        return bases

    def _executar_referencia(
        self, contexto: ContextoGeracao, bases: BasesSimulacao, baseline: pd.DataFrame,
    ) -> TentativaAprovada | None:
        if self._referencia is None:
            return None
        codigo = self._referencia.gerar(contexto, None)
        return TentativaAprovada(codigo, self._executar(codigo, contexto, bases, baseline), 0)

    def _gerar_e_executar(
        self, contexto: ContextoGeracao, bases: BasesSimulacao, baseline: pd.DataFrame,
        conferencia: TentativaAprovada | None, cronometro: Cronometro,
    ) -> TentativaAprovada:
        erro: str | None = None
        codigo: CodigoGerado | None = None
        for numero in range(1, self._max_tentativas + 1):
            try:
                with cronometro.medir("gerar_codigo"):
                    codigo = self._gerador.gerar(contexto, erro)
                with cronometro.medir("executar_sandbox"):
                    comparacao = self._executar(codigo, contexto, bases, baseline)
                if conferencia is None:
                    return TentativaAprovada(codigo, comparacao, numero)
                with cronometro.medir("conferir"):
                    conferir_contra_referencia(comparacao, conferencia.comparacao)
                return TentativaAprovada(codigo, comparacao, numero, CONFERIDO)
            # Qualquer falha da tentativa (LLM fora/429, código inválido, retorno com tipo errado)
            # vira nova tentativa e, no fim, um 422 com a causa, nunca um 500 genérico.
            except Exception as falha:
                erro = f"{type(falha).__name__}: {falha}"
        if conferencia is not None:
            return replace(conferencia, numero=self._max_tentativas, observacao=f"{USOU_REFERENCIA} Último erro: {erro}")
        raise SimulacaoFalhouError("geracao_codigo", erro or "sem detalhe", codigo.fonte if codigo else None)

    def _executar(
        self, codigo: CodigoGerado, contexto: ContextoGeracao, bases: BasesSimulacao, baseline: pd.DataFrame,
    ) -> pd.DataFrame:
        execucao = self._runner.executar(codigo.fonte, bases.como_dict(), baseline, contexto.competencias)
        if not execucao.ok or execucao.apuracao_simulada is None or execucao.contribuicoes is None:
            raise ExecucaoFalhouError(f"{execucao.status}: {execucao.mensagem}")
        return conferir_resultado(baseline, execucao.apuracao_simulada, execucao.contribuicoes, contexto.parametros)

    def _resumir(
        self, rule_id: str, contexto: ContextoGeracao, bases: BasesSimulacao,
        baseline: pd.DataFrame, aprovada: TentativaAprovada,
    ) -> ResultadoSimulacao:
        comparacao, parametros = aprovada.comparacao, contexto.parametros
        totais = calcular_totais(comparacao)
        orcamento = avaliar_orcamento(totais, parametros.orcamento_limite)
        por_marca = quebrar_por(comparacao, "cod_marca")
        meta = avaliar_meta(bases.vendas, parametros)
        resultado = ResultadoSimulacao(
            rule_id=rule_id, competencias=contexto.competencias, totais=totais,
            por_marca=por_marca, por_cargo=quebrar_por(comparacao, "cod_cargo"),
            orcamento=orcamento, meta=meta,
            impacto=medir_impacto(comparacao), maiores_lojas=maiores_lojas(comparacao),
            cenarios=propor_cenarios(parametros, orcamento, por_marca, self._custo_com(contexto, bases, baseline)),
            ressalvas=RESSALVAS, codigo=aprovada.codigo.fonte, origem_codigo=aprovada.codigo.origem,
            tentativas=aprovada.numero, explicacao="", observacao=aprovada.observacao,
        )
        resumo = resultado.model_dump(include=CAMPOS_EXPLICACAO)
        return resultado.model_copy(update={"explicacao": self._explicador.explicar(resumo)})

    def _custo_com(self, contexto: ContextoGeracao, bases: BasesSimulacao, baseline: pd.DataFrame) -> SimularCusto:
        """Simula de novo, com o código determinístico, a mesma regra com outros parâmetros."""
        def simular_custo(parametros: ParametrosSimulacao) -> float | None:
            variante = replace(contexto, parametros=parametros)
            try:
                comparacao = self._executar(self._recalculo.gerar(variante, None), variante, bases, baseline)
            except (ExecucaoFalhouError, AssercaoViolada):  # cenário é acessório: sem ele, o resultado segue
                return None
            return calcular_totais(comparacao).diferenca
        return simular_custo


def _modelo_da_ia(aprovada: TentativaAprovada) -> str:
    """O modelo que escreveu o código, ou a origem do código fixo (ex.: "modelo")."""
    # Com USOU_REFERENCIA o código aprovado é o fixo, mas quem divergiu nas tentativas foi a IA.
    if aprovada.codigo.origem in ("llm", "fake") or USOU_REFERENCIA in aprovada.observacao:
        return get_settings().AI_MODEL
    return aprovada.codigo.origem


def _amostras(bases: BasesSimulacao, baseline: pd.DataFrame) -> dict[str, str]:
    tabelas = {**bases.como_dict(), "vendas": _amostra_vendas(bases.vendas), "apuracao_base": baseline}
    return {nome: tabela.head(LINHAS_AMOSTRA).to_csv(index=False) for nome, tabela in tabelas.items()}


def _amostra_vendas(vendas: pd.DataFrame) -> pd.DataFrame:
    """Metade do início e metade do fim por data, para mostrar datas reais além do dia 1º."""
    ordenadas = vendas.sort_values("data_venda")
    metade = LINHAS_AMOSTRA // 2
    return pd.concat([ordenadas.head(metade), ordenadas.tail(metade)])
