"""CVE researcher agent.

For each merged finding, query the RAG vector store for the most similar CVE
records. The top matches are attached to the finding so reviewers can jump
straight to the public advisories.
"""

from __future__ import annotations

from app.agents.state import AgentState
from app.database import SessionLocal
from app.rag.vectorstore import CVEVectorStore
from app.utils.logger import get_logger

logger = get_logger(__name__)


def cve_researcher_node(state: AgentState) -> AgentState:
    findings = state.get("merged_findings", []) or []
    if not findings:
        return state

    db = SessionLocal()
    try:
        store = CVEVectorStore(db)
        cve_context: dict[str, list[dict]] = {}

        for finding in findings:
            query = _build_query(finding)
            try:
                matches = store.search(query, top_k=3)
            except Exception as exc:
                logger.warning(f"CVE search failed: {exc}")
                continue

            if not matches:
                continue

            related = [m.cve_id for m in matches]
            finding["related_cves"] = related
            cve_context[finding["title"]] = [m.model_dump() for m in matches]

        state["cve_context"] = cve_context
        metrics = state.get("metrics", {}) or {}
        metrics["cve_lookups"] = len(findings)
        state["metrics"] = metrics
    finally:
        db.close()

    return state


def _build_query(finding: dict) -> str:
    pieces = [
        finding.get("title") or "",
        finding.get("category") or "",
        finding.get("cwe_id") or "",
        finding.get("description") or "",
    ]
    return " ".join(p for p in pieces if p).strip()
