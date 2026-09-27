from functools import lru_cache

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_ai_model, get_settings
from app.core.db import get_connection
from app.simulacao.bases import PostgresFonteBases
from app.simulacao.baseline import BaselineError
from app.simulacao.dtos import ResultadoSimulacao, SimulacaoRequest
from app.simulacao.explicacao import ExplicadorLlm
from app.simulacao.service import SimulacaoFalhouError, SimuladorCampanha
from app.tools.code_tool.gerador import GeradorCodigo, GeradorCodigoLlm, GeradorCodigoModelo
from app.tools.code_tool.runner import SubprocessRunner
from app.tools.regra_tool.parametros import RegraInvalidaError

router = APIRouter(prefix="/simulacao", tags=["simulacao"])


@lru_cache
def get_simulador() -> SimuladorCampanha:
    modelo = get_ai_model()
    modo = get_settings().CODEGEN_MODO
    return SimuladorCampanha(
        fonte_bases=PostgresFonteBases(get_connection),
        gerador=_escolher_gerador(modo),
        runner=SubprocessRunner(),
        explicador=ExplicadorLlm(modelo),
        # Confere o código da IA contra o cálculo determinístico do mesmo contrato.
        referencia=GeradorCodigoModelo() if modo == "llm" else None,
    )


def _escolher_gerador(modo: str) -> GeradorCodigo:
    if modo == "modelo":
        return GeradorCodigoModelo()
    if modo == "llm":
        return GeradorCodigoLlm(get_ai_model())
    raise ValueError(f"CODEGEN_MODO inválido: {modo!r}; esperado 'llm' ou 'modelo'")


@router.post("", response_model=ResultadoSimulacao)
def simular(body: SimulacaoRequest) -> ResultadoSimulacao | JSONResponse:
    try:
        return get_simulador().simular(body.regra)
    except RegraInvalidaError as erro:
        return _falha("validacao", "Regra incompleta ou inválida", erros=erro.erros)
    except SimulacaoFalhouError as erro:
        return _falha(erro.etapa, erro.mensagem, codigo=erro.codigo)
    except BaselineError as erro:
        return _falha("baseline", str(erro))


def _falha(etapa: str, mensagem: str, **extras: object) -> JSONResponse:
    return JSONResponse(status_code=422, content={"etapa": etapa, "mensagem": mensagem, **extras})
