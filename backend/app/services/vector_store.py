"""
Thin wrapper around a persistent ChromaDB collection. All Chroma-specific
details (client creation, collection naming, id schemes) live here so the
rest of the app just calls add/query/delete.
"""
from functools import lru_cache

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_client() -> chromadb.ClientAPI:
    logger.info("Initializing ChromaDB persistent client at %s", settings.CHROMA_DIR)
    return chromadb.PersistentClient(
        path=str(settings.CHROMA_DIR),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_collection():
    client = _get_client()
    return client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    collection = get_collection()
    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )


def query(embedding: list[float], top_k: int) -> dict:
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    return collection.query(
        query_embeddings=[embedding],
        n_results=min(top_k, count),
    )


def delete_by_doc_id(doc_id: str) -> None:
    collection = get_collection()
    collection.delete(where={"doc_id": doc_id})


def clear_all() -> None:
    """Drop and recreate the collection."""
    client = _get_client()
    try:
        client.delete_collection(settings.CHROMA_COLLECTION_NAME)
    except Exception:
        pass  # collection may not exist yet
    logger.info("Cleared vector store collection")


def total_chunks() -> int:
    return get_collection().count()


# ---------------------------------------------------------------------------
# Summary collection — parallel store that holds pre-generated summaries.
# Keys mirror the main collection: chunk-level entries use the same
# "{doc_id}::{chunk_index}" ids; the document-level entry uses "{doc_id}::doc".
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_summary_client() -> chromadb.ClientAPI:
    # Reuse the same persistent client — lru_cache on _get_client already
    # returns a singleton, so calling it again is free.
    return _get_client()


def get_summary_collection():
    client = _get_summary_client()
    return client.get_or_create_collection(
        name=settings.SUMMARY_COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def add_summaries(
    ids: list[str],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    """
    Store pre-generated summary texts.  No embeddings are stored here —
    the collection is used purely for key-value lookup by id, not for
    semantic search.  We still satisfy Chroma's requirement for content by
    passing the summary text as the document.
    """
    collection = get_summary_collection()
    collection.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
    )


def get_summaries_by_ids(ids: list[str]) -> dict[str, str]:
    """
    Fetch summaries for a list of chunk/doc ids.
    Returns a mapping {id -> summary_text}.  Missing ids are silently omitted.
    """
    if not ids:
        return {}
    collection = get_summary_collection()
    try:
        result = collection.get(ids=ids, include=["documents"])
    except Exception:
        logger.warning("Summary lookup failed for ids: %s", ids)
        return {}
    return {
        rid: rdoc
        for rid, rdoc in zip(result["ids"], result["documents"])
        if rdoc
    }


def get_document_summary(doc_id: str) -> str | None:
    """Convenience wrapper — returns the document-level summary or None."""
    mapping = get_summaries_by_ids([f"{doc_id}::doc"])
    return mapping.get(f"{doc_id}::doc")


def delete_summaries_by_doc_id(doc_id: str) -> None:
    """Remove all chunk summaries and the document summary for *doc_id*."""
    collection = get_summary_collection()
    try:
        collection.delete(where={"doc_id": doc_id})
    except Exception:
        logger.warning("Could not delete summaries for doc_id %s", doc_id)


def clear_summaries() -> None:
    """Drop and recreate the summary collection."""
    client = _get_client()
    try:
        client.delete_collection(settings.SUMMARY_COLLECTION_NAME)
    except Exception:
        pass
    logger.info("Cleared summary collection")
