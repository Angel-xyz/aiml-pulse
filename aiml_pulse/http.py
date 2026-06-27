"""Shared HTTP client with retries, timeouts, and rate limiting."""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter
)

from aiml_pulse.config import load_settings
from aiml_pulse.ethics import default_limiter, default_user_agent


def get_client() -> httpx.Client:
    settings = load_settings()
    return httpx.Client(
        headers={"User-Agent": settings.user_agent or default_user_agent()},
        timeout=settings.request_timeout_seconds,
        follow_redirects=True,
    )


def get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    """Fetch JSON with retries, rate limiting, and timeouts."""
    settings = load_settings()
    default_limiter.acquire()

    for attempt in Retrying(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential_jitter(initial=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    ):
        with attempt:
            with get_client() as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()

    raise RuntimeError("unreachable")  # pragma: no cover


def get_text(url: str, params: dict[str, Any] | None = None) -> str:
    """Fetch text with retries, rate limiting, and timeouts."""
    settings = load_settings()
    default_limiter.acquire()

    for attempt in Retrying(
        stop=stop_after_attempt(settings.max_retries),
        wait=wait_exponential_jitter(initial=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        reraise=True,
    ):
        with attempt:
            with get_client() as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.text

    raise RuntimeError("unreachable")