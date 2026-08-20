"""
Pydantic schemas shared across routers/services.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    file_type: str
    size_bytes: int
    num_chunks: int
    uploaded_at: datetime
    status: str = Field(description="Simple RAG status: processing, indexed, failed")
    error_message: Optional[str] = None
    # --- Phase 2: dual indexing into LightRAG/Neo4j ---
    graphrag_status: str = Field(
        default="not_started",
        description="LightRAG indexing status: not_started, processing, indexed, failed",
    )
    graphrag_error_message: Optional[str] = None


class UploadResponse(BaseModel):
    documents: list[DocumentInfo]
    message: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
    total_documents: int
    total_chunks: int


class DeleteResponse(BaseModel):
    doc_id: str
    message: str


class RetrievedChunk(BaseModel):
    chunk_id: str
    doc_id: str
    filename: str
    text: str
    similarity_score: float
    chunk_index: int
    # Pre-generated summary produced at ingest time for fast lookup.
    # None when the document was indexed before summarization was introduced.
    summary: Optional[str] = None


class DocumentSummary(BaseModel):
    """Document-level summary produced at ingest time."""
    doc_id: str
    filename: str
    summary: str


class LatencyBreakdown(BaseModel):
    embedding_ms: float
    retrieval_ms: float
    llm_ms: float
    total_ms: float


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: Optional[int] = None


class QueryResponse(BaseModel):
    question: str
    answer: str
    retrieved_chunks: list[RetrievedChunk]
    latency: LatencyBreakdown
    model: str
    # Document-level summaries for every unique document that contributed a
    # retrieved chunk.  Keyed list so the UI can render a per-doc overview.
    document_summaries: list[DocumentSummary] = []


class RebuildResponse(BaseModel):
    message: str
    total_documents: int
    total_chunks: int
    rebuild_time_ms: float


class MetricsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    avg_chunk_size_chars: float
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    last_indexed_at: Optional[datetime] = None
    # --- Phase 2: knowledge graph metrics (None if Neo4j is unreachable) ---
    total_entities: Optional[int] = None
    total_relationships: Optional[int] = None
    graph_density: Optional[float] = None
    documents_indexed_in_graph: int = 0


# ============================================================
# Phase 2: LightRAG / Graph RAG schemas
# ============================================================


class GraphEntity(BaseModel):
    name: str
    entity_type: Optional[str] = None
    description: Optional[str] = None


class GraphRelationship(BaseModel):
    source: str
    target: str
    description: Optional[str] = None
    weight: Optional[float] = None


class LightRAGQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    mode: str = Field(
        default="hybrid",
        description="LightRAG retrieval mode: naive, local, global, hybrid, mix",
    )
    decompose: bool = Field(
        default=False,
        description="When True, the question is decomposed into 2-4 sub-questions via LLM, "
        "each queried against LightRAG in parallel, then results are merged.",
    )


class LightRAGLatency(BaseModel):
    context_retrieval_ms: float
    generation_ms: float
    total_ms: float


class LightRAGQueryResponse(BaseModel):
    question: str
    mode: str
    answer: str
    entities: list[GraphEntity]
    relationships: list[GraphRelationship]
    context_preview: str = Field(
        description="Raw context block LightRAG assembled for the LLM, "
        "truncated for display."
    )
    latency: LightRAGLatency
    sub_questions: list[str] = Field(
        default=[],
        description="The sub-questions derived from the original question (one element "
        "when decompose=False or decomposition was skipped).",
    )


class GraphNode(BaseModel):
    id: str
    label: str
    entity_type: Optional[str] = None
    description: Optional[str] = None
    source_id: Optional[str] = None
    degree: int = 0


class GraphEdge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[float] = None


class GraphDataResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool = Field(
        description="True if the full graph exceeds GRAPH_VIEW_NODE_LIMIT "
        "and this response was capped."
    )


class GraphStatsResponse(BaseModel):
    node_count: int
    edge_count: int
    density: float
    avg_degree: float
    reachable: bool = Field(description="Whether Neo4j could be reached at all")


# ============================================================
# Phase 3: Comparison, Experiment Mode schemas
# ============================================================


class CompareRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    lightrag_mode: str = Field(default="hybrid")


class CompareResponse(BaseModel):
    question: str
    simple_rag: Optional[QueryResponse] = None
    simple_rag_error: Optional[str] = None
    lightrag: Optional[LightRAGQueryResponse] = None
    lightrag_error: Optional[str] = None


class ExperimentSnapshotRequest(BaseModel):
    label: str = Field(
        min_length=1, max_length=200, description="e.g. 'After 5 PDFs'"
    )
    notes: Optional[str] = None


class ExperimentSnapshot(BaseModel):
    run_id: str
    label: str
    notes: Optional[str] = None
    recorded_at: datetime
    total_documents: int
    total_chunks: int
    total_entities: Optional[int] = None
    total_relationships: Optional[int] = None
    graph_density: Optional[float] = None


class ExperimentHistoryResponse(BaseModel):
    snapshots: list[ExperimentSnapshot]
