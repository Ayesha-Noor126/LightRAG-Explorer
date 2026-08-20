"""
Lightweight JSON-file-backed registry of uploaded documents and their
processing status. Not a real database, but enough for a single-instance
research/education app, and easy to swap for Postgres later without
touching the routers (only this module and its callers would change).
"""
import json
import threading
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.models.schemas import DocumentInfo
from app.utils.logger import get_logger

logger = get_logger(__name__)

_REGISTRY_PATH: Path = settings.UPLOAD_DIR.parent / "document_registry.json"
_lock = threading.Lock()


def _load() -> dict:
    if not _REGISTRY_PATH.exists():
        return {}
    with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw


def _save(data: dict) -> None:
    with open(_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def upsert(doc: DocumentInfo) -> None:
    with _lock:
        data = _load()
        data[doc.doc_id] = json.loads(doc.model_dump_json())
        _save(data)


def get(doc_id: str) -> DocumentInfo | None:
    data = _load()
    raw = data.get(doc_id)
    return DocumentInfo(**raw) if raw else None


def list_all() -> list[DocumentInfo]:
    data = _load()
    docs = [DocumentInfo(**v) for v in data.values()]
    return sorted(docs, key=lambda d: d.uploaded_at)


def delete(doc_id: str) -> None:
    with _lock:
        data = _load()
        data.pop(doc_id, None)
        _save(data)


def clear() -> None:
    with _lock:
        _save({})


def latest_upload_time() -> datetime | None:
    docs = list_all()
    if not docs:
        return None
    return max(d.uploaded_at for d in docs)
