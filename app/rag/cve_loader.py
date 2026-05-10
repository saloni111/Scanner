"""CLI to seed the CVE knowledge base.

Usage:
    python -m app.rag.cve_loader --seed
    python -m app.rag.cve_loader --file path/to/cves.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.database import SessionLocal
from app.rag.vectorstore import CVEVectorStore
from app.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_SEED = Path(__file__).resolve().parents[2] / "data" / "cve_seed.json"


def load_from_file(path: Path) -> int:
    if not path.exists():
        logger.error(f"File not found: {path}")
        return 0

    records = json.loads(path.read_text())
    db = SessionLocal()
    try:
        store = CVEVectorStore(db)
        count = store.upsert(records)
        logger.info(f"Loaded {count} CVE records from {path}")
        return count
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the CVE vector store.")
    parser.add_argument("--seed", action="store_true", help="Load the bundled seed file.")
    parser.add_argument("--file", type=Path, help="Path to a JSON file of CVE records.")
    args = parser.parse_args()

    if args.file:
        load_from_file(args.file)
    elif args.seed:
        load_from_file(_DEFAULT_SEED)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
