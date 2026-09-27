"""Dados e dublês compartilhados pelos testes da simulação (sem banco e sem LLM)."""
from datetime import date

import pandas as pd

from app.simulacao.bases import BasesSimulacao
from app.tools.code_tool.dtos import CodigoGerado, ContextoGeracao
from app.tools.code_tool.gerador import GeradorCodigoModelo
from app.tools.regra_tool.dtos import ParametrosSimulacao

# Loja 1 (marca 30): M1 vendedor (100) e G1 gerente (150). Loja 2 (marca 10): M2 vendedor.
RH = pd.DataFrame({
    "matricula": ["M1", "G1", "M2"],
    "competencia": ["2025-11"] * 3,
    "cod_loja": ["1", "1", "2"],
    "cod_marca": ["30", "30", "10"],
    "cod_cargo": ["100", "150", "100"],
    "data_admissao": pd.to_datetime(["2020-01-01"] * 3),
    "data_demissao": pd.to_datetime([None] * 3),
})
VENDAS = pd.DataFrame({
    "matricula": ["M1", "M1", "G1", "M2"],
    "competencia": ["2025-11"] * 4,
    "data_venda": pd.to_datetime(["2025-11-01", "2025-11-25", "2025-11-01", "2025-11-26"]),
    "vlr_venda": [1000.0, 500.0, 200.0, 800.0],
    "cod_loja": ["1", "1", "1", "2"],
    "cod_marca": ["30", "30", "30", "10"],
    "cod_cargo": ["100", "100", "150", "100"],
})
COMISSOES = pd.DataFrame({
    "cod_marca": ["30", "30", "10"],
    "cod_cargo": ["100", "150", "100"],
    "pct_comiss": [2.0, 1.0, 3.0],
})


def bases_pequenas() -> BasesSimulacao:
    return BasesSimulacao(rh=RH.copy(), vendas=VENDAS.copy(), comissoes=COMISSOES.copy())


def parametros_black_friday(**sobrescrever: object) -> ParametrosSimulacao:
    valores = {
        "data_inicio": date(2025, 11, 24), "data_fim": date(2025, 11, 30), "pct_acrescimo": 1.0,
        "marcas_alvo": ["10", "30"], "cargos_alvo": ["100", "200", "300"],
        "meta_vendas": 1000.0, "orcamento_limite": 20.0,
    }
    return ParametrosSimulacao(**{**valores, **sobrescrever})


class FakeFonteBases:
    def __init__(self, bases: BasesSimulacao) -> None:
        self.bases = bases
        self.competencias_pedidas: list[list[str]] = []

    def carregar(self, competencias: list[str]) -> BasesSimulacao:
        self.competencias_pedidas.append(competencias)
        return self.bases


class FakeGeradorSequencial:
    """Devolve um fonte por tentativa e registra o erro recebido em cada uma."""

    def __init__(self, fontes: list[str]) -> None:
        self._fontes = fontes
        self.erros_recebidos: list[str | None] = []

    def gerar(self, contexto: ContextoGeracao, erro_anterior: str | None) -> CodigoGerado:
        self.erros_recebidos.append(erro_anterior)
        indice = min(len(self.erros_recebidos), len(self._fontes)) - 1
        return CodigoGerado(fonte=self._fontes[indice], origem="fake")


class FakeGeradorLlmIndisponivel:
    """Simula a LLM fora do ar (ex.: 429 do Gemini) na primeira tentativa."""

    def __init__(self, fonte_depois: str) -> None:
        self._fonte_depois = fonte_depois
        self.chamadas = 0

    def gerar(self, contexto: ContextoGeracao, erro_anterior: str | None) -> CodigoGerado:
        self.chamadas += 1
        if self.chamadas == 1:
            raise ConnectionError("429 RESOURCE_EXHAUSTED")
        return CodigoGerado(fonte=self._fonte_depois, origem="fake")


class FakeExplicador:
    def __init__(self) -> None:
        self.resumos: list[dict[str, object]] = []

    def explicar(self, resumo: dict[str, object]) -> str:
        self.resumos.append(resumo)
        return "explicação fake"


class FakeSimuladorCusto:
    """Custo proporcional ao % (como a regra real), e registra cada parâmetro simulado."""

    def __init__(self, custo_por_ponto: float, falhar: bool = False) -> None:
        self.custo_por_ponto, self.falhar = custo_por_ponto, falhar
        self.simulados: list[ParametrosSimulacao] = []

    def __call__(self, parametros: ParametrosSimulacao) -> float | None:
        self.simulados.append(parametros)
        return None if self.falhar else round(parametros.pct_acrescimo * self.custo_por_ponto, 2)


def fonte_modelo(parametros: ParametrosSimulacao) -> str:
    contexto = ContextoGeracao(parametros, ["2025-11"], {})
    return GeradorCodigoModelo().gerar(contexto, None).fonte
