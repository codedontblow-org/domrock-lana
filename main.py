import threading
import asyncio
from fastapi import FastAPI
from pydantic import BaseModel

# Import do servidor gRPC
from app.grpc_server import serve

def start_grpc_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(serve())

app = FastAPI(title="Domrock Lana API")

@app.on_event("startup")
def startup_event():
    # Inicia o servidor gRPC em uma Thread separada ao subir o Uvicorn
    thread = threading.Thread(target=start_grpc_server, daemon=True)
    thread.start()

# --- SUA ROTA AGENT/INVOKE DIRETA ---
class AgentRequest(BaseModel):
    # Ajuste os campos do model conforme o seu contrato
    prompt: str
    contexto: str | None = None

@app.post("/agent/invoke")
async def invoke_agent(request: AgentRequest):
    # Coloque a sua lógica do agente aqui
    return {"resposta": "Sua resposta do agente aqui"}

@app.get("/")
def read_root():
    return {"status": "ok", "service": "Lana AI"}