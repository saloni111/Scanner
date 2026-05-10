"""Tiny CLI that scans a local folder against a running scanner API.

Usage:
    python scripts/scan_local.py --path ./my-project --api http://localhost:8000

It walks the folder, packages each file into a /scans request, and prints
the resulting findings. Useful for spot-checking the scanner without
setting up GitHub.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

_TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".rb", ".php",
    ".cs", ".rs", ".c", ".cpp", ".h", ".hpp", ".sh", ".sql", ".yml",
    ".yaml", ".json", ".tf", ".kt",
}


def collect_files(root: Path, max_files: int, max_bytes: int) -> list[dict]:
    files: list[dict] = []
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in _TEXT_EXTENSIONS:
            continue
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        if p.stat().st_size > max_bytes:
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        files.append(
            {
                "path": str(p.relative_to(root)),
                "content": content,
            }
        )
        if len(files) >= max_files:
            break
    return files


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, required=True, help="Folder to scan")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--max-files", type=int, default=100)
    parser.add_argument("--max-bytes", type=int, default=200_000)
    args = parser.parse_args()

    if not args.path.exists():
        print(f"Path not found: {args.path}", file=sys.stderr)
        return 2

    files = collect_files(args.path, args.max_files, args.max_bytes)
    if not files:
        print("No source files found.", file=sys.stderr)
        return 1

    print(f"Submitting {len(files)} file(s) to {args.api} ...")
    with httpx.Client(timeout=120) as client:
        r = client.post(f"{args.api}/scans", json={"files": files})
        r.raise_for_status()
        scan = r.json()
        print(f"Scan id: {scan['id']}  findings: {scan['findings_count']}  risk: {scan['risk_score']}")

        detail = client.get(f"{args.api}/scans/{scan['id']}").json()
        print("\nSummary:\n" + (detail.get("summary") or ""))

        print("\nFindings:")
        for v in detail.get("vulnerabilities", []):
            loc = f"{v['file_path']}:{v.get('line_start') or '?'}"
            print(f"  [{v['severity'].upper():8}] {v['title']}  ({loc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
