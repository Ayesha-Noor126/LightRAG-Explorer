from fastapi import APIRouter, HTTPException

from app.models.schemas import QueryRequest, QueryResponse
from app.services import simple_rag_service as rag
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/query", tags=["query"])
logger = get_logger(__name__)


@router.post("/simple-rag", response_model=QueryResponse)
async def query_simple_rag(request: QueryRequest):
    try:
        return rag.answer_query(request.question, request.top_k)
    except RuntimeError as e:
        # e.g. missing GEMINI_API_KEY
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("Query failed")
        raise HTTPException(status_code=500, detail="Query failed. Check server logs.")
