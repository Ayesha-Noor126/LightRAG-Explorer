"""
Phase 2 adds a second indexing target: every uploaded document should be
indexed by BOTH Simple RAG (Chroma) and LightRAG (Neo4j graph). This module
is the single place that fans a document out to both pipelines and merges
their statuses onto one DocumentInfo record, so the router stays simple and
Phase 3's comparison view can trust `status` and `graphrag_status` are both
always populated.

Simple RAG indexing is synchronous and blocking (as in Phase 1). LightRAG
indexing is fire-and-forget from LightRAG's perspective (it processes
asynchronously), so `graphrag_status` starts at "processing" once the
document is successfully handed off, and won't flip to "indexed" here —
Phase 3's analytics/graph tab is where you'd see the graph actually grow.
We still mark it "failed" immediately if LightRAG can't be reached at all,
since that's actionable right away.
"""
from pathlib import Path

from app.models.schemas import DocumentInfo
from app.services import document_processor as dp
from app.services import document_registry as registry
from app.services import lightrag_service
from app.services import simple_rag_service as rag
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def ingest_document_dual(file_path: Path, original_filename: str) -> DocumentInfo:
    # Simple RAG indexing (Phase 1 pipeline) — synchronous, unchanged.
    doc_info = rag.ingest_document(file_path, original_filename)

    # LightRAG indexing (Phase 2) — best-effort, never blocks or fails the upload.
    try:
        text = dp.extract_text(file_path)
        await lightrag_service.insert_document(text, original_filename)
        doc_info.graphrag_status = "processing"
        logger.info("Handed off '%s' to LightRAG for graph indexing", original_filename)
    except lightrag_service.LightRAGUnavailableError as e:
        doc_info.graphrag_status = "failed"
        doc_info.graphrag_error_message = str(e)
        logger.warning("LightRAG indexing failed for '%s': %s", original_filename, e)
    except Exception as e:
        doc_info.graphrag_status = "failed"
        doc_info.graphrag_error_message = (
            f"Could not reach LightRAG server at indexing time: {e}"
        )
        logger.warning(
            "LightRAG unreachable while indexing '%s': %s", original_filename, e
        )

    registry.upsert(doc_info)
    return doc_info
