"""Retry & degrade policy for the harness tool loop.

Philosophy:
- **Models recover from error messages better than from exceptions.**
  When a tool fails, we surface the error text as a tool_result block and
  let the model decide what to do. We don't crash the whole run.
- **Transient HTTP errors** (connection reset, 429, 500-series) retry with
  small exponential backoff, capped. 4xx (except 429) do not retry.
- **Max step cap** prevents a confused model from looping forever.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Callable, TypeVar

log = logging.getLogger("mindos.harness.recovery")

T = TypeVar("T")

_RETRIABLE_HTTP = {408, 409, 429, 500, 502, 503, 504}


class HarnessError(Exception):
    """Unrecoverable harness failure."""


def with_retries(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    sleep: Callable[[float], None] = time.sleep,
    label: str = "call",
) -> T:
    """Run `fn()` with exponential backoff on transient failures."""
    last_exc: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            if not _is_retriable(e) or i == attempts:
                if last_exc is None:
                    last_exc = e
                raise HarnessError(f"{label} failed after {i} attempt(s): {e}") from e
            last_exc = e
            delay = min(max_delay, base_delay * (2 ** (i - 1)))
            delay *= 0.8 + 0.4 * random.random()  # jitter
            log.warning("%s transient failure (%s); retry %d/%d in %.2fs",
                        label, e, i, attempts, delay)
            sleep(delay)
    # Unreachable but keeps type-checkers happy
    raise HarnessError(f"{label} failed") from last_exc


def _is_retriable(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if isinstance(code, int) and code in _RETRIABLE_HTTP:
        return True
    msg = str(exc).lower()
    return any(t in msg for t in (
        "timeout", "timed out", "connection reset",
        "connection aborted", "temporarily unavailable",
    ))
