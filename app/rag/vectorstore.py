"""pgvector-backed CVE store with semantic search."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cve import CVERecord
from app.rag.embeddings import embed_text
from app.schemas.vulnerability import CVEMatch
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CVEVectorStore:
    def __init__(self, db: Session) -> None:
        self.db = db

    # -------------------------------------------------------------- read

    def get(self, cve_id: str) -> CVERecord | None:
        return self.db.get(CVERecord, cve_id)

    def search(self, query: str, *, top_k: int = 5) -> list[CVEMatch]:
        """Return the `top_k` CVE entries most similar to `query`.

        Uses pgvector cosine distance. Distance is converted to a 0-1
        similarity score (1 = identical).
        """
        if not query.strip():
            return []

        query_vec = embed_text(query)
        distance = CVERecord.embedding.cosine_distance(query_vec).label("distance")
        stmt = (
            select(CVERecord, distance)
            .where(CVERecord.embedding.is_not(None))
            .order_by(distance)
            .limit(top_k)
        )
        rows = self.db.execute(stmt).all()

        out: list[CVEMatch] = []
        for record, dist in rows:
            similarity = max(0.0, 1.0 - float(dist))
            out.append(
                CVEMatch(
                    cve_id=record.cve_id,
                    title=record.title,
                    description=record.description,
                    severity=record.severity,
                    cvss_score=record.cvss_score,
                    cwe_ids=record.cwe_ids,
                    similarity=round(similarity, 4),
                )
            )
        return out

    # -------------------------------------------------------------- write

    def upsert(self, records: list[dict]) -> int:
        """Insert or update records and (re)compute their embeddings."""
        n = 0
        for entry in records:
            cve_id = entry["cve_id"]
            existing = self.db.get(CVERecord, cve_id)
            text = self._embedding_text(entry)
            embedding = embed_text(text)

            if existing:
                existing.title = entry["title"]
                existing.description = entry["description"]
                existing.severity = entry.get("severity")
                existing.cvss_score = entry.get("cvss_score")
                existing.cwe_ids = entry.get("cwe_ids")
                existing.affected_products = entry.get("affected_products")
                existing.references = entry.get("references")
                existing.embedding = embedding
            else:
                self.db.add(
                    CVERecord(
                        cve_id=cve_id,
                        title=entry["title"],
                        description=entry["description"],
                        severity=entry.get("severity"),
                        cvss_score=entry.get("cvss_score"),
                        cwe_ids=entry.get("cwe_ids"),
                        affected_products=entry.get("affected_products"),
                        references=entry.get("references"),
                        embedding=embedding,
                    )
                )
            n += 1
        self.db.commit()
        return n

    @staticmethod
    def _embedding_text(entry: dict) -> str:
        cwes = " ".join(entry.get("cwe_ids") or [])
        products = " ".join(entry.get("affected_products") or [])
        return (
            f"{entry['cve_id']}. {entry['title']}. "
            f"CWE: {cwes}. Affects: {products}. {entry['description']}"
        )
