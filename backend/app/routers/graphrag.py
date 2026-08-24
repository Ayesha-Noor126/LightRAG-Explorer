from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    GraphDataResponse,
    GraphEntity,
    GraphRelationship,
    GraphStatsResponse,
    LightRAGLatency,
    LightRAGQueryRequest,
    LightRAGQueryResponse,
)
from app.services import lightrag_service, neo4j_service
from app.utils.logger import get_logger

router = APIRouter(tags=["graphrag"])
logger = get_logger(__name__)


@router.post("/api/query/lightrag", response_model=LightRAGQueryResponse)
async def query_lightrag(request: LightRAGQueryRequest):
    try:
        result = await lightrag_service.query(
            request.question, request.mode, decompose=request.decompose
        )
    except lightrag_service.LightRAGUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("LightRAG query failed")
        raise HTTPException(
            status_code=502,
            detail="Could not reach the LightRAG server. Is its Docker "
            "container running and LIGHTRAG_API_URL correct?",
        )

    return LightRAGQueryResponse(
        question=request.question,
        mode=request.mode,
        answer=result["answer"],
        entities=[GraphEntity(**e) for e in result["entities"]],
        relationships=[GraphRelationship(**r) for r in result["relationships"]],
        context_preview=result["context_preview"],
        latency=LightRAGLatency(
            context_retrieval_ms=result["context_retrieval_ms"],
            generation_ms=result["generation_ms"],
            total_ms=result["total_ms"],
        ),
        sub_questions=result.get("sub_questions", [request.question]),
    )


@router.get("/api/graph/stats", response_model=GraphStatsResponse)
async def graph_stats():
    return neo4j_service.get_graph_stats()


@router.get("/api/graph/data", response_model=GraphDataResponse)
async def graph_data(limit: int = Query(default=150, ge=1, le=1000)):
    return neo4j_service.get_graph_data(limit)


@router.get("/api/graph/health")
async def graph_health():
    return {
        "neo4j_reachable": neo4j_service.is_reachable(),
        "lightrag_reachable": await lightrag_service.health_check(),
    }
