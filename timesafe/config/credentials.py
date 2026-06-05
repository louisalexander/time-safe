from __future__ import annotations

from typing import Protocol

import keyring
import keyring.errors

SERVICE_PREFIX = "timesafe"
ACCOUNT = "timesafe"


def service_name(repo: str) -> str:
    return f"{SERVICE_PREFIX}:{repo}"


class CredentialStore(Protocol):
    """Stores a GitHub PAT per vault repo. Implementations never persist tokens in plaintext files."""

    def get(self, repo: str) -> str | None: ...
    def put(self, repo: str, token: str) -> None: ...
    def delete(self, repo: str) -> None: ...


class KeyringCredentialStore:
    """PATs in the OS keychain via `keyring`, one entry per vault repo."""

    def get(self, repo: str) -> str | None:
        return keyring.get_password(service_name(repo), ACCOUNT)

    def put(self, repo: str, token: str) -> None:
        keyring.set_password(service_name(repo), ACCOUNT, token)

    def delete(self, repo: str) -> None:
        try:
            keyring.delete_password(service_name(repo), ACCOUNT)
        except keyring.errors.PasswordDeleteError:
            pass  # already absent — fine


class InMemoryCredentialStore:
    """Non-persistent CredentialStore for tests and headless runs."""

    def __init__(self) -> None:
        self._tokens: dict[str, str] = {}

    def get(self, repo: str) -> str | None:
        return self._tokens.get(repo)

    def put(self, repo: str, token: str) -> None:
        self._tokens[repo] = token

    def delete(self, repo: str) -> None:
        self._tokens.pop(repo, None)
