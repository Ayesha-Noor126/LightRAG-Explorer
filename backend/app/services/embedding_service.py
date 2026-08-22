"""
Wraps Sentence Transformers so the rest of the app never touches the
model directly. Model is loaded once (lazily) and reused across requests.
"""
import time
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
    return SentenceTransformer(settings.EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> tuple[list[list[float]], float]:
    """Returns (embeddings, elapsed_ms)."""
    model = _get_model()
    start = time.perf_counter()
    vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return vectors.tolist(), elapsed_ms


def embed_query(query: str) -> tuple[list[float], float]:
    vectors, elapsed_ms = embed_texts([query])
    return vectors[0], elapsed_ms
