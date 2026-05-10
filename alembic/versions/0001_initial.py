"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    scan_source = sa.Enum("snippet", "pr", "repository", name="scan_source")
    scan_status = sa.Enum("pending", "running", "completed", "failed", name="scan_status")
    severity = sa.Enum("info", "low", "medium", "high", "critical", name="vuln_severity")

    op.create_table(
        "scans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source", scan_source, nullable=False, server_default="snippet"),
        sa.Column("repository", sa.String(255), nullable=True),
        sa.Column("pr_number", sa.Integer, nullable=True),
        sa.Column("commit_sha", sa.String(64), nullable=True),
        sa.Column("triggered_by", sa.String(120), nullable=True),
        sa.Column("status", scan_status, nullable=False, server_default="pending"),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("risk_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("findings_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("metrics", sa.JSON, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_scans_status", "scans", ["status"])
    op.create_index("ix_scans_created_at", "scans", ["created_at"])

    op.create_table(
        "scan_files",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "scan_id",
            sa.String(36),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("language", sa.String(40), nullable=True),
        sa.Column("size_bytes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index("ix_scan_files_scan_id", "scan_files", ["scan_id"])

    op.create_table(
        "vulnerabilities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "scan_id",
            sa.String(36),
            sa.ForeignKey("scans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("line_start", sa.Integer, nullable=True),
        sa.Column("line_end", sa.Integer, nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("severity", severity, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("recommendation", sa.Text, nullable=True),
        sa.Column("code_snippet", sa.Text, nullable=True),
        sa.Column("cwe_id", sa.String(20), nullable=True),
        sa.Column("related_cves", sa.JSON, nullable=True),
        sa.Column("detected_by", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_vulnerabilities_scan_id", "vulnerabilities", ["scan_id"])
    op.create_index("ix_vulnerabilities_severity", "vulnerabilities", ["severity"])
    op.create_index("ix_vulnerabilities_category", "vulnerabilities", ["category"])

    op.create_table(
        "cve_records",
        sa.Column("cve_id", sa.String(40), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("severity", sa.String(20), nullable=True),
        sa.Column("cvss_score", sa.Float, nullable=True),
        sa.Column("cwe_ids", sa.JSON, nullable=True),
        sa.Column("affected_products", sa.JSON, nullable=True),
        sa.Column("references", sa.JSON, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
    )

    # Approximate-NN index for fast similarity search.
    op.execute(
        "CREATE INDEX ix_cve_records_embedding "
        "ON cve_records USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cve_records_embedding")
    op.drop_table("cve_records")
    op.drop_index("ix_vulnerabilities_category", table_name="vulnerabilities")
    op.drop_index("ix_vulnerabilities_severity", table_name="vulnerabilities")
    op.drop_index("ix_vulnerabilities_scan_id", table_name="vulnerabilities")
    op.drop_table("vulnerabilities")
    op.drop_index("ix_scan_files_scan_id", table_name="scan_files")
    op.drop_table("scan_files")
    op.drop_index("ix_scans_created_at", table_name="scans")
    op.drop_index("ix_scans_status", table_name="scans")
    op.drop_table("scans")
    op.execute("DROP TYPE IF EXISTS vuln_severity")
    op.execute("DROP TYPE IF EXISTS scan_status")
    op.execute("DROP TYPE IF EXISTS scan_source")
