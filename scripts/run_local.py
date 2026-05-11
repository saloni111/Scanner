"""Run the scanner API locally using SQLite (no Postgres or Docker needed).

Usage:
    python scripts/run_local.py

The server starts on http://127.0.0.1:8000.
Interactive docs: http://127.0.0.1:8000/docs

To scan the bundled vulnerable demo file, in another terminal:
    curl -X POST http://127.0.0.1:8000/scans \\
         -H "Content-Type: application/json" \\
         -d @examples/scan_request.json | python3 -m json.tool

Or use the Makefile shortcut (after the server is running):
    make scan-demo

Notes:
- CVE RAG search is skipped in SQLite mode (pgvector needs Postgres).
  Use `docker compose up` for the full experience including CVE lookup.
- Set OPENAI_API_KEY in .env (or export it) to enable the LLM agents.
"""

from __future__ import annotations

import os
import sys

# Must be set before any app imports.
os.environ.setdefault("DATABASE_URL", "sqlite:///scanner.sqlite")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("LOG_LEVEL", "INFO")

# Make sure `app` is importable when running as `python scripts/run_local.py`.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base, engine  # noqa: E402
import app.models  # noqa: E402, F401  -- registers all ORM models with Base

# pgvector's Vector column type can't be created in SQLite; drop it so
# create_all works cleanly.
cve_table = Base.metadata.tables.get("cve_records")
if cve_table is not None:
    Base.metadata.remove(cve_table)

Base.metadata.create_all(engine)
print("DB ready (SQLite). Tables:", list(Base.metadata.tables.keys()))
print("Starting API on http://127.0.0.1:8000 — docs at http://127.0.0.1:8000/docs\n")

import uvicorn  # noqa: E402
from app.main import app  # noqa: E402

uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
