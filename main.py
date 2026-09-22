from fastapi import FastAPI
from app.agent.router import router as agent_router
from app.tools.query_tool.router import router as query_router

app = FastAPI(title="lana-ai")

app.include_router(agent_router)
app.include_router(query_router)

@app.get("/")
def read_root():
    return {"status": "lana-ai is running"}