"""
Handles text extraction from uploaded files and chunking of that text.
Kept independent of the vector store / LLM so it can be reused by other
RAG backends (e.g. LightRAG) later without modification.
"""
from dataclasses import dataclass
from pathlib import Path

import docx
import fitz  # PyMuPDF

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class UnsupportedFileTypeError(Exception):
    pass


class EmptyDocumentError(Exception):
    pass


@dataclass
class Chunk:
    text: str
    chunk_index: int


def extract_text(file_path: Path) -> str:
    """Dispatch to the correct extractor based on file extension."""
    ext = file_path.suffix.lower()

    if ext == ".pdf":
        return _extract_pdf(file_path)
    elif ext == ".docx":
        return _extract_docx(file_path)
    elif ext in (".txt", ".md"):
        return _extract_plain_text(file_path)
    else:
        raise UnsupportedFileTypeError(f"Unsupported file type: {ext}")


def _extract_pdf(file_path: Path) -> str:
    text_parts = []
    with fitz.open(file_path) as pdf:
        for page in pdf:
            text_parts.append(page.get_text())
    return "\n".join(text_parts).strip()


def _extract_docx(file_path: Path) -> str:
    document = docx.Document(str(file_path))
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    return "\n".join(paragraphs).strip()


def _extract_plain_text(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8", errors="ignore").strip()


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[Chunk]:
    """
    Simple sliding-window character chunker with overlap. Splits on the
    nearest sentence/paragraph boundary within the window when possible to
    avoid cutting sentences in half.
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    if not text or not text.strip():
        raise EmptyDocumentError("Document contains no extractable text.")

    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks: list[Chunk] = []
    start = 0
    text_len = len(text)
    chunk_index = 0

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Try to break on a paragraph or sentence boundary near `end`.
        if end < text_len:
            window = text[start:end]
            boundary = max(window.rfind("\n\n"), window.rfind(". "))
            if boundary > chunk_size * 0.5:  # only use it if reasonably far in
                end = start + boundary + 1

        chunk_str = text[start:end].strip()
        if chunk_str:
            chunks.append(Chunk(text=chunk_str, chunk_index=chunk_index))
            chunk_index += 1

        if end >= text_len:
            break

        start = end - chunk_overlap

    logger.info("Chunked document into %d chunks", len(chunks))
    return chunks
