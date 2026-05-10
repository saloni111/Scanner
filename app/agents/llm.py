"""LLM helper used by agent nodes.

Wraps the OpenAI chat client and falls back to a deterministic stub when no
API key is configured. That keeps the project usable in CI / local dev without
network access.
"""

from __future__ import annotations

import json
from typing import Any

from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMUnavailable(RuntimeError):
    """Raised when the LLM is not configured."""


def chat_json(system: str, user: str, *, temperature: float = 0.1) -> dict[str, Any]:
    """Send a chat request and parse the JSON response.

    The caller is expected to instruct the model to respond in strict JSON.
    Raises `LLMUnavailable` if no API key is configured (no retry); other
    transient errors are retried with exponential backoff.
    """
    settings = get_settings()
    if not settings.llm_enabled:
        raise LLMUnavailable("OPENAI_API_KEY is not set")
    return _chat_json_with_retry(system, user, temperature, settings)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=8),
    retry=retry_if_not_exception_type(LLMUnavailable),
    reraise=True,
)
def _chat_json_with_retry(
    system: str, user: str, temperature: float, settings
) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = response.choices[0].message.content or "{}"
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON content; ignoring.")
        return {}
