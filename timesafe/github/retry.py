from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, TypeVar

import httpx

"""Bounded retry with exponential backoff, for idempotent GitHub reads only.

A single attempt is right for an interactive run, but the CLI exists for unattended cron and
systemd use, where a transient 5xx turning a break-glass check into a hard failure is worse than a
few seconds of waiting. So reads retry, and writes never do — `add` is not idempotent, and a
retried write after an ambiguous failure risks a duplicate or a confusing partial state. The
existing cleanup path already leaves the vault clean for the caller to retry deliberately.

The ceiling matters as much as the retrying: a cron job that hangs is a worse failure than one that
exits 4, so the total wait can never exceed MAX_TOTAL_DELAY.
"""

ATTEMPTS = 3
BASE_DELAY = 1.0
MAX_DELAY = 5.0
MAX_TOTAL_DELAY = MAX_DELAY * (ATTEMPTS - 1)

# 403 is deliberately absent: an unscoped token answers 403 forever, and retrying it would cost
# every single run the full budget. GitHub's *secondary* rate limit also answers 403, but it says
# so with a Retry-After, which is handled separately below.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

T = TypeVar("T")


def is_retryable(exc: BaseException) -> bool:
    """True for failures that a second attempt could plausibly resolve."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status in RETRYABLE_STATUS or (
            status == 403 and _retry_after(exc.response) is not None
        )
    # TransportError covers connection resets, DNS blips, timeouts and protocol errors — every
    # transport-level cause that NetworkError already reports as `code: "network"`.
    return isinstance(exc, httpx.TransportError)


def _retry_after(response: httpx.Response) -> float | None:
    """The Retry-After header in seconds, or None if absent or in the HTTP-date form.

    Only the delta-seconds form is honoured. The HTTP-date form needs the server's clock to agree
    with ours, and getting that wrong means waiting the wrong amount for no benefit.
    """
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        return float(raw.strip())
    except ValueError:
        return None


def _delay_before_retry(exc: BaseException, attempt: int) -> float | None:
    """Seconds to wait before attempt `attempt + 1`, or None to give up now."""
    if isinstance(exc, httpx.HTTPStatusError):
        after = _retry_after(exc.response)
        if after is not None:
            # A cooldown longer than our whole budget is not something an unattended run should sit
            # through — fail now and let the next scheduled run try, rather than block for an hour.
            return after if after <= MAX_DELAY else None
    return min(BASE_DELAY * 2 ** (attempt - 1), MAX_DELAY)


def retrying(
    fn: Callable[..., T],
    *,
    attempts: int = ATTEMPTS,
    sleep: Callable[[float], Any] = time.sleep,
) -> Callable[..., T]:
    """Wrap `fn` so transient failures are retried. `attempts=1` makes the wrapper a pass-through.

    Wraps the whole call, not any one HTTP request: a read is idempotent however many requests it
    happens to be made of, so this stays correct if the underlying implementation changes.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        for attempt in range(1, attempts + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 — is_retryable decides; everything else re-raises
                if attempt == attempts or not is_retryable(exc):
                    raise
                delay = _delay_before_retry(exc, attempt)
                if delay is None:
                    raise
                sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover

    return wrapper
