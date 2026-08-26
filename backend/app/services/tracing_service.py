"""
Thin wrapper around the Langfuse Python SDK.

All Langfuse interaction lives here so the rest of the app never imports
the SDK directly.  If credentials are missing or the SDK call fails for any
reason the helpers degrade gracefully — tracing is never allowed to break
the main query pipeline.

Trace structure for a LightRAG query
─────────────────────────────────────
trace  "lightrag-query"
  ├── span  "context-retrieval"      # POST /query  only_need_context=True
  │         input:  {question, mode}
  │         output: {entities_found, relationships_found, context_preview}
  │         metadata: {sub_query_count, mode}
  │
  └── span  "answer-generation"      # POST /query  (normal)
            input:  {question, mode}
            output: {answer_preview}
            metadata: {answer_length_chars}
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Client singleton
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_client():
    """
    Returns a Langfuse client or None when credentials are absent.
    Imported lazily so that missing the package at import time is caught here
    rather than crashing the whole app.
    """
    if not settings.LANGFUSE_SECRET_KEY or not settings.LANGFUSE_PUBLIC_KEY:
        logger.warning(
            "Langfuse credentials not configured — tracing disabled. "
            "Set LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY in backend/.env."
        )
        return None

    try:
        from langfuse import Langfuse  # noqa: PLC0415

        client = Langfuse(
            secret_key=settings.LANGFUSE_SECRET_KEY,
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            host=settings.LANGFUSE_BASE_URL,
        )
        logger.info("Langfuse tracing enabled → %s", settings.LANGFUSE_BASE_URL)
        return client
    except Exception as exc:
        logger.warning("Langfuse client init failed (%s) — tracing disabled.", exc)
        return None


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def is_enabled() -> bool:
    return _get_client() is not None


class _NoOpTrace:
    """Returned when tracing is disabled so callers never need to branch."""

    def span(self, *_, **__):
        return _NoOpSpan()

    def update(self, *_, **__):
        pass

    def flush(self):
        pass


class _NoOpSpan:
    def end(self, *_, **__):
        pass

    def update(self, *_, **__):
        pass


def start_lightrag_trace(
    question: str,
    mode: str,
    session_id: str | None = None,
) -> Any:
    """
    Opens a top-level Langfuse trace for one LightRAG query.
    Returns a trace object (real or no-op).  The caller must call
    trace.flush() after all spans have been ended.
    """
    client = _get_client()
    if client is None:
        return _NoOpTrace()

    try:
        trace = client.trace(
            name="lightrag-query",
            input={"question": question, "mode": mode},
            session_id=session_id,
            tags=["lightrag", mode],
            metadata={"mode": mode},
        )
        return trace
    except Exception as exc:
        logger.debug("Langfuse trace creation failed: %s", exc)
        return _NoOpTrace()


def start_span(
    trace,
    name: str,
    input_data: dict,
    metadata: dict | None = None,
) -> Any:
    """Opens a child span on an existing trace."""
    try:
        return trace.span(
            name=name,
            input=input_data,
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.debug("Langfuse span creation failed: %s", exc)
        return _NoOpSpan()


def end_span(span, output: dict, metadata: dict | None = None) -> None:
    """Closes a span with its output data."""
    try:
        span.end(output=output, metadata=metadata or {})
    except Exception as exc:
        logger.debug("Langfuse span end failed: %s", exc)


def finish_trace(trace, output: dict, metadata: dict | None = None) -> None:
    """
    Attaches final output to the trace and flushes the SDK buffer so the
    event is sent to Langfuse before the HTTP response is returned.
    """
    try:
        trace.update(output=output, metadata=metadata or {})
        client = _get_client()
        if client:
            client.flush()
    except Exception as exc:
        logger.debug("Langfuse trace finish failed: %s", exc)


def _count_sub_queries(context: str, mode: str) -> int:
    """
    Estimates the number of sub-queries LightRAG fired internally by
    counting distinct retrieval blocks in the context string it returns.

    LightRAG's hybrid / mix modes fan out to several internal searches
    (naive keyword, local entity, global community).  The context block it
    assembles has clearly delimited sections we can count.

    Supported header formats:
      NEW (bracket-style):   [Entities]  [Relationships]  [Sources]  [Reports]
      OLD (dash-style):      -----Entities-----  -----Relationships-----

    Each unique section header represents one internal retrieval path.
    We fall back to a mode-based estimate when the context is empty or
    the sections are absent (older LightRAG versions).
    """
    import re  # noqa: PLC0415

    if not context:
        # Mode-based fallback estimate
        return {"naive": 1, "local": 2, "global": 2, "hybrid": 3, "mix": 4}.get(mode, 1)

    # Match bracket-style headers: [Entities], [Relationships], [Sources], [Reports]
    bracket_headers = re.findall(r"^\s*\[([A-Za-z][A-Za-z\s]*)\]\s*$", context, re.MULTILINE)

    # Match dash-style headers: -----Entities-----
    dash_headers = re.findall(r"-----\s*\w[\w\s]*\w\s*-----", context)

    # Combine all unique header names found
    all_headers = {h.strip().lower() for h in bracket_headers} | {
        h.strip().lower() for h in dash_headers
    }

    if all_headers:
        count = max(1, len(all_headers))
        logger.debug("Detected %d retrieval sections: %s", count, all_headers)
        return count

    # No section headers found — fall back to mode-based estimate
    return {"naive": 1, "local": 2, "global": 2, "hybrid": 3, "mix": 4}.get(mode, 1)
