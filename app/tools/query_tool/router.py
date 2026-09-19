from fastapi import APIRouter
from app.tools.query_tool.dtos import QueryRequestBody, QueryResponseBody
from app.tools.query_tool.service import executar

router = APIRouter(prefix="/sql", tags=["query_tool"])

@router.post("/query", response_model=QueryResponseBody)
def query(body: QueryRequestBody):
    return executar(body)