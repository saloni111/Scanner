"""Thin wrapper around PyGithub for fetching PR diffs."""

from __future__ import annotations

import base64

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class GitHubService:
    def __init__(self, token: str | None = None) -> None:
        settings = get_settings()
        self.token = token or settings.github_token
        self.max_files = settings.max_files_per_scan
        self.max_file_bytes = settings.max_file_size_kb * 1024

    def _client(self):
        # Imported lazily so the rest of the app keeps working without PyGithub
        # installed (e.g. local snippet-only scans).
        from github import Auth, Github

        if not self.token:
            raise RuntimeError("GITHUB_TOKEN not configured")
        return Github(auth=Auth.Token(self.token))

    def fetch_pr_files(
        self, repository: str, pr_number: int
    ) -> tuple[list[tuple[str, str, str | None]], str]:
        """Return `(files, head_sha)` where files is a list of `(path, content, language)`.

        Skips deleted files, binary blobs, and files that exceed the size limit.
        """
        gh = self._client()
        repo = gh.get_repo(repository)
        pr = repo.get_pull(pr_number)
        head_sha = pr.head.sha

        files: list[tuple[str, str, str | None]] = []
        for f in pr.get_files():
            if f.status == "removed":
                continue
            if len(files) >= self.max_files:
                logger.warning(
                    f"PR {repository}#{pr_number} has more than "
                    f"{self.max_files} files, truncating."
                )
                break
            try:
                blob = repo.get_contents(f.filename, ref=head_sha)
            except Exception:
                logger.debug(f"Skipping unreadable file {f.filename}")
                continue
            if blob.size and blob.size > self.max_file_bytes:
                logger.info(f"Skipping large file {f.filename} ({blob.size} bytes)")
                continue
            content = _decode_blob(blob)
            if content is None:
                continue
            files.append((f.filename, content, None))

        return files, head_sha


def _decode_blob(blob) -> str | None:
    try:
        if blob.encoding == "base64":
            return base64.b64decode(blob.content).decode("utf-8", errors="replace")
        return blob.decoded_content.decode("utf-8", errors="replace")
    except Exception:
        return None
