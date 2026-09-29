from fastapi import FastAPI
from app.agent.router import router as agent_router
from app.simulacao.router import router as simulacao_router

app = FastAPI(title="lana-ai")

app.include_router(agent_router)
app.include_router(simulacao_router)

@app.get("/")
def read_root():
    return {"status": "lana-ai is running"}