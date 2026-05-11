"""FastAPI entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import cve, scans
from app.config import get_settings
from app.schemas.scan import HealthResponse
from app.utils.logger import get_logger, setup_logging

_STATIC_DIR = Path(__file__).parent / "static"

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


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    """Serve the landing page."""
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/demo", include_in_schema=False)
@app.get("/demo.html", include_in_schema=False)
def demo() -> FileResponse:
    """Serve the interactive demo."""
    return FileResponse(_STATIC_DIR / "demo.html")


app.include_router(scans.router)
app.include_router(cve.router)

# Mount static assets at root so CSS/JS references in HTML work (e.g. href="styles.css").
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
