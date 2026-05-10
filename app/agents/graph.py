"""LangGraph wiring for the scanner pipeline.

The graph runs five specialized nodes in sequence:

    static_analyzer  ->  vulnerability_detector  ->  cve_researcher
                       \\                          /
                        merger  ->  severity_assessor  ->  report_generator

`merger` deduplicates findings from the rule-based and LLM agents, and the
final `report_generator` produces the human summary stored on the scan.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.agents.cve_researcher import cve_researcher_node
from app.agents.report_generator import report_generator_node
from app.agents.severity_assessor import severity_assessor_node
from app.agents.state import AgentState
from app.agents.static_analyzer import static_analyzer_node
from app.agents.vulnerability_detector import vulnerability_detector_node


def _merger_node(state: AgentState) -> AgentState:
    """Combine static and AI findings, dropping near-duplicates."""
    static = state.get("static_findings", []) or []
    ai = state.get("ai_findings", []) or []
    merged: list[dict] = []
    seen: set[tuple[str, int | None, str]] = set()

    for finding in [*static, *ai]:
        key = (
            finding.get("file_path", ""),
            finding.get("line_start"),
            finding.get("category", ""),
        )
        if key in seen:
            # If the AI agent and the static one report the same issue, prefer
            # the higher-confidence record by replacing it.
            for i, existing in enumerate(merged):
                ekey = (
                    existing.get("file_path", ""),
                    existing.get("line_start"),
                    existing.get("category", ""),
                )
                if ekey == key and finding.get("confidence", 0) > existing.get(
                    "confidence", 0
                ):
                    merged[i] = finding
                    break
            continue
        seen.add(key)
        merged.append(finding)

    state["merged_findings"] = merged
    metrics = state.get("metrics", {}) or {}
    metrics.update(
        {
            "static_findings": len(static),
            "ai_findings": len(ai),
            "merged_findings": len(merged),
        }
    )
    state["metrics"] = metrics
    return state


def build_scan_graph():
    """Compile the LangGraph workflow."""
    graph = StateGraph(AgentState)

    graph.add_node("static_analyzer", static_analyzer_node)
    graph.add_node("vulnerability_detector", vulnerability_detector_node)
    graph.add_node("merger", _merger_node)
    graph.add_node("cve_researcher", cve_researcher_node)
    graph.add_node("severity_assessor", severity_assessor_node)
    graph.add_node("report_generator", report_generator_node)

    graph.add_edge(START, "static_analyzer")
    graph.add_edge("static_analyzer", "vulnerability_detector")
    graph.add_edge("vulnerability_detector", "merger")
    graph.add_edge("merger", "cve_researcher")
    graph.add_edge("cve_researcher", "severity_assessor")
    graph.add_edge("severity_assessor", "report_generator")
    graph.add_edge("report_generator", END)

    return graph.compile()
