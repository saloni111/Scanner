"""End-to-end test for the LangGraph pipeline using stubbed externals."""

from __future__ import annotations

from unittest.mock import patch

from app.agents.graph import build_scan_graph
from app.agents.state import AgentState, FileBlob

_VULNERABLE_CODE = """\
import pickle
import subprocess

API_KEY = "AKIAIOSFODNN7EXAMPLE"

def run(payload, cmd):
    obj = pickle.loads(payload)
    subprocess.run(cmd, shell=True)
    return obj
"""


def test_graph_runs_end_to_end_without_llm():
    """With no OPENAI_API_KEY, the LLM nodes are skipped and we still get static findings."""
    graph = build_scan_graph()

    initial: AgentState = {
        "files": [FileBlob(path="app.py", content=_VULNERABLE_CODE, language="python")],
        "scan_id": "test-scan",
        "static_findings": [],
        "ai_findings": [],
        "merged_findings": [],
        "cve_context": {},
        "summary": "",
        "metrics": {},
    }

    # Patch the CVE researcher so it doesn't try to hit the database.
    with patch("app.agents.cve_researcher.SessionLocal") as session_factory:
        session_factory.return_value.__enter__ = lambda self: self
        session_factory.return_value.__exit__ = lambda *a: None
        # The node opens a session and calls .close(); we make it a no-op.
        fake = session_factory.return_value
        fake.close = lambda: None
        with patch("app.agents.cve_researcher.CVEVectorStore") as store_cls:
            store_cls.return_value.search.return_value = []
            result = graph.invoke(initial)

    findings = result["merged_findings"]
    assert len(findings) >= 3  # secret, pickle, subprocess shell=True
    categories = {f["category"] for f in findings}
    assert {"secret", "deserialization", "command-injection"}.issubset(categories)
    assert result["summary"]
    assert result["metrics"]["static_findings"] >= 3
    assert result["metrics"]["llm_used"] is False
