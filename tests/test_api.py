"""API smoke tests using FastAPI's TestClient against an in-memory SQLite DB."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Force a sqlite test DB before app imports anything.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_scanner.sqlite")
os.environ.setdefault("OPENAI_API_KEY", "")

from app import database  # noqa: E402
from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _setup_db() -> Iterator[None]:
    # Replace engine/session with sqlite for tests. We can't use the real
    # pgvector column on sqlite, so we drop the CVE table from metadata.
    cve_table = Base.metadata.tables.get("cve_records")
    if cve_table is not None:
        Base.metadata.remove(cve_table)

    engine = create_engine("sqlite:///./test_scanner.sqlite", future=True)
    database.engine = engine
    database.SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_create_and_get_scan(client: TestClient, monkeypatch):
    # Skip the CVE researcher (needs DB+pgvector).
    from app.agents import cve_researcher

    monkeypatch.setattr(
        cve_researcher, "cve_researcher_node", lambda state: state, raising=True
    )

    payload = {
        "files": [
            {
                "path": "app.py",
                "language": "python",
                "content": (
                    'API_KEY = "AKIAIOSFODNN7EXAMPLE"\n'
                    "import subprocess\n"
                    "subprocess.run(cmd, shell=True)\n"
                ),
            }
        ],
        "triggered_by": "test",
    }

    r = client.post("/scans", json=payload)
    assert r.status_code == 201, r.text
    scan_id = r.json()["id"]
    assert r.json()["findings_count"] >= 1

    r = client.get(f"/scans/{scan_id}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["status"] == "completed"
    assert any(v["category"] == "secret" for v in detail["vulnerabilities"])

    r = client.get("/scans")
    assert r.status_code == 200
    assert r.json()["total"] >= 1
