"""Process-local pacing for Gemini model requests."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

_DEFAULT_INTERVAL_SECONDS = 15.0

_lock: asyncio.Lock | None = None
_last_request_started_at: float | None = None


def _interval_seconds() -> float:
    raw = os.getenv(
        "CANONFLOW_GEMINI_MIN_INTERVAL_SECONDS",
        str(_DEFAULT_INTERVAL_SECONDS),
    )

    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(
            "CANONFLOW_GEMINI_MIN_INTERVAL_SECONDS must be numeric"
        ) from exc

    if value < 0:
        raise RuntimeError(
            "CANONFLOW_GEMINI_MIN_INTERVAL_SECONDS must be >= 0"
        )

    return value


def _get_lock() -> asyncio.Lock:
    global _lock

    if _lock is None:
        _lock = asyncio.Lock()

    return _lock


async def pace_gemini_requests(
    callback_context: Any,
    llm_request: Any,
) -> None:
    """Ensure a minimum interval between model request starts.

    Parameter names intentionally follow the Google ADK callback contract.
    Returning None permits the model request.
    """

    del callback_context, llm_request

    global _last_request_started_at

    interval = _interval_seconds()

    async with _get_lock():
        now = time.monotonic()

        if _last_request_started_at is not None:
            elapsed = now - _last_request_started_at
            delay = max(0.0, interval - elapsed)

            if delay:
                print(
                    f"GEMINI RATE LIMIT: waiting {delay:.2f}s "
                    f"(minimum interval {interval:.2f}s)",
                    flush=True,
                )
                await asyncio.sleep(delay)

        _last_request_started_at = time.monotonic()

    return None
