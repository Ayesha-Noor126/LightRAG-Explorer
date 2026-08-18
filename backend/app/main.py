from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import analytics, comparison, documents, experiments, graphrag, query
from app.utils.logger import get_logger

logger = get_logger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "LightRAG Explorer — full 3-phase build: document management, "
        "Simple RAG, Graph RAG via LightRAG + Neo4j, side-by-side "
        "comparison, and experiment tracking."
    ),
    version="1.0.0-phase3",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(query.router)
app.include_router(analytics.router)
app.include_router(graphrag.router)
app.include_router(comparison.router)
app.include_router(experiments.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check server logs for details."},
    )


@app.get("/api/health", tags=["health"])
async def health_check():
    return {"status": "ok", "phase": 3, "app": settings.APP_NAME}


@app.get("/", tags=["health"])
async def root():
    return {
        "message": "LightRAG Explorer API — Phase 1+2+3 (complete)",
        "docs": "/docs",
    }
