from fastapi import APIRouter

from app.models.schemas import (
    ExperimentHistoryResponse,
    ExperimentSnapshot,
    ExperimentSnapshotRequest,
)
from app.services import document_registry as registry
from app.services import experiment_registry
from app.services import neo4j_service, vector_store

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.post("", response_model=ExperimentSnapshot)
async def record_snapshot(request: ExperimentSnapshotRequest):
    """
    Captures the current dataset/graph size as a labeled snapshot (e.g.
    "After 5 PDFs") so Experiment Mode can chart how the graph grows and
    how retrieval/latency changes as the corpus grows, per the spec's
    Experiment 1-4 flows.
    """
    docs = registry.list_all()
    total_chunks = vector_store.total_chunks()
    graph_stats = neo4j_service.get_graph_stats()

    return experiment_registry.record(
        label=request.label,
        notes=request.notes,
        total_documents=len(docs),
        total_chunks=total_chunks,
        total_entities=graph_stats.node_count if graph_stats.reachable else None,
        total_relationships=graph_stats.edge_count if graph_stats.reachable else None,
        graph_density=graph_stats.density if graph_stats.reachable else None,
    )


@router.get("", response_model=ExperimentHistoryResponse)
async def list_snapshots():
    return ExperimentHistoryResponse(snapshots=experiment_registry.list_all())


@router.delete("")
async def clear_snapshots():
    experiment_registry.clear()
    return {"message": "Experiment history cleared."}
