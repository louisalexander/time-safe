from __future__ import annotations

import re
from datetime import timedelta

"""Pure input validators shared by the TUI and the CLI. Imports nothing from Textual."""

_UNIT = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}
_REPO_RE = re.compile(r"^[^/\s]+/[^/\s]+$")


def parse_duration(text: str | None) -> timedelta:
    """Parse a lock duration like '30m', '2h', '7d', '1d12h', '90s'. A bare number means days."""
    s = re.sub(r"\s+", "", (text or "").strip().lower())
    if not s:
        raise ValueError("Enter a duration, e.g. 30m, 2h, 7d.")
    if s.isdigit():
        total = timedelta(days=int(s))
    else:
        if not re.fullmatch(r"(\d+[smhdw])+", s):
            raise ValueError("Invalid duration — use e.g. 30m, 2h, 7d, 1d12h.")
        kwargs: dict[str, int] = {}
        for num, unit in re.findall(r"(\d+)([smhdw])", s):
            kwargs[_UNIT[unit]] = kwargs.get(_UNIT[unit], 0) + int(num)
        total = timedelta(**kwargs)
    if total.total_seconds() <= 0:
        raise ValueError("Duration must be positive.")
    return total


def is_valid_email(raw: str | None) -> bool:
    if not raw:
        return False
    s = raw.strip()
    if not s or any(c.isspace() for c in s) or s.count("@") != 1:
        return False
    local, _, domain = s.partition("@")
    if not local or "." not in domain:
        return False
    return all(label for label in domain.split("."))


def is_valid_repo(repo: str | None) -> bool:
    return bool(repo) and _REPO_RE.match(repo) is not None
