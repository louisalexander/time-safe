from __future__ import annotations

"""Countdown rendering shared by the TUI and the CLI. Imports nothing from Textual.

The sibling of `validation.py`: duration *parsing* was shared from the start, duration *rendering*
was not, and the two copies drifted until the same secret at the same moment read differently
depending on which interface you were looking at.
"""


def humanize_seconds(seconds: int, *, ready: str = "-") -> str:
    """Render a countdown, largest unit first, three units at most.

    `ready` is what to print once the wait is over — the only thing the two callers disagree about,
    because the CLI's table already carries a READY column and the TUI's row does not.
    """
    if seconds <= 0:
        return ready
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h {minutes:02d}m"
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    if minutes:
        return f"{minutes}m {secs:02d}s"
    return f"{secs}s"
