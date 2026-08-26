from app.config import settings
from app.models.schemas import MetricsResponse
from app.services import document_registry as registry
from app.services import neo4j_service, vector_store
from fastapi import APIRouter

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("", response_model=MetricsResponse)
async def get_metrics():
    docs = registry.list_all()
    total_chunks = vector_store.total_chunks()

    avg_chunk_size = 0.0
    # Rough estimate: total characters across indexed docs / total chunks.
    # (Exact per-chunk char count isn't stored to keep the registry light;
    # this is a reasonable aggregate proxy.)
    if total_chunks:
        avg_chunk_size = settings.CHUNK_SIZE  # nominal target size

    # --- Phase 2: graph metrics (best-effort; None if Neo4j unreachable) ---
    graph_stats = neo4j_service.get_graph_stats()
    docs_in_graph = len(
        [d for d in docs if d.graphrag_status in ("processing", "indexed")]
    )

    return MetricsResponse(
        total_documents=len(docs),
        total_chunks=total_chunks,
        avg_chunk_size_chars=avg_chunk_size,
        embedding_model=settings.EMBEDDING_MODEL,
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        last_indexed_at=registry.latest_upload_time(),
        total_entities=graph_stats.node_count if graph_stats.reachable else None,
        total_relationships=graph_stats.edge_count if graph_stats.reachable else None,
        graph_density=graph_stats.density if graph_stats.reachable else None,
        documents_indexed_in_graph=docs_in_graph,
    )
