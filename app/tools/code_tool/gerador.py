"""Geradores do código da regra.

`GeradorCodigoLlm` é a ferramenta da A6-37. `GeradorCodigoModelo` é o plano B da demo:
preenche um modelo fixo com os parâmetros, sem LLM, e passa pela mesma validação e execução.
"""
from pathlib import Path
from typing import Protocol

from langchain_core.language_models import BaseChatModel

from app.core.config import extract_text
from app.tools.code_tool.codigo import extrair_codigo, validar_codigo
from app.tools.code_tool.dtos import CodigoGerado, ContextoGeracao
from app.tools.code_tool.prompt import montar_prompt_geracao

CAMINHO_MODELO = Path(__file__).with_name("modelo_acrescimo_pct.py.txt")


class GeradorCodigo(Protocol):
    def gerar(self, contexto: ContextoGeracao, erro_anterior: str | None) -> CodigoGerado: ...


class GeradorCodigoLlm:
    """Ex.: GeradorCodigoLlm(get_ai_model()).gerar(contexto, erro_anterior=None).fonte"""

    def __init__(self, modelo: BaseChatModel) -> None:
        self._modelo = modelo

    def gerar(self, contexto: ContextoGeracao, erro_anterior: str | None) -> CodigoGerado:
        resposta = self._modelo.invoke(montar_prompt_geracao(contexto, erro_anterior))
        return CodigoGerado(fonte=extrair_codigo(extract_text(resposta)), origem="llm")


class GeradorCodigoModelo:
    """Plano B: código determinístico para acréscimo de % em janela de datas."""

    def gerar(self, contexto: ContextoGeracao, erro_anterior: str | None) -> CodigoGerado:
        p = contexto.parametros
        fonte = CAMINHO_MODELO.read_text(encoding="utf-8").format(
            data_inicio=p.data_inicio.isoformat(), data_fim=p.data_fim.isoformat(),
            pct_acrescimo=p.pct_acrescimo, marcas_alvo=p.marcas_alvo, cargos_alvo=p.cargos_alvo,
        )
        validar_codigo(fonte)
        return CodigoGerado(fonte=fonte, origem="modelo")
