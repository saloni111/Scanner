"""Scanner service: orchestrates persistence + multi-agent execution."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from app.agents.graph import build_scan_graph
from app.agents.state import AgentState, FileBlob
from app.database import SessionLocal
from app.models.scan import Scan, ScanFile, ScanSource, ScanStatus
from app.models.vulnerability import SEVERITY_SCORES, Severity, Vulnerability
from app.schemas.scan import FileInput
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ScannerService:
    """Coordinates scan lifecycle: create -> execute graph -> persist findings."""

    def __init__(self) -> None:
        self._graph = build_scan_graph()

    # ------------------------------------------------------------------ create

    def create_pending_scan(
        self,
        db: Session,
        *,
        source: str = "snippet",
        repository: str | None = None,
        pr_number: int | None = None,
        commit_sha: str | None = None,
        triggered_by: str | None = None,
    ) -> Scan:
        scan = Scan(
            source=ScanSource(source),
            repository=repository,
            pr_number=pr_number,
            commit_sha=commit_sha,
            triggered_by=triggered_by,
            status=ScanStatus.PENDING,
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)
        return scan

    # ----------------------------------------------------------------- execute

    def run_scan(
        self,
        db: Session,
        *,
        files: list[FileInput],
        repository: str | None = None,
        triggered_by: str | None = None,
    ) -> Scan:
        """Synchronous scan flow used by the snippet endpoint."""
        scan = self.create_pending_scan(
            db,
            source="snippet" if not repository else "repository",
            repository=repository,
            triggered_by=triggered_by,
        )
        self._execute(db, scan, [(f.path, f.content, f.language) for f in files])
        return scan

    def execute_async(
        self,
        scan_id: str,
        files: list[tuple[str, str, str | None]],
    ) -> None:
        """Background-task entrypoint. Manages its own DB session."""
        db = SessionLocal()
        try:
            scan = db.get(Scan, scan_id)
            if scan is None:
                logger.error(f"Async scan {scan_id} not found")
                return
            self._execute(db, scan, files)
        finally:
            db.close()

    # ----------------------------------------------------------------- internal

    def _execute(
        self,
        db: Session,
        scan: Scan,
        files: Iterable[tuple[str, str, str | None]],
    ) -> None:
        scan.status = ScanStatus.RUNNING
        db.commit()
        started = time.time()

        blobs: list[FileBlob] = []
        for path, content, language in files:
            blob = FileBlob(
                path=path,
                content=content,
                language=language or _guess_language(path),
            )
            blobs.append(blob)
            db.add(
                ScanFile(
                    scan_id=scan.id,
                    path=path,
                    language=blob.language,
                    size_bytes=len(content.encode("utf-8")),
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                )
            )
        db.commit()

        try:
            initial_state: AgentState = {
                "files": blobs,
                "scan_id": scan.id,
                "static_findings": [],
                "ai_findings": [],
                "merged_findings": [],
                "cve_context": {},
                "summary": "",
                "metrics": {},
            }
            final_state = self._graph.invoke(initial_state)
        except Exception as exc:
            logger.exception("Scan failed")
            scan.status = ScanStatus.FAILED
            scan.error = str(exc)
            scan.completed_at = datetime.utcnow()
            db.commit()
            return

        findings = final_state.get("merged_findings", [])
        for f in findings:
            db.add(
                Vulnerability(
                    scan_id=scan.id,
                    file_path=f["file_path"],
                    line_start=f.get("line_start"),
                    line_end=f.get("line_end"),
                    title=f["title"],
                    category=f["category"],
                    severity=Severity(f["severity"]),
                    confidence=f.get("confidence", 0.5),
                    description=f["description"],
                    recommendation=f.get("recommendation"),
                    code_snippet=f.get("code_snippet"),
                    cwe_id=f.get("cwe_id"),
                    related_cves=f.get("related_cves"),
                    detected_by=f.get("detected_by"),
                )
            )

        scan.findings_count = len(findings)
        scan.risk_score = _compute_risk_score(findings)
        scan.summary = final_state.get("summary")
        scan.metrics = {
            **final_state.get("metrics", {}),
            "duration_ms": int((time.time() - started) * 1000),
            "files_scanned": len(blobs),
        }
        scan.status = ScanStatus.COMPLETED
        scan.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(scan)
        logger.info(
            f"Scan {scan.id} completed: {scan.findings_count} findings, "
            f"risk={scan.risk_score}"
        )


# ---------------------------------------------------------------------- helpers


def _compute_risk_score(findings: list[dict]) -> int:
    """Aggregate severity scores into a 0-100 risk score."""
    if not findings:
        return 0
    total = sum(
        SEVERITY_SCORES.get(Severity(f["severity"]), 1) * f.get("confidence", 0.5)
        for f in findings
    )
    return min(100, int(total))


_LANG_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".sh": "bash",
    ".sql": "sql",
    ".yml": "yaml",
    ".yaml": "yaml",
}


def _guess_language(path: str) -> str:
    lower = path.lower()
    for ext, lang in _LANG_MAP.items():
        if lower.endswith(ext):
            return lang
    return "text"
