"""Shared state passed between LangGraph agent nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict


@dataclass
class FileBlob:
    path: str
    content: str
    language: str | None = None

    @property
    def line_count(self) -> int:
        return self.content.count("\n") + 1


class Finding(TypedDict, total=False):
    """A single vulnerability finding (used in graph state).

    The DB model `Vulnerability` mirrors these fields.
    """

    file_path: str
    line_start: int | None
    line_end: int | None
    title: str
    category: str
    severity: str  # one of: info | low | medium | high | critical
    confidence: float
    description: str
    recommendation: str | None
    code_snippet: str | None
    cwe_id: str | None
    related_cves: list[str] | None
    detected_by: str  # which agent emitted it


class AgentState(TypedDict, total=False):
    files: list[FileBlob]
    scan_id: str

    static_findings: list[Finding]
    ai_findings: list[Finding]
    merged_findings: list[Finding]

    cve_context: dict[str, list[dict[str, Any]]]
    summary: str
    metrics: dict[str, Any]
