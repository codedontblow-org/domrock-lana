from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.agent.service import lana_invoke
from pydantic import BaseModel

class AgentEvents(BaseModel):
    type: str
    tool: str
    args: dict | None = None
    result: str | None = None

class AgentRequest(BaseModel):
    chat_id: str
    message: str
    # Regra como está no painel (com as edições do usuário), para o agente partir dela.
    regra: dict[str, Any] | None = None


class AgentResponse(BaseModel):
    chat_id: str
    response: str
    events: list[AgentEvents] = []
    # Regra registrada neste turno (contrato de estrutura_parametros_regra), para o painel de revisão.
    regra: dict[str, Any] | None = None

router = APIRouter(prefix="/agent", tags=["agent"])

MENSAGEM_COTA = (
    "A Lana atingiu o limite de uso do provedor de IA neste minuto. Aguarde cerca de 1 minuto "
    "e envie a mensagem de novo."
)


@router.post("/invoke", response_model=AgentResponse)
def invoke(body: AgentRequest) -> AgentResponse | JSONResponse:
    try:
        return lana_invoke(body.chat_id, body.message, body.regra)
    except Exception as erro:
        # Cota da LLM (429) vira 503 com mensagem para o usuário, não um 500 sem explicação.
        if _eh_limite_de_cota(erro):
            return JSONResponse(status_code=503, content={"etapa": "cota_llm", "mensagem": MENSAGEM_COTA})
        raise


def _eh_limite_de_cota(erro: Exception) -> bool:
    texto = f"{type(erro).__name__} {erro}"
    return "RateLimit" in texto or "RESOURCE_EXHAUSTED" in texto or "429" in texto