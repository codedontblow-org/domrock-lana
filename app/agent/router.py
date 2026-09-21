from fastapi import APIRouter
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


class AgentResponse(BaseModel):
    chat_id: str
    response: str
    events: list[AgentEvents] = []

router = APIRouter(prefix="/agent", tags=["agent"])

@router.post("/invoke", response_model=AgentResponse)
def invoke(body: AgentRequest):
    return lana_invoke(body.chat_id, body.message)