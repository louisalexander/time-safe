from __future__ import annotations

from typing import Any

"""Typed CLI errors.

Each class binds a process exit code to a stable, machine-readable `code` string, so callers can
branch on either without parsing prose. Exit codes are part of the CLI's public contract:

    0  success
    2  usage error
    3  not yet unlockable
    4  vault / network error
    5  no such secret
"""


class TimesafeError(Exception):
    """Base for every error the CLI reports. Never carries secret material in its message."""

    exit_code = 4
    code = "vault"

    def __init__(self, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.message = message
        self.extra = extra

    def to_json(self) -> dict[str, Any]:
        return {"error": self.message, "code": self.code, **self.extra}


class UsageError(TimesafeError):
    """Bad invocation: unknown flags, no vault selected, unusable stdin."""

    exit_code = 2
    code = "usage"


class EmptyStdinError(UsageError):
    """`--secret-stdin` was given but stdin held nothing."""

    code = "empty_stdin"


class AmbiguousNameError(UsageError):
    """A `--name` lookup matched more than one secret. Never resolved by guessing."""

    code = "ambiguous_name"


class NotReadyError(TimesafeError):
    """The secret's unlock round has not arrived. Distinct code so callers can tell it from a fault."""

    exit_code = 3
    code = "not_ready"


class VaultError(TimesafeError):
    """The vault could not be read or written."""

    exit_code = 4
    code = "vault"


class NetworkError(VaultError):
    """A vault error whose cause was transport-level, so callers can choose to retry."""

    code = "network"


class NotFoundError(TimesafeError):
    """No secret matched the given id or name."""

    exit_code = 5
    code = "not_found"
