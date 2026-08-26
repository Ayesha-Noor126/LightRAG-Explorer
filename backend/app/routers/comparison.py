import asyncio

from fastapi import APIRouter

from app.models.schemas import (
    CompareRequest,
    CompareResponse,
    LightRAGLatency,
    GraphEntity,
    GraphRelationship,
    LightRAGQueryResponse,
)
from app.services import lightrag_service
from app.services import simple_rag_service as rag
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/query", tags=["comparison"])
logger = get_logger(__name__)


async def _run_simple_rag(question: str):
    # simple_rag_service.answer_query is sync (embedding/Chroma/Gemini calls
    # are all blocking), so run it in a thread to stay concurrent with the
    # LightRAG call below.
    return await asyncio.to_thread(rag.answer_query, question)


async def _run_lightrag(question: str, mode: str):
    result = await lightrag_service.query(question, mode)
    return LightRAGQueryResponse(
        question=question,
        mode=mode,
        answer=result["answer"],
        entities=[GraphEntity(**e) for e in result["entities"]],
        relationships=[GraphRelationship(**r) for r in result["relationships"]],
        context_preview=result["context_preview"],
        latency=LightRAGLatency(
            context_retrieval_ms=result["context_retrieval_ms"],
            generation_ms=result["generation_ms"],
            total_ms=result["total_ms"],
        ),
        sub_questions=result.get("sub_questions", [question]),
    )


@router.post("/compare", response_model=CompareResponse)
async def compare(request: CompareRequest):
    """
    Fires the same question at Simple RAG and LightRAG concurrently and
    returns both results (or per-side error messages) so the frontend can
    render them side by side regardless of whether one side fails.
    """
    simple_result, simple_error = None, None
    lightrag_result, lightrag_error = None, None

    results = await asyncio.gather(
        _run_simple_rag(request.question),
        _run_lightrag(request.question, request.lightrag_mode),
        return_exceptions=True,
    )

    simple_outcome, lightrag_outcome = results

    if isinstance(simple_outcome, Exception):
        logger.warning("Simple RAG side of comparison failed: %s", simple_outcome)
        simple_error = str(simple_outcome)
    else:
        simple_result = simple_outcome

    if isinstance(lightrag_outcome, Exception):
        logger.warning("LightRAG side of comparison failed: %s", lightrag_outcome)
        lightrag_error = str(lightrag_outcome)
    else:
        lightrag_result = lightrag_outcome

    return CompareResponse(
        question=request.question,
        simple_rag=simple_result,
        simple_rag_error=simple_error,
        lightrag=lightrag_result,
        lightrag_error=lightrag_error,
    )
