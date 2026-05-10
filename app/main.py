"""FastAPI entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import cve, scans
from app.config import get_settings
from app.schemas.scan import HealthResponse
from app.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info(
        f"Starting scanner v{__version__} env={settings.app_env} "
        f"llm_enabled={settings.llm_enabled}"
    )
    yield
    logger.info("Shutting down scanner")


app = FastAPI(
    title="Multi-Agent Code Security Scanner",
    description=(
        "An AI-powered scanner that analyzes pull requests for security issues "
        "using a team of LangGraph agents and a RAG-backed CVE knowledge base."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    """Liveness probe used by Docker/AWS."""
    settings = get_settings()
    return HealthResponse(version=__version__, llm_enabled=settings.llm_enabled)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": "code-security-scanner",
        "version": __version__,
        "docs": "/docs",
    }


app.include_router(scans.router)
app.include_router(cve.router)
