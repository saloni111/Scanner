"""Severity assessor agent.

Walks the merged findings and adjusts severity based on context:
  * If a related CVE has a CVSS >= 9.0, bump the finding to at least HIGH.
  * If multiple findings share the same file, raise confidence slightly.
  * Cap severity for very low-confidence findings.

This keeps the final report calibrated even when individual agents disagree.
"""

from __future__ import annotations

from collections import Counter

from app.agents.state import AgentState
from app.utils.logger import get_logger

logger = get_logger(__name__)

_ORDER = ["info", "low", "medium", "high", "critical"]


def severity_assessor_node(state: AgentState) -> AgentState:
    findings = state.get("merged_findings", []) or []
    cve_context = state.get("cve_context", {}) or {}

    file_counts = Counter(f.get("file_path") for f in findings)

    for finding in findings:
        # Boost from related CVEs.
        cves = cve_context.get(finding.get("title"), [])
        max_cvss = max((c.get("cvss_score") or 0 for c in cves), default=0)
        if max_cvss >= 9.0:
            finding["severity"] = _at_least(finding["severity"], "high")
        elif max_cvss >= 7.0:
            finding["severity"] = _at_least(finding["severity"], "medium")

        # Cluster boost: many findings in the same file is suspicious.
        if file_counts[finding.get("file_path")] >= 3:
            finding["confidence"] = min(1.0, finding.get("confidence", 0.5) + 0.1)

        # Demote low-confidence noise.
        if finding.get("confidence", 0) < 0.3:
            finding["severity"] = _at_most(finding["severity"], "low")

    state["merged_findings"] = findings
    return state


def _at_least(current: str, floor: str) -> str:
    return _ORDER[max(_ORDER.index(current), _ORDER.index(floor))]


def _at_most(current: str, ceiling: str) -> str:
    return _ORDER[min(_ORDER.index(current), _ORDER.index(ceiling))]
