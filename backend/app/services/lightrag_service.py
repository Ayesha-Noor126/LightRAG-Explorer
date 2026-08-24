"""
Client for the official LightRAG server Docker image (ghcr.io/hkuds/lightrag).
We deliberately do NOT reimplement entity extraction, relationship
extraction, or graph construction — all of that happens inside the
LightRAG container. This module only talks to its HTTP API.

LightRAG server API surface used here (as of the widely-deployed
"LightRAG Server" REST API):
  POST /documents/text     -> insert raw text for indexing
  POST /query               -> ask a question, get a generated answer
  GET  /health               -> liveness check

To get retrieval-explanation data (which entities/relationships were used),
we call /query twice: once with only_need_context=True to get the raw
context block LightRAG assembled (this is what actually gets sent to the
LLM), and once normally to get the generated answer.

LightRAG formats the context block in one of two formats depending on
server version:

  NEW (pipe-delimited tuples — most common in current Docker images):
    [Entities]
    ("entity"<|>ENTITY_NAME<|>TYPE<|>description<|>rank)
    ...
    [Relationships]
    ("relationship"<|>SOURCE<|>TARGET<|>description<|>keywords<|>weight<|>rank)
    ...
    [Sources]
    chunk text…

  OLD (CSV-style — older builds):
    -----Entities-----
    id,entity,type,description
    0,"Neo4j","Technology","A graph database..."
    -----Relationships-----
    id,source,target,description,weight
    0,"Neo4j","LangChain","Neo4j is used by...",0.8

_parse_context() handles both formats gracefully and falls back to empty
lists if neither matches (different LightRAG version).

If decompose=True, query() first asks the LLM to split the user question
into 2-4 focused sub-questions, runs each through LightRAG in parallel,
then merges the results into one unified answer.
"""
import asyncio
import csv
import io
import re
import time
import uuid

import httpx

from app.config import settings
from app.services import tracing_service as tracer
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LightRAGUnavailableError(Exception):
    pass


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if settings.LIGHTRAG_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LIGHTRAG_API_KEY}"
    return headers


async def health_check() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{settings.LIGHTRAG_API_URL}/health", headers=_headers()
            )
            return resp.status_code == 200
    except Exception:
        return False


async def insert_document(text: str, filename: str) -> None:
    """
    Sends raw extracted text to LightRAG for indexing. LightRAG handles
    chunking, entity extraction, relationship extraction, and graph
    construction internally and asynchronously — this call only enqueues
    the document; it does not wait for graph construction to finish.
    """
    payload = {"text": text, "file_source": filename}
    async with httpx.AsyncClient(timeout=settings.LIGHTRAG_REQUEST_TIMEOUT_S) as client:
        resp = await client.post(
            f"{settings.LIGHTRAG_API_URL}/documents/text",
            json=payload,
            headers=_headers(),
        )
        if resp.status_code >= 400:
            raise LightRAGUnavailableError(
                f"LightRAG rejected document '{filename}': "
                f"{resp.status_code} {resp.text[:300]}"
            )


# ---------------------------------------------------------------------------
# Context parsing — supports both new pipe-tuple format and old CSV format
# ---------------------------------------------------------------------------

def _parse_pipe_entities(block: str) -> list[dict]:
    """
    Parse the new LightRAG pipe-delimited entity tuple format:
        ("entity"<|>NAME<|>TYPE<|>DESCRIPTION<|>RANK)
    """
    entities: list[dict] = []
    # Match tuples that start with "entity" as the first field
    pattern = re.compile(
        r'\(\s*["\']?entity["\']?\s*<\|>\s*([^<]+?)\s*<\|>\s*([^<]*?)\s*<\|>\s*([^<]*?)\s*(?:<\|>[^)]*?)?\)',
        re.IGNORECASE,
    )
    for m in pattern.finditer(block):
        name = m.group(1).strip().strip('"\'')
        etype = m.group(2).strip().strip('"\'') or None
        desc = m.group(3).strip().strip('"\'') or None
        if name:
            entities.append({"name": name, "entity_type": etype, "description": desc})
    return entities


def _parse_pipe_relationships(block: str) -> list[dict]:
    """
    Parse the new LightRAG pipe-delimited relationship tuple format:
        ("relationship"<|>SOURCE<|>TARGET<|>DESCRIPTION<|>KEYWORDS<|>WEIGHT<|>RANK)
    """
    relationships: list[dict] = []
    pattern = re.compile(
        r'\(\s*["\']?relationship["\']?\s*<\|>\s*([^<]+?)\s*<\|>\s*([^<]+?)\s*<\|>\s*([^<]*?)\s*(?:<\|>([^<]*?))?\s*(?:<\|>([^<)]*?))?\s*(?:<\|>[^)]*?)?\)',
        re.IGNORECASE,
    )
    for m in pattern.finditer(block):
        source = m.group(1).strip().strip('"\'')
        target = m.group(2).strip().strip('"\'')
        desc = (m.group(3) or "").strip().strip('"\'') or None
        weight_raw = (m.group(5) or "").strip().strip('"\'')
        try:
            weight = float(weight_raw) if weight_raw else None
        except ValueError:
            weight = None
        if source and target:
            relationships.append(
                {
                    "source": source,
                    "target": target,
                    "description": desc,
                    "weight": weight,
                }
            )
    return relationships


def _extract_bracket_section(context: str, section_name: str) -> str:
    """
    Extracts content of a bracket-style section like:
        [Entities]
        ...content...
        [NextSection]   ← or end of string
    """
    pattern = re.compile(
        rf"\[{re.escape(section_name)}\]\s*\n(.*?)(?=\n\[|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(context)
    return m.group(1).strip() if m else ""


def _extract_dash_section(context: str, header_pattern: str) -> str:
    """
    Extracts content of a dash-style CSV section like:
        -----Entities-----
        id,entity,type,description
        ...
        -----Relationships-----  ← or end of string
    """
    m = re.search(
        rf"{header_pattern}\s*\n(.*?)(?=\n-----|$)",
        context,
        re.DOTALL | re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def _parse_context(context: str) -> tuple[list[dict], list[dict]]:
    """
    Tries to extract entity and relationship tables from the raw context
    block that LightRAG returns via only_need_context=True.

    Supported formats (tried in order):
      1. New bracket + pipe-tuple format:
           [Entities] / [Relationships] / [Relations] / [Edges]
      2. Old dash + CSV format:
           -----Entities----- / -----Relationships-----

    Returns (entities, relationships). Both are empty lists on any parse
    failure so the caller always gets a clean result.
    """
    entities: list[dict] = []
    relationships: list[dict] = []

    if not context:
        return entities, relationships

    # ---- Try new bracket / pipe-tuple format first ----
    entity_block = _extract_bracket_section(context, "Entities")

    # Relationship section may be named [Relationships], [Relations], or [Edges]
    rel_block = (
        _extract_bracket_section(context, "Relationships")
        or _extract_bracket_section(context, "Relations")
        or _extract_bracket_section(context, "Edges")
    )

    if entity_block:
        try:
            entities = _parse_pipe_entities(entity_block)
        except Exception:
            logger.debug("Could not parse pipe-tuple entity block from LightRAG context")

    if rel_block:
        try:
            relationships = _parse_pipe_relationships(rel_block)
        except Exception:
            logger.debug("Could not parse pipe-tuple relationship block from LightRAG context")

    # ---- Fall back to old dash/CSV format if bracket format found nothing ----
    if not entities and not relationships:
        dash_entity_block = _extract_dash_section(context, r"-----\s*Entities\s*-----")
        dash_rel_block = _extract_dash_section(context, r"-----\s*Relationships\s*-----")

        if dash_entity_block:
            try:
                reader = csv.DictReader(io.StringIO(dash_entity_block))
                for row in reader:
                    name = row.get("entity") or row.get("name")
                    if name:
                        entities.append(
                            {
                                "name": name.strip('"'),
                                "entity_type": (row.get("type") or "").strip('"') or None,
                                "description": (row.get("description") or "").strip('"') or None,
                            }
                        )
            except Exception:
                logger.debug("Could not parse CSV entity table from LightRAG context")

        if dash_rel_block:
            try:
                reader = csv.DictReader(io.StringIO(dash_rel_block))
                for row in reader:
                    source = row.get("source")
                    target = row.get("target")
                    if source and target:
                        weight_raw = row.get("weight")
                        try:
                            weight = float(weight_raw) if weight_raw else None
                        except ValueError:
                            weight = None
                        relationships.append(
                            {
                                "source": source.strip('"'),
                                "target": target.strip('"'),
                                "description": (row.get("description") or "").strip('"') or None,
                                "weight": weight,
                            }
                        )
            except Exception:
                logger.debug("Could not parse CSV relationship table from LightRAG context")

    return entities, relationships


# ---------------------------------------------------------------------------
# Query decomposition — break a complex question into sub-questions via LLM
# ---------------------------------------------------------------------------

def _decompose_question(question: str) -> list[str]:
    """
    Uses the Gemini LLM to break a complex question into 2-4 focused
    sub-questions that each target a distinct aspect of the original query.
    Returns the original question as a single-element list if decomposition
    fails or produces only one question.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — skipping query decomposition")
        return [question]

    try:
        import google.generativeai as genai  # noqa: PLC0415

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)

        prompt = (
            "You are a query decomposition assistant for a knowledge graph retrieval system.\n\n"
            "Break the following user question into 2 to 4 focused sub-questions that together "
            "cover all aspects of the original question. Each sub-question should be:\n"
            "- Self-contained and independently answerable\n"
            "- Targeting a specific entity, relationship, or concept\n"
            "- Directly relevant to the original question\n\n"
            "Return ONLY the sub-questions, one per line, with no numbering, bullets, "
            "or extra commentary.\n\n"
            f"Original question: {question}"
        )

        response = model.generate_content(prompt)
        raw = response.text.strip()

        sub_questions = [
            line.strip().lstrip("•-123456789.) \t")
            for line in raw.splitlines()
            if line.strip() and len(line.strip()) > 10
        ]

        # Filter out lines that look like headers/commentary
        sub_questions = [q for q in sub_questions if q.endswith("?") or len(q) > 20]

        if len(sub_questions) >= 2:
            logger.info(
                "Decomposed query into %d sub-questions: %s",
                len(sub_questions),
                sub_questions,
            )
            return sub_questions

    except Exception as exc:
        logger.warning("Query decomposition failed (%s) — using original question", exc)

    return [question]


def _merge_results(results: list[dict], sub_questions: list[str], original_question: str) -> dict:
    """
    Merges multiple per-sub-question query results into a single unified response.
    Deduplicates entities and relationships, picks the longest context preview,
    and synthesizes a combined answer using the LLM.
    """
    # Aggregate timing
    total_ctx_ms = sum(r.get("context_retrieval_ms", 0) for r in results)
    total_gen_ms = sum(r.get("generation_ms", 0) for r in results)
    total_ms = sum(r.get("total_ms", 0) for r in results)

    # Deduplicate entities by name (case-insensitive)
    seen_entity_names: set[str] = set()
    merged_entities: list[dict] = []
    for r in results:
        for e in r.get("entities", []):
            key = e["name"].lower()
            if key not in seen_entity_names:
                seen_entity_names.add(key)
                merged_entities.append(e)

    # Deduplicate relationships by (source, target) pair
    seen_rel_pairs: set[tuple] = set()
    merged_relationships: list[dict] = []
    for r in results:
        for rel in r.get("relationships", []):
            pair = (rel["source"].lower(), rel["target"].lower())
            if pair not in seen_rel_pairs:
                seen_rel_pairs.add(pair)
                merged_relationships.append(rel)

    # Collect all partial answers
    partial_answers = []
    for sq, r in zip(sub_questions, results):
        ans = r.get("answer", "").strip()
        if ans and ans != "LightRAG did not return a usable answer for this query.":
            partial_answers.append(f"Sub-question: {sq}\nAnswer: {ans}")

    # Longest context preview for debugging
    context_preview = max(
        (r.get("context_preview", "") for r in results),
        key=len,
        default="(No context returned by LightRAG.)",
    )

    # Synthesize final answer from partial answers using LLM
    final_answer = ""
    if partial_answers and settings.GEMINI_API_KEY:
        try:
            import google.generativeai as genai  # noqa: PLC0415

            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
            joined = "\n\n---\n\n".join(partial_answers)
            synthesis_prompt = (
                f"You have retrieved answers to several sub-questions derived from this "
                f"original question:\n\n\"{original_question}\"\n\n"
                f"Sub-question answers:\n{joined}\n\n"
                "Write a single, coherent, comprehensive answer to the original question "
                "by synthesizing the information above. Do not repeat the sub-questions. "
                "Be concise and factual."
            )
            resp = model.generate_content(synthesis_prompt)
            final_answer = resp.text.strip()
        except Exception as exc:
            logger.warning("Answer synthesis failed (%s) — concatenating partial answers", exc)

    if not final_answer:
        # Fallback: concatenate partial answers
        final_answer = "\n\n".join(
            f"[{sq}]\n{r.get('answer', '')}"
            for sq, r in zip(sub_questions, results)
            if r.get("answer")
        )

    if not final_answer:
        final_answer = "LightRAG did not return a usable answer for this query."

    return {
        "answer": final_answer,
        "entities": merged_entities,
        "relationships": merged_relationships,
        "context_preview": context_preview or "(No context returned by LightRAG.)",
        "context_retrieval_ms": round(total_ctx_ms, 2),
        "generation_ms": round(total_gen_ms, 2),
        "total_ms": round(total_ms, 2),
        "sub_questions": sub_questions,
    }


# ---------------------------------------------------------------------------
# Core query — single question
# ---------------------------------------------------------------------------

async def query(question: str, mode: str = "hybrid", decompose: bool = False) -> dict:
    """
    Returns a dict with: answer, entities, relationships, context_preview,
    context_retrieval_ms, generation_ms, total_ms, sub_questions.

    When decompose=True, first decomposes the question into 2-4 sub-questions
    via the LLM, runs each in parallel through LightRAG, then merges results.

    Every call is traced in Langfuse:
      trace  "lightrag-query"
        ├── span  "context-retrieval"   (only_need_context=True call)
        └── span  "answer-generation"   (normal query call)
    """
    mode = mode if mode in ("naive", "local", "global", "hybrid", "mix") else "hybrid"

    # --- Query decomposition ---
    if decompose:
        sub_questions = _decompose_question(question)
        if len(sub_questions) > 1:
            # Run all sub-questions in parallel (each calls _single_query)
            tasks = [_single_query(sq, mode) for sq in sub_questions]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out failed results, keep successful ones
            good_results = []
            good_questions = []
            for sq, result in zip(sub_questions, results):
                if isinstance(result, Exception):
                    logger.warning("Sub-query failed for '%s': %s", sq, result)
                else:
                    good_results.append(result)
                    good_questions.append(sq)

            if good_results:
                return _merge_results(good_results, good_questions, question)
            # Fall through to single query if all sub-queries failed

    # --- Single question (no decomposition or fallback) ---
    result = await _single_query(question, mode)
    result["sub_questions"] = [question]
    return result


async def _single_query(question: str, mode: str) -> dict:
    """
    Runs one question through LightRAG: context retrieval + answer generation.
    Returns dict with answer, entities, relationships, context_preview, latencies.
    """
    t_start = time.perf_counter()
    session_id = str(uuid.uuid4())
    trace = tracer.start_lightrag_trace(question=question, mode=mode, session_id=session_id)

    async with httpx.AsyncClient(timeout=settings.LIGHTRAG_REQUEST_TIMEOUT_S) as client:
        # ------------------------------------------------------------------
        # 1. Context-retrieval call  (only_need_context=True)
        # ------------------------------------------------------------------
        ctx_span = tracer.start_span(
            trace,
            name="context-retrieval",
            input_data={"question": question, "mode": mode, "only_need_context": True},
            metadata={"lightrag_url": settings.LIGHTRAG_API_URL, "mode": mode},
        )

        t_ctx_start = time.perf_counter()
        entities: list[dict] = []
        relationships: list[dict] = []
        context_preview = ""
        sub_query_count = 0

        try:
            ctx_resp = await client.post(
                f"{settings.LIGHTRAG_API_URL}/query",
                json={"query": question, "mode": mode, "only_need_context": True},
                headers=_headers(),
            )
            if ctx_resp.status_code == 200:
                raw_json = ctx_resp.json()
                # --- DIAGNOSTIC: log exactly what LightRAG returned ---
                logger.info(
                    "[DIAG] LightRAG context response keys: %s",
                    list(raw_json.keys()),
                )
                context = raw_json.get("response", "") or ""
                logger.info(
                    "[DIAG] Raw context first 400 chars (mode=%s): %r",
                    mode,
                    context[:400],
                )
                # -----------------------------------------------------
                entities_raw, rels_raw = _parse_context(context)
                entities = entities_raw
                relationships = rels_raw
                context_preview = context[:4000]
                sub_query_count = tracer._count_sub_queries(context, mode)
                logger.info(
                    "Context retrieved: %d entities, %d relationships, ~%d sub-queries",
                    len(entities),
                    len(relationships),
                    sub_query_count,
                )
            else:
                logger.warning(
                    "LightRAG context-only call returned %d: %s",
                    ctx_resp.status_code,
                    ctx_resp.text[:200],
                )
        except Exception as exc:
            logger.warning("LightRAG context-only call failed (%s); continuing without it", exc)

        context_ms = (time.perf_counter() - t_ctx_start) * 1000

        tracer.end_span(
            ctx_span,
            output={
                "entities_found": len(entities),
                "relationships_found": len(relationships),
                # Expanded to 2000 chars so the context format is visible in Langfuse
                "context_preview": context_preview[:2000],
                "sub_query_count": sub_query_count,
            },
            metadata={
                "sub_query_count": sub_query_count,
                "context_retrieval_ms": round(context_ms, 2),
                "mode": mode,
            },
        )

        # ------------------------------------------------------------------
        # 2. Answer-generation call
        # ------------------------------------------------------------------
        gen_span = tracer.start_span(
            trace,
            name="answer-generation",
            input_data={"question": question, "mode": mode},
            metadata={"lightrag_url": settings.LIGHTRAG_API_URL, "mode": mode},
        )

        t_gen_start = time.perf_counter()
        resp = await client.post(
            f"{settings.LIGHTRAG_API_URL}/query",
            json={"query": question, "mode": mode},
            headers=_headers(),
        )
        if resp.status_code >= 400:
            tracer.end_span(gen_span, output={"error": resp.text[:300]})
            tracer.finish_trace(trace, output={"error": resp.text[:300]})
            raise LightRAGUnavailableError(
                f"LightRAG query failed: {resp.status_code} {resp.text[:300]}"
            )

        answer = (resp.json().get("response", "") or "").strip()
        generation_ms = (time.perf_counter() - t_gen_start) * 1000

        tracer.end_span(
            gen_span,
            output={"answer_preview": answer[:500]},
            metadata={
                "answer_length_chars": len(answer),
                "generation_ms": round(generation_ms, 2),
            },
        )

    total_ms = (time.perf_counter() - t_start) * 1000

    if not answer:
        answer = "LightRAG did not return a usable answer for this query."

    tracer.finish_trace(
        trace,
        output={"answer_preview": answer[:500]},
        metadata={
            "sub_query_count": sub_query_count,
            "entities_found": len(entities),
            "relationships_found": len(relationships),
            "context_retrieval_ms": round(context_ms, 2),
            "generation_ms": round(generation_ms, 2),
            "total_ms": round(total_ms, 2),
            "mode": mode,
        },
    )

    return {
        "answer": answer,
        "entities": entities,
        "relationships": relationships,
        "context_preview": context_preview or "(No context returned by LightRAG.)",
        "context_retrieval_ms": round(context_ms, 2),
        "generation_ms": round(generation_ms, 2),
        "total_ms": round(total_ms, 2),
    }
