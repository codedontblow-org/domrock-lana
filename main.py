import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.agent.router import router as agent_router
from app.simulacao.router import router as simulacao_router
from app.grpc_server import serve_grpc  # Ajusta o caminho para onde está a tua função serve_grpc

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Inicia o servidor gRPC em background
    grpc_task = asyncio.create_task(serve_grpc())
    print("🚀 Servidor gRPC iniciado em background na porta 50051")
    
    yield  # Mantém o FastAPI e as rotas HTTP a rodar normalmente
    
    # 2. Encerra o gRPC ao desligar a aplicação
    grpc_task.cancel()
    try:
        await grpc_task
    except asyncio.CancelledError:
        print("🛑 Servidor gRPC encerrado com sucesso")

app = FastAPI(title="lana-ai", lifespan=lifespan)

# Mantém todos os teus routers HTTP ativos
app.include_router(agent_router)
app.include_router(simulacao_router)

@app.get("/")
def read_root():
    return {
        "status": "lana-ai is running",
        "grpc": "active on port 50051"
    }