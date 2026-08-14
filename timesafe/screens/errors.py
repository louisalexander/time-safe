from __future__ import annotations

from timesafe.errors import TimesafeError
from timesafe.format import humanize_seconds

"""Rendering `timesafe.errors` in the TUI.

The taxonomy exists so a caller can tell "not ready" from "broken", and that is exactly the
distinction a user needs to decide what to do next: `not_ready` means wait, `network` means retry,
`vault` means fix the token scope or the repo. Anything unlisted is a fault worth shouting about.
"""

_SEVERITY = {
    "not_ready": "warning",
    "network": "warning",
    "not_found": "warning",
    "ambiguous_name": "warning",
}


def severity_of(exc: TimesafeError) -> str:
    return _SEVERITY.get(exc.code, "error")


def message_of(exc: TimesafeError) -> str:
    """The error's own already-composed message, plus a countdown when it carries one.

    `NotReadyError` knows `seconds_remaining`, so "ready in 4m 12s" costs nothing and says far more
    than "not unlocked yet".
    """
    remaining = exc.extra.get("seconds_remaining")
    if remaining:
        return f"{exc.message} Ready in {humanize_seconds(int(remaining))}."
    return exc.message
