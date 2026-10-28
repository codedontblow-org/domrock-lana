from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.agent.service import lana_invoke
from pydantic import BaseModel

class AgentEvents(BaseModel):
    ferramenta: str
    descricao_legivel: str
    tempo: int
    situacao: str
    tabelas: list[str] | None = None
    competencias: list[str] | None = None
    filtros: Any | None = None
    registros: int | None = None
    sql: str | None = None
    args: dict[str, Any] | None = None
    result: Any | None = None

class AgentRequest(BaseModel):
    chat_id: str
    message: str
    # Regra como está no painel (com as edições do usuário), para o agente partir dela.
    regra: dict[str, Any] | None = None
    # Histórico de mensagens recebido do backend (A6-65).
    historico: list[dict[str, Any]] | None = None


class AgentResponse(BaseModel):
    chat_id: str
    response: str
    events: list[AgentEvents] = []
    # Regra registrada neste turno (contrato de estrutura_parametros_regra), para o painel de revisão.
    regra: dict[str, Any] | None = None
    # De onde veio cada número (contrato 2.2), montada pelo código; None quando não usou ferramenta.
    trilha: dict[str, Any] | None = None

router = APIRouter(prefix="/agent", tags=["agent"])

MENSAGEM_COTA = (
    "A Lana atingiu o limite de uso do provedor de IA neste minuto. Aguarde cerca de 1 minuto "
    "e envie a mensagem de novo."
)


@router.post("/invoke", response_model=AgentResponse)
def invoke(body: AgentRequest) -> AgentResponse | JSONResponse:
    try:
        return lana_invoke(body.chat_id, body.message, body.regra, body.historico)
    except Exception as erro:
        # Cota da LLM (429) vira 503 com mensagem para o usuário, não um 500 sem explicação.
        if limite_de_cota(erro):
            return JSONResponse(status_code=503, content={"etapa": "cota_llm", "mensagem": MENSAGEM_COTA})
        if tempo_esgotado(erro):
            return JSONResponse(status_code=504, content={"etapa": "tempo", "mensagem": MENSAGEM_TEMPO})
        raise


MENSAGEM_TEMPO = (
    "O provedor de IA demorou demais para responder e a chamada foi cortada. Envie a mensagem "
    "de novo em instantes."
)


def tempo_esgotado(erro: Exception) -> bool:
    """O provedor cortou a chamada por tempo: o Gemini devolve 504 DEADLINE_EXCEEDED quando passa do AI_TIMEOUT_S.

    Ex.: tempo_esgotado(RuntimeError("504 DEADLINE_EXCEEDED. Deadline expired")) -> True
    """
    return "DEADLINE_EXCEEDED" in str(erro) or "Timeout" in type(erro).__name__


def limite_de_cota(erro: Exception) -> bool:
    texto = f"{type(erro).__name__} {erro}"
    return "RateLimit" in texto or "RESOURCE_EXHAUSTED" in texto or "429" in texto