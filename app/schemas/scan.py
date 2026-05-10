"""Scan-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.vulnerability import VulnerabilityOut


class FileInput(BaseModel):
    """Single file submitted to the scanner."""

    path: str = Field(..., description="Relative path of the file inside the repo.")
    content: str = Field(..., description="Raw file contents.")
    language: str | None = Field(
        default=None,
        description="Optional language hint (python, javascript, go, ...).",
    )


class ScanCreate(BaseModel):
    """Request body for creating a snippet/manual scan."""

    files: list[FileInput] = Field(..., min_length=1)
    repository: str | None = None
    triggered_by: str | None = None


class PRScanRequest(BaseModel):
    """Request body for scanning a GitHub pull request."""

    repository: str = Field(..., description="owner/repo slug, e.g. acme/api")
    pr_number: int = Field(..., gt=0)
    triggered_by: str | None = None


class ScanResult(BaseModel):
    """Slim response returned right after a scan kicks off."""

    id: str
    status: str
    findings_count: int
    risk_score: int


class ScanListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    repository: str | None
    pr_number: int | None
    status: str
    findings_count: int
    risk_score: int
    created_at: datetime
    completed_at: datetime | None


class ScanDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    repository: str | None
    pr_number: int | None
    commit_sha: str | None
    status: str
    summary: str | None
    risk_score: int
    findings_count: int
    metrics: dict | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    vulnerabilities: list[VulnerabilityOut] = []


class ScanListResponse(BaseModel):
    total: int
    items: list[ScanListItem]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    llm_enabled: bool
