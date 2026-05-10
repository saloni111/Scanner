"""Shared test setup.

Tests run with a sqlite-backed database and no LLM key. Doing this in a
top-level conftest means the env vars are set before anything in `app`
imports.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_scanner.sqlite")
os.environ.setdefault("OPENAI_API_KEY", "")
