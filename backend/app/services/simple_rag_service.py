"""
Orchestrates the full Simple RAG pipeline described in the spec:

    Upload -> Extract -> Chunk -> Embed -> Vector DB -> Retrieve -> LLM -> Answer

Routers call into this module; this module calls the lower-level services
(document_processor, embedding_service, vector_store, llm_service,
document_registry). Keeping orchestration in one place makes it easy to
reuse the same shape for a second pipeline (LightRAG) in Phase 2.
"""
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.models.schemas import (
    DocumentInfo,
    DocumentSummary,
    LatencyBreakdown,
    QueryResponse,
    RetrievedChunk,
)
from app.services import document_processor as dp
from app.services import document_registry as registry
from app.services import embedding_service, llm_service, vector_store
from app.utils.logger import get_logger

logger = get_logger(__name__)


class IngestionError(Exception):
    pass


def validate_upload(filename: str, size_bytes: int) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise IngestionError(
            f"'{ext}' is not supported. Allowed types: "
            f"{', '.join(sorted(settings.ALLOWED_EXTENSIONS))}"
        )
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise IngestionError(
            f"File exceeds the {settings.MAX_FILE_SIZE_MB}MB size limit."
        )


def ingest_document(file_path: Path, original_filename: str) -> DocumentInfo:
    """
    Extracts text, chunks it, embeds the chunks, and stores them in Chroma.
    Registers document metadata (including failure state) regardless of
    outcome so the UI can surface what went wrong.
    """
    doc_id = str(uuid.uuid4())
    ext = Path(original_filename).suffix.lower()
    size_bytes = file_path.stat().st_size

    doc_info = DocumentInfo(
        doc_id=doc_id,
        filename=original_filename,
        file_type=ext,
        size_bytes=size_bytes,
        num_chunks=0,
        uploaded_at=datetime.now(timezone.utc),
        status="processing",
    )
    registry.upsert(doc_info)

    try:
        text = dp.extract_text(file_path)
        chunks = dp.chunk_text(text)

        if not chunks:
            raise dp.EmptyDocumentError("No chunks produced from document.")

        chunk_texts = [c.text for c in chunks]
        embeddings, _ = embedding_service.embed_texts(chunk_texts)

        ids = [f"{doc_id}::{c.chunk_index}" for c in chunks]
        metadatas = [
            {
                "doc_id": doc_id,
                "filename": original_filename,
                "chunk_index": c.chunk_index,
            }
            for c in chunks
        ]

        vector_store.add_chunks(
            ids=ids,
            embeddings=embeddings,
            documents=chunk_texts,
            metadatas=metadatas,
        )

        # -----------------------------------------------------------------
        # Summarization — generate a dense summary for every chunk and one
        # document-level overview, then persist them in a parallel Chroma
        # collection for fast lookup at query time.
        # -----------------------------------------------------------------
        logger.info("Generating summaries for %d chunks …", len(chunks))
        summary_ids: list[str] = []
        summary_texts: list[str] = []
        summary_metas: list[dict] = []

        for chunk, chunk_id in zip(chunks, ids):
            truncated = chunk.text[: settings.SUMMARY_CHUNK_MAX_CHARS]
            try:
                chunk_summary, _ = llm_service.generate_summary(truncated)
            except Exception as exc:
                logger.warning("Chunk summary failed for %s: %s", chunk_id, exc)
                chunk_summary = "(Summary unavailable)"
            summary_ids.append(chunk_id)
            summary_texts.append(chunk_summary)
            summary_metas.append(
                {
                    "doc_id": doc_id,
                    "filename": original_filename,
                    "chunk_index": chunk.chunk_index,
                    "summary_type": "chunk",
                }
            )

        # Document-level summary from first SUMMARY_DOC_MAX_CHARS characters.
        doc_text_truncated = text[: settings.SUMMARY_DOC_MAX_CHARS]
        try:
            doc_summary, _ = llm_service.generate_document_summary(doc_text_truncated)
        except Exception as exc:
            logger.warning("Document summary failed for %s: %s", doc_id, exc)
            doc_summary = "(Summary unavailable)"

        summary_ids.append(f"{doc_id}::doc")
        summary_texts.append(doc_summary)
        summary_metas.append(
            {
                "doc_id": doc_id,
                "filename": original_filename,
                "chunk_index": -1,
                "summary_type": "document",
            }
        )

        vector_store.add_summaries(
            ids=summary_ids,
            documents=summary_texts,
            metadatas=summary_metas,
        )
        logger.info("Stored %d chunk summaries + 1 doc summary for %s", len(chunks), original_filename)

        doc_info.num_chunks = len(chunks)
        doc_info.status = "indexed"
        registry.upsert(doc_info)
        logger.info(
            "Indexed document %s (%s) into %d chunks",
            original_filename,
            doc_id,
            len(chunks),
        )

    except Exception as e:
        logger.exception("Failed to ingest document %s", original_filename)
        doc_info.status = "failed"
        doc_info.error_message = str(e)
        registry.upsert(doc_info)

    return doc_info


def delete_document(doc_id: str) -> None:
    vector_store.delete_by_doc_id(doc_id)
    vector_store.delete_summaries_by_doc_id(doc_id)
    registry.delete(doc_id)
    upload_path = settings.UPLOAD_DIR / doc_id
    if upload_path.exists():
        for f in upload_path.iterdir():
            f.unlink()
        upload_path.rmdir()


def clear_all_documents() -> None:
    vector_store.clear_all()
    vector_store.clear_summaries()
    registry.clear()
    for child in settings.UPLOAD_DIR.iterdir():
        if child.is_dir():
            for f in child.iterdir():
                f.unlink()
            child.rmdir()


def rebuild_index() -> tuple[int, int, float]:
    """
    Re-ingests every stored raw file from disk. Useful after changing
    chunking/embedding config. Returns (num_docs, num_chunks, elapsed_ms).
    """
    start = time.perf_counter()
    docs = registry.list_all()
    vector_store.clear_all()
    vector_store.clear_summaries()

    total_chunks = 0
    for doc in docs:
        doc_dir = settings.UPLOAD_DIR / doc.doc_id
        matches = list(doc_dir.glob("*")) if doc_dir.exists() else []
        if not matches:
            logger.warning("Raw file missing for %s during rebuild, skipping", doc.doc_id)
            continue
        raw_file = matches[0]

        try:
            text = dp.extract_text(raw_file)
            chunks = dp.chunk_text(text)
            chunk_texts = [c.text for c in chunks]
            embeddings, _ = embedding_service.embed_texts(chunk_texts)
            ids = [f"{doc.doc_id}::{c.chunk_index}" for c in chunks]
            metadatas = [
                {"doc_id": doc.doc_id, "filename": doc.filename, "chunk_index": c.chunk_index}
                for c in chunks
            ]
            vector_store.add_chunks(ids, embeddings, chunk_texts, metadatas)

            # Re-generate summaries for all chunks + the document.
            logger.info("Generating summaries for %d chunks (rebuild) …", len(chunks))
            summary_ids: list[str] = []
            summary_texts: list[str] = []
            summary_metas: list[dict] = []

            for chunk, chunk_id in zip(chunks, ids):
                truncated = chunk.text[: settings.SUMMARY_CHUNK_MAX_CHARS]
                try:
                    chunk_summary, _ = llm_service.generate_summary(truncated)
                except Exception as exc:
                    logger.warning("Chunk summary failed for %s: %s", chunk_id, exc)
                    chunk_summary = "(Summary unavailable)"
                summary_ids.append(chunk_id)
                summary_texts.append(chunk_summary)
                summary_metas.append(
                    {
                        "doc_id": doc.doc_id,
                        "filename": doc.filename,
                        "chunk_index": chunk.chunk_index,
                        "summary_type": "chunk",
                    }
                )

            raw_text = dp.extract_text(raw_file)
            doc_text_truncated = raw_text[: settings.SUMMARY_DOC_MAX_CHARS]
            try:
                doc_summary, _ = llm_service.generate_document_summary(doc_text_truncated)
            except Exception as exc:
                logger.warning("Document summary failed for %s: %s", doc.doc_id, exc)
                doc_summary = "(Summary unavailable)"

            summary_ids.append(f"{doc.doc_id}::doc")
            summary_texts.append(doc_summary)
            summary_metas.append(
                {
                    "doc_id": doc.doc_id,
                    "filename": doc.filename,
                    "chunk_index": -1,
                    "summary_type": "document",
                }
            )

            vector_store.add_summaries(
                ids=summary_ids,
                documents=summary_texts,
                metadatas=summary_metas,
            )
            doc.num_chunks = len(chunks)
            doc.status = "indexed"
            doc.error_message = None
            total_chunks += len(chunks)
        except Exception as e:
            doc.status = "failed"
            doc.error_message = str(e)
            logger.exception("Rebuild failed for %s", doc.filename)

        registry.upsert(doc)

    elapsed_ms = (time.perf_counter() - start) * 1000
    return len(docs), total_chunks, elapsed_ms


def answer_query(question: str, top_k: int | None = None) -> QueryResponse:
    top_k = top_k or settings.TOP_K
    t_start = time.perf_counter()

    query_embedding, embed_ms = embedding_service.embed_query(question)

    t_retrieve_start = time.perf_counter()
    results = vector_store.query(query_embedding, top_k)
    retrieve_ms = (time.perf_counter() - t_retrieve_start) * 1000

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    # ------------------------------------------------------------------
    # Fetch pre-generated summaries for every retrieved chunk id in one
    # batch call — this is the "fast lookup" step.
    # ------------------------------------------------------------------
    chunk_summary_map = vector_store.get_summaries_by_ids(ids) if ids else {}

    retrieved_chunks: list[RetrievedChunk] = []
    seen_doc_ids: dict[str, str] = {}  # doc_id -> filename

    for chunk_id, doc_text, meta, distance in zip(ids, documents, metadatas, distances):
        # Chroma cosine "distance" -> similarity score in [0, 1] (higher = more similar)
        similarity = max(0.0, 1.0 - distance)
        doc_id = meta.get("doc_id", "")
        filename = meta.get("filename", "unknown")
        if doc_id and doc_id not in seen_doc_ids:
            seen_doc_ids[doc_id] = filename
        retrieved_chunks.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                filename=filename,
                text=doc_text,
                similarity_score=round(similarity, 4),
                chunk_index=meta.get("chunk_index", -1),
                summary=chunk_summary_map.get(chunk_id),
            )
        )

    # ------------------------------------------------------------------
    # Fetch document-level summaries for every unique source document.
    # ------------------------------------------------------------------
    doc_summary_ids = [f"{did}::doc" for did in seen_doc_ids]
    doc_summary_map = vector_store.get_summaries_by_ids(doc_summary_ids) if doc_summary_ids else {}

    document_summaries: list[DocumentSummary] = []
    for doc_id, filename in seen_doc_ids.items():
        raw = doc_summary_map.get(f"{doc_id}::doc")
        if raw:
            document_summaries.append(
                DocumentSummary(doc_id=doc_id, filename=filename, summary=raw)
            )

    if retrieved_chunks:
        answer, llm_ms = llm_service.generate_answer(
            question, [c.text for c in retrieved_chunks]
        )
    else:
        answer = (
            "No documents have been indexed yet, so there is no context to "
            "answer from. Upload at least one document first."
        )
        llm_ms = 0.0

    total_ms = (time.perf_counter() - t_start) * 1000

    return QueryResponse(
        question=question,
        answer=answer,
        retrieved_chunks=retrieved_chunks,
        latency=LatencyBreakdown(
            embedding_ms=round(embed_ms, 2),
            retrieval_ms=round(retrieve_ms, 2),
            llm_ms=round(llm_ms, 2),
            total_ms=round(total_ms, 2),
        ),
        model=settings.GEMINI_MODEL,
        document_summaries=document_summaries,
    )
