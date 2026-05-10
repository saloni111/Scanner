"""HTTP routes that expose the CVE knowledge base."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.rag.vectorstore import CVEVectorStore
from app.schemas.vulnerability import CVEMatch

router = APIRouter(prefix="/cve", tags=["cve"])


@router.get("/search", response_model=list[CVEMatch], summary="Semantic CVE search")
def search_cve(
    q: str = Query(..., min_length=3, description="Free-text query."),
    top_k: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> list[CVEMatch]:
    """Return CVE entries most similar to the query.

    Uses the RAG vector store (pgvector + OpenAI embeddings). Results include
    a similarity score in [0, 1].
    """
    store = CVEVectorStore(db)
    matches = store.search(q, top_k=top_k)
    return matches


@router.get("/{cve_id}", response_model=CVEMatch, summary="Get a CVE by ID")
def get_cve(cve_id: str, db: Session = Depends(get_db)) -> CVEMatch:
    store = CVEVectorStore(db)
    record = store.get(cve_id)
    if not record:
        raise HTTPException(status_code=404, detail="CVE not found")
    return CVEMatch(
        cve_id=record.cve_id,
        title=record.title,
        description=record.description,
        severity=record.severity,
        cvss_score=record.cvss_score,
        cwe_ids=record.cwe_ids,
        similarity=1.0,
    )
