"""
Wraps the Gemini API call used to turn retrieved context into an answer.
Isolated here so swapping providers later only touches this file.
"""
import time

import google.generativeai as genai

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_CONFIGURED = False


def _ensure_configured() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    if not settings.GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to backend/.env (see .env.example)."
        )
    genai.configure(api_key=settings.GEMINI_API_KEY)
    _CONFIGURED = True


SYSTEM_PROMPT = """You are a precise research assistant answering questions using \
ONLY the provided context excerpts from uploaded documents. \
If the context does not contain enough information to answer, say so explicitly \
rather than guessing. Cite which excerpt(s) you used when relevant. Be concise."""

_CHUNK_SUMMARY_PROMPT = """\
You are a precise summarization assistant. Your task is to write a single, \
dense paragraph (3-5 sentences) that captures the key facts, concepts, and \
conclusions found in the excerpt below. \
Do NOT add information that is not in the excerpt. \
Do NOT include any preamble like "This excerpt discusses…" — start directly \
with the substance."""

_DOC_SUMMARY_PROMPT = """\
You are a precise summarization assistant. Your task is to write a concise \
overview (up to 8 sentences) of the document text below, covering: \
(1) the main topic, (2) key arguments or findings, and (3) the scope or \
conclusion. Do NOT add information that is not in the text. \
Do NOT include any preamble — start directly with the substance."""


def generate_summary(chunk_text: str) -> tuple[str, float]:
    """
    Generates a dense 3-5 sentence summary of a single chunk of text.
    Returns (summary_text, elapsed_ms).
    Used at ingest time so each chunk has a pre-built summary for fast lookup.
    """
    _ensure_configured()

    prompt = (
        f"{_CHUNK_SUMMARY_PROMPT}\n\n"
        f"EXCERPT:\n{chunk_text}\n\n"
        f"SUMMARY:"
    )

    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    start = time.perf_counter()
    try:
        response = model.generate_content(prompt)
        summary = (response.text or "").strip()
    except Exception:
        logger.exception("Gemini chunk summarization failed")
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000

    if not summary:
        summary = "(Summary unavailable)"

    return summary, elapsed_ms


def generate_document_summary(document_text: str) -> tuple[str, float]:
    """
    Generates a concise document-level summary (up to 8 sentences).
    Returns (summary_text, elapsed_ms).
    Used at ingest time so the whole document has a top-level overview.
    """
    _ensure_configured()

    prompt = (
        f"{_DOC_SUMMARY_PROMPT}\n\n"
        f"DOCUMENT:\n{document_text}\n\n"
        f"OVERVIEW:"
    )

    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    start = time.perf_counter()
    try:
        response = model.generate_content(prompt)
        summary = (response.text or "").strip()
    except Exception:
        logger.exception("Gemini document summarization failed")
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000

    if not summary:
        summary = "(Summary unavailable)"

    return summary, elapsed_ms


def generate_answer(question: str, context_chunks: list[str]) -> tuple[str, float]:
    """Returns (answer_text, elapsed_ms)."""
    _ensure_configured()

    context_block = "\n\n".join(
        f"[Excerpt {i + 1}]\n{chunk}" for i, chunk in enumerate(context_chunks)
    )
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"CONTEXT:\n{context_block}\n\n"
        f"QUESTION: {question}\n\n"
        f"ANSWER:"
    )

    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    start = time.perf_counter()
    try:
        response = model.generate_content(prompt)
        answer = (response.text or "").strip()
    except Exception:
        logger.exception("Gemini generation failed")
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000

    if not answer:
        answer = "The model did not return a usable answer for this query."

    return answer, elapsed_ms
