"""Trilha da simulação (contrato 2.2): os 6 passos fixos, nesta ordem, montados pelo código.

carregar_bases → comissao_atual → gerar_codigo → executar_sandbox → conferir → resumir. Cada
descrição sai dos números da própria simulação; a LLM não escreve nada aqui (A6-70).

Ex.: montar_trilha_simulacao(execucao).passos[0].descricao
     -> "Bases de nov/2025: 469 pessoas no RH, 721 vendas de 24/11 a 30/11, 24 linhas de % por marca e cargo"
"""
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import pandas as pd

from app.core.trilha import PassoTrilha, competencias_por_extenso
from app.simulacao.bases import SQL_DAS_BASES, TABELAS_DAS_BASES, BasesSimulacao
from app.simulacao.dtos import TotaisSimulacao, TrilhaSimulacao
from app.simulacao.resumo import gerar_premissas, vendas_do_periodo
from app.simulacao.texto_humano import formatar_reais
from app.simulacao.vigencia import HistoricoComissao
from app.tools.dtos import calcular_tempo_ms
from app.tools.regra_tool.dtos import ParametrosSimulacao

# O que conferir_resultado (assercoes.py) verifica em toda execução; a referência entra quando conferida.
CONFERENCIAS = [
    "colunas obrigatórias", "mesmas pessoas e meses da comissão atual", "sem comissão negativa",
    "contribuições somam a diferença", "escopo da regra",
]
CONFERENCIA_REFERENCIA = "cálculo de referência"


class Cronometro:
    """Tempo de cada passo em ms, somado entre tentativas. Ex.: with cronometro.medir("conferir"): ..."""

    def __init__(self) -> None:
        self.tempos: dict[str, int] = {}

    @contextmanager
    def medir(self, passo: str) -> Iterator[None]:
        inicio = time.perf_counter()
        try:
            yield
        finally:
            self.tempos[passo] = self.tempos.get(passo, 0) + calcular_tempo_ms(inicio)


@dataclass(frozen=True)
class ExecucaoSimulada:
    """O que a trilha lê da simulação. `conferido`: a IA bateu com a referência; `usou_referencia`: não bateu."""

    parametros: ParametrosSimulacao
    competencias: list[str]
    bases: BasesSimulacao
    baseline: pd.DataFrame
    modelo: str
    tentativas: int
    conferido: bool
    usou_referencia: bool
    linhas_executadas: int
    totais: TotaisSimulacao
    campanhas: list[HistoricoComissao]
    tempos: dict[str, int]


def montar_trilha_simulacao(execucao: ExecucaoSimulada) -> TrilhaSimulacao:
    passos = [
        _carregar_bases(execucao), _comissao_atual(execucao), _gerar_codigo(execucao),
        _executar_sandbox(execucao), _conferir(execucao), _resumir(execucao),
    ]
    for passo in passos:
        passo.tempo_ms = execucao.tempos.get(passo.ferramenta, 0)
    return TrilhaSimulacao(
        modelo=execucao.modelo, tentativas=execucao.tentativas, premissas=gerar_premissas(execucao.parametros),
        passos=passos, campanhas=execucao.campanhas,
    )


def _carregar_bases(execucao: ExecucaoSimulada) -> PassoTrilha:
    bases, parametros = execucao.bases, execucao.parametros
    pessoas = int(bases.rh["matricula"].nunique())
    vendas = len(vendas_do_periodo(bases.vendas, parametros))
    periodo = f"{parametros.data_inicio:%d/%m} a {parametros.data_fim:%d/%m}"
    descricao = (
        f"Bases de {competencias_por_extenso(execucao.competencias)}: {pessoas} pessoas no RH, "
        f"{vendas} vendas de {periodo}, {len(bases.comissoes)} linhas de % por marca e cargo"
    )
    return PassoTrilha(
        ordem=1, ferramenta="carregar_bases", descricao=descricao, tabelas_acessadas=list(TABELAS_DAS_BASES),
        competencias=execucao.competencias, sql_executado=SQL_DAS_BASES,
        filtros=f"vendas de {parametros.data_inicio:%d/%m/%Y} a {parametros.data_fim:%d/%m/%Y}; "
                f"marcas {', '.join(parametros.marcas_alvo)}",
        registros_retornados=len(bases.rh) + len(bases.vendas) + len(bases.comissoes),
    )


def _comissao_atual(execucao: ExecucaoSimulada) -> PassoTrilha:
    total = float(execucao.baseline["comissao"].sum())
    return PassoTrilha(
        ordem=2, ferramenta="comissao_atual", descricao=f"Comissão atual (regras 5a a 5g): {formatar_reais(total)}",
        competencias=execucao.competencias, registros_retornados=len(execucao.baseline),
    )


def _gerar_codigo(execucao: ExecucaoSimulada) -> PassoTrilha:
    tentativas = f"{execucao.tentativas} {'tentativa' if execucao.tentativas == 1 else 'tentativas'}"
    if execucao.usou_referencia:
        descricao = (f"O código gerado por {execucao.modelo} divergiu do cálculo de referência em {tentativas}; "
                     "valeu o cálculo de referência")
    elif execucao.conferido:
        descricao = f"Código gerado por {execucao.modelo} em {tentativas}, conferido com o cálculo de referência"
    else:
        descricao = f"Código gerado por {execucao.modelo} em {tentativas}"
    return PassoTrilha(ordem=3, ferramenta="gerar_codigo", descricao=descricao)


def _executar_sandbox(execucao: ExecucaoSimulada) -> PassoTrilha:
    return PassoTrilha(ordem=4, ferramenta="executar_sandbox", descricao="Código executado no sandbox",
                       registros_retornados=execucao.linhas_executadas)


def _conferir(execucao: ExecucaoSimulada) -> PassoTrilha:
    conferencias = CONFERENCIAS + ([CONFERENCIA_REFERENCIA] if execucao.conferido else [])
    descricao = f"{len(conferencias)} conferências passaram: {', '.join(conferencias)}"
    return PassoTrilha(ordem=5, ferramenta="conferir", descricao=descricao)


def _resumir(execucao: ExecucaoSimulada) -> PassoTrilha:
    return PassoTrilha(ordem=6, ferramenta="resumir",
                       descricao=f"Custo adicional de {formatar_reais(execucao.totais.diferenca)}")
