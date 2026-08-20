import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.models.schemas import (
    DeleteResponse,
    DocumentListResponse,
    RebuildResponse,
    UploadResponse,
)
from app.services import document_registry as registry
from app.services import ingestion_service
from app.services import simple_rag_service as rag
from app.utils.logger import get_logger

router = APIRouter(prefix="/api/documents", tags=["documents"])
logger = get_logger(__name__)


@router.post("/upload", response_model=UploadResponse)
async def upload_documents(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    results = []
    for upload in files:
        contents = await upload.read()
        try:
            rag.validate_upload(upload.filename, len(contents))
        except rag.IngestionError as e:
            raise HTTPException(status_code=400, detail=str(e))

        doc_dir = settings.UPLOAD_DIR / str(uuid.uuid4())
        doc_dir.mkdir(parents=True, exist_ok=True)
        dest_path = doc_dir / upload.filename
        with open(dest_path, "wb") as f:
            f.write(contents)

        doc_info = await ingestion_service.ingest_document_dual(dest_path, upload.filename)

        # Rename storage dir to the actual doc_id so rebuild() can find it later.
        final_dir = settings.UPLOAD_DIR / doc_info.doc_id
        if doc_dir != final_dir:
            shutil.move(str(doc_dir), str(final_dir))

        results.append(doc_info)

    failed = [d for d in results if d.status == "failed"]
    message = (
        f"Indexed {len(results) - len(failed)}/{len(results)} document(s)."
        + (f" {len(failed)} failed." if failed else "")
    )
    return UploadResponse(documents=results, message=message)


@router.get("", response_model=DocumentListResponse)
async def list_documents():
    docs = registry.list_all()
    total_chunks = sum(d.num_chunks for d in docs)
    return DocumentListResponse(
        documents=docs, total_documents=len(docs), total_chunks=total_chunks
    )


@router.delete("/{doc_id}", response_model=DeleteResponse)
async def delete_document(doc_id: str):
    doc = registry.get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    rag.delete_document(doc_id)
    return DeleteResponse(doc_id=doc_id, message=f"Deleted '{doc.filename}'.")


@router.delete("", response_model=DeleteResponse)
async def clear_documents():
    rag.clear_all_documents()
    return DeleteResponse(doc_id="*", message="All documents cleared.")


@router.post("/rebuild", response_model=RebuildResponse)
async def rebuild_index():
    num_docs, num_chunks, elapsed_ms = rag.rebuild_index()
    return RebuildResponse(
        message="Index rebuilt successfully.",
        total_documents=num_docs,
        total_chunks=num_chunks,
        rebuild_time_ms=round(elapsed_ms, 2),
    )
