"""
Centralized configuration for the LightRAG Explorer backend.
All values are overridable via environment variables (see .env.example).
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "LightRAG Explorer API"
    ENV: str = os.getenv("ENV", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # --- Storage paths ---
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    CHROMA_DIR: Path = BASE_DIR / "data" / "chroma_db"

    # --- Upload limits ---
    MAX_FILE_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx", ".txt", ".md"}

    # --- Chunking ---
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", 1000))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", 150))

    # --- Embeddings ---
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

    # --- Retrieval ---
    TOP_K: int = int(os.getenv("TOP_K", 5))

    # --- LLM (Gemini) ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    # --- Chroma collection ---
    CHROMA_COLLECTION_NAME: str = "simple_rag_documents"
    # Parallel collection that stores pre-generated summaries for fast lookup.
    SUMMARY_COLLECTION_NAME: str = "simple_rag_summaries"

    # --- Summarization ---
    # Maximum characters of a chunk to feed into the summarizer.
    SUMMARY_CHUNK_MAX_CHARS: int = int(os.getenv("SUMMARY_CHUNK_MAX_CHARS", 3000))
    # Maximum characters of the full document text fed to the doc-level summarizer.
    SUMMARY_DOC_MAX_CHARS: int = int(os.getenv("SUMMARY_DOC_MAX_CHARS", 20000))

    # --- LightRAG (Phase 2) ---
    # Base URL of the official LightRAG server Docker container.
    LIGHTRAG_API_URL: str = os.getenv("LIGHTRAG_API_URL", "http://localhost:9621")
    LIGHTRAG_API_KEY: str = os.getenv("LIGHTRAG_API_KEY", "")
    LIGHTRAG_DEFAULT_MODE: str = os.getenv("LIGHTRAG_DEFAULT_MODE", "hybrid")
    LIGHTRAG_REQUEST_TIMEOUT_S: float = float(os.getenv("LIGHTRAG_REQUEST_TIMEOUT_S", 120))

    # --- Neo4j (Phase 2) ---
    # This is the same Neo4j instance LightRAG is configured to use as its
    # graph storage backend (LIGHTRAG_GRAPH_STORAGE=Neo4JStorage). The
    # backend connects to it directly (read-only queries) to power the
    # Graph tab, independent of whatever LightRAG's own API exposes.
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "password123")
    NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "neo4j")
    GRAPH_VIEW_NODE_LIMIT: int = int(os.getenv("GRAPH_VIEW_NODE_LIMIT", 150))

    # --- Langfuse observability ---
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_BASE_URL: str = os.getenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure storage directories exist at import time.
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
