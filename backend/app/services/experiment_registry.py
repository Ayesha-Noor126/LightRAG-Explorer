"""
JSON-file-backed store of "experiment snapshots" — a point-in-time record
of dataset size + graph size + query performance that the user explicitly
saves while running the Experiment Mode flows described in the spec
(upload 1 / 5 / 20 / 100 PDFs and observe graph growth). Same lightweight
pattern as document_registry.py.
"""
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.models.schemas import ExperimentSnapshot

_REGISTRY_PATH: Path = settings.UPLOAD_DIR.parent / "experiment_history.json"
_lock = threading.Lock()


def _load() -> list[dict]:
    if not _REGISTRY_PATH.exists():
        return []
    with open(_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: list[dict]) -> None:
    with open(_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def record(
    label: str,
    notes: str | None,
    total_documents: int,
    total_chunks: int,
    total_entities: int | None,
    total_relationships: int | None,
    graph_density: float | None,
) -> ExperimentSnapshot:
    snapshot = ExperimentSnapshot(
        run_id=str(uuid.uuid4()),
        label=label,
        notes=notes,
        recorded_at=datetime.now(timezone.utc),
        total_documents=total_documents,
        total_chunks=total_chunks,
        total_entities=total_entities,
        total_relationships=total_relationships,
        graph_density=graph_density,
    )
    with _lock:
        data = _load()
        data.append(json.loads(snapshot.model_dump_json()))
        _save(data)
    return snapshot


def list_all() -> list[ExperimentSnapshot]:
    data = _load()
    snapshots = [ExperimentSnapshot(**d) for d in data]
    return sorted(snapshots, key=lambda s: s.recorded_at)


def clear() -> None:
    with _lock:
        _save([])
