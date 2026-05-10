"""HTTP routes for managing scans."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.database import get_db
from app.models.scan import Scan, ScanStatus
from app.schemas.scan import (
    PRScanRequest,
    ScanCreate,
    ScanDetail,
    ScanListItem,
    ScanListResponse,
    ScanResult,
)
from app.services.github import GitHubService
from app.services.scanner import ScannerService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/scans", tags=["scans"])


def _scanner() -> ScannerService:
    return ScannerService()


@router.post(
    "",
    response_model=ScanResult,
    status_code=status.HTTP_201_CREATED,
    summary="Submit code for scanning",
)
def create_scan(
    payload: ScanCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    scanner: ScannerService = Depends(_scanner),
) -> ScanResult:
    """Run a synchronous scan over a list of files.

    The scan record is created immediately. For small payloads the analysis
    runs inline. For very large submissions consider using `/scans/pr` which
    streams files from GitHub.
    """
    settings = get_settings()
    if len(payload.files) > settings.max_files_per_scan:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files: limit is {settings.max_files_per_scan}",
        )

    scan = scanner.run_scan(
        db,
        files=payload.files,
        repository=payload.repository,
        triggered_by=payload.triggered_by,
    )

    return ScanResult(
        id=scan.id,
        status=scan.status.value,
        findings_count=scan.findings_count,
        risk_score=scan.risk_score,
    )


@router.post(
    "/pr",
    response_model=ScanResult,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Scan a GitHub pull request",
)
def scan_pull_request(
    payload: PRScanRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    scanner: ScannerService = Depends(_scanner),
) -> ScanResult:
    """Pull files from a GitHub PR and run them through the agents.

    The scan starts immediately and continues in the background; clients can
    poll `GET /scans/{id}` to track progress.
    """
    gh = GitHubService()
    try:
        files, commit_sha = gh.fetch_pr_files(payload.repository, payload.pr_number)
    except Exception as exc:
        logger.exception("Failed to fetch PR files")
        raise HTTPException(status_code=502, detail=f"GitHub error: {exc}") from exc

    scan = scanner.create_pending_scan(
        db,
        source="pr",
        repository=payload.repository,
        pr_number=payload.pr_number,
        commit_sha=commit_sha,
        triggered_by=payload.triggered_by,
    )

    background.add_task(scanner.execute_async, scan.id, files)

    return ScanResult(
        id=scan.id,
        status=scan.status.value,
        findings_count=0,
        risk_score=0,
    )


@router.get("", response_model=ScanListResponse, summary="List scans")
def list_scans(
    db: Session = Depends(get_db),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repository: str | None = Query(default=None),
    status_filter: ScanStatus | None = Query(default=None, alias="status"),
) -> ScanListResponse:
    base = select(Scan)
    if repository:
        base = base.where(Scan.repository == repository)
    if status_filter:
        base = base.where(Scan.status == status_filter)

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(desc(Scan.created_at)).limit(limit).offset(offset)
    ).all()

    return ScanListResponse(
        total=total,
        items=[
            ScanListItem(
                id=r.id,
                source=r.source.value,
                repository=r.repository,
                pr_number=r.pr_number,
                status=r.status.value,
                findings_count=r.findings_count,
                risk_score=r.risk_score,
                created_at=r.created_at,
                completed_at=r.completed_at,
            )
            for r in rows
        ],
    )


@router.get("/{scan_id}", response_model=ScanDetail, summary="Get a scan")
def get_scan(scan_id: str, db: Session = Depends(get_db)) -> ScanDetail:
    scan = db.scalar(
        select(Scan)
        .where(Scan.id == scan_id)
        .options(selectinload(Scan.vulnerabilities))
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    return ScanDetail(
        id=scan.id,
        source=scan.source.value,
        repository=scan.repository,
        pr_number=scan.pr_number,
        commit_sha=scan.commit_sha,
        status=scan.status.value,
        summary=scan.summary,
        risk_score=scan.risk_score,
        findings_count=scan.findings_count,
        metrics=scan.metrics,
        error=scan.error,
        created_at=scan.created_at,
        completed_at=scan.completed_at,
        vulnerabilities=[v for v in scan.vulnerabilities],
    )


@router.delete(
    "/{scan_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a scan",
)
def delete_scan(scan_id: str, db: Session = Depends(get_db)):
    scan = db.get(Scan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    db.delete(scan)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
