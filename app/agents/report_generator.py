"""Report generator agent.

Writes the executive summary that's shown at the top of the scan detail
page. Uses the LLM if available, otherwise falls back to a simple template.
"""

from __future__ import annotations

import json
from collections import Counter

from app.agents.llm import LLMUnavailable, chat_json
from app.agents.state import AgentState
from app.utils.logger import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """You are summarizing the result of an automated security scan
for engineers reviewing a pull request. Write a concise, factual paragraph (3-5
sentences). Highlight the highest-severity issues, name the affected files, and
end with the most important recommended action. Avoid marketing language.

Respond with JSON: {"summary": "..."}.
"""


def report_generator_node(state: AgentState) -> AgentState:
    findings = state.get("merged_findings", []) or []
    if not findings:
        state["summary"] = "No vulnerabilities detected. Nice work!"
        return state

    severity_counts = Counter(f.get("severity") for f in findings)
    summary = _llm_summary(findings) or _template_summary(findings, severity_counts)
    state["summary"] = summary
    return state


def _llm_summary(findings: list[dict]) -> str | None:
    try:
        compact = [
            {
                "file": f.get("file_path"),
                "line": f.get("line_start"),
                "severity": f.get("severity"),
                "title": f.get("title"),
            }
            for f in findings[:30]
        ]
        data = chat_json(
            _SYSTEM_PROMPT,
            "Findings:\n" + json.dumps(compact, indent=2),
        )
        return (data.get("summary") or "").strip() or None
    except LLMUnavailable:
        return None
    except Exception as exc:
        logger.warning(f"summary LLM call failed: {exc}")
        return None


def _template_summary(findings: list[dict], counts: Counter) -> str:
    parts = [f"Found {len(findings)} potential issue(s):"]
    for sev in ("critical", "high", "medium", "low", "info"):
        if counts.get(sev):
            parts.append(f"{counts[sev]} {sev}")
    top = sorted(
        findings,
        key=lambda f: (
            -["info", "low", "medium", "high", "critical"].index(f.get("severity", "info")),
            -f.get("confidence", 0),
        ),
    )[:3]
    if top:
        joined = "; ".join(
            f"{f['title']} in {f['file_path']}"
            + (f":{f['line_start']}" if f.get("line_start") else "")
            for f in top
        )
        parts.append(f"Top concerns: {joined}.")
    return " ".join(parts)
