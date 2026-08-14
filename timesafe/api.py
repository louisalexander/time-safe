from __future__ import annotations

import contextlib
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from typing import Any

import httpx

from timesafe.config.credentials import CredentialStore, KeyringCredentialStore
from timesafe.config.registry import VaultRef, VaultRegistry
from timesafe.errors import (
    AmbiguousNameError,
    NetworkError,
    NotFoundError,
    NotReadyError,
    TimesafeError,
    UsageError,
    VaultError,
)
from timesafe.github.client import GitHubClient
from timesafe.resolve import resolve_vault
from timesafe.timelock import tle
from timesafe.validation import is_valid_email, is_valid_repo, parse_duration
from timesafe.vault.secret import Secret
from timesafe.vault.vault import SECRETS_DIR, Vault, _workflow_path

"""The UI-free, importable time-safe API.

Every function here returns plain JSON-ready data and raises `timesafe.errors` exceptions. Nothing
prints, exits, or reads argv — `timesafe.cli` owns all of that. Callers who want to skip subprocess
entirely can use this module directly:

    from timesafe import api
    added = api.add(name="break-glass", duration="10d", secret=plaintext)
    later = api.reveal(secret_id=added["id"])
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


@contextlib.contextmanager
def _github_errors(what: str):
    """Translate transport failures into typed errors, without ever echoing a request body."""
    try:
        yield
    except TimesafeError:
        raise
    except httpx.HTTPStatusError as exc:
        raise VaultError(f"{what}: GitHub returned {exc.response.status_code}.") from exc
    except httpx.HTTPError as exc:
        raise NetworkError(f"{what}: {type(exc).__name__}.") from exc


def _vault_for(vault: Vault | None, selector: str | None) -> Vault:
    return vault if vault is not None else resolve_vault(selector)


def _as_duration(duration: str | timedelta) -> timedelta:
    if isinstance(duration, timedelta):
        if duration.total_seconds() <= 0:
            raise UsageError("Duration must be positive.")
        return duration
    try:
        return parse_duration(duration)
    except ValueError as exc:
        raise UsageError(str(exc)) from None


def _find(secrets: Iterable[Secret], secret_id: str | None, name: str | None) -> Secret:
    """Resolve a secret by id, or by name when that name is unambiguous.

    Names are not unique — nothing in the vault enforces it, and the TUI will happily create two
    secrets with the same label — so a duplicate name is an error, never a silent pick.
    """
    secrets = list(secrets)
    if secret_id:
        for s in secrets:
            if s.id == secret_id:
                return s
        raise NotFoundError(f"No secret with id {secret_id}.")
    if name:
        matches = [s for s in secrets if s.name == name]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise NotFoundError(f"No secret named {name!r}.")
        raise AmbiguousNameError(
            f"{len(matches)} secrets are named {name!r}; look them up by id instead.",
            ids=sorted(s.id for s in matches),
        )
    raise UsageError("Specify a secret with --id (preferred) or --name.")


def _seconds_remaining(secret: Secret, now: datetime | None = None) -> int:
    delta = (secret.unlock_at - (now or _now())).total_seconds()
    return max(0, int(delta))


# ── add ──────────────────────────────────────────────────────────────────────
def add(
    *,
    name: str,
    duration: str | timedelta,
    secret: str,
    email: str | None = None,
    vault: Vault | None = None,
    selector: str | None = None,
) -> dict[str, Any]:
    """Timelock `secret` for `duration` and push it to the vault.

    Returns the authoritative id the vault will use for every later lookup. Callers must persist
    that id — it is not derivable from `name`.
    """
    if not name or not name.strip():
        raise UsageError("A secret needs a --name.")
    if not secret:
        raise UsageError("The secret is empty.")
    if email and not is_valid_email(email):
        raise UsageError(f"{email!r} is not a valid delivery email.")

    unlock_at = _now() + _as_duration(duration)
    v = _vault_for(vault, selector)

    with _github_errors("could not read the vault"):
        before = set(v.github.list_dir(SECRETS_DIR))

    try:
        created = v.put_secret(name.strip(), unlock_at, secret, email)
    except BaseException as exc:  # noqa: BLE001 — cleanup must run for anything, then re-raise
        cleaned = _clean_partial_write(v, before)
        if isinstance(exc, TimesafeError):
            raise
        raise VaultError(
            f"Failed to write the secret. {_describe_write_failure(exc)} Nothing was left behind.",
            cleaned=cleaned,
        ) from exc

    return {
        "id": created.id,
        "name": created.name,
        "unlock_at": created.unlock_at.astimezone(timezone.utc).isoformat(),
        "round": created.drand_round,
        "vault_path": f"{SECRETS_DIR}/{created.id}.tle",
        "pushed": True,
    }


def _describe_write_failure(exc: BaseException) -> str:
    """Explain a failed vault write without echoing anything sensitive.

    An HTTP status and a repo path carry no secret material, and they are the difference between a
    self-diagnosing error and one that sends an operator reading source code.
    """
    if not isinstance(exc, httpx.HTTPStatusError):
        return f"({type(exc).__name__})."

    status = exc.response.status_code
    path = exc.request.url.path.split("/contents/", 1)[-1]
    detail = f"GitHub returned {status} writing {path}."

    # An add with --email writes a per-secret delivery workflow, so a token with only `contents`
    # write fails here and nowhere else — an easy scope to miss, and the failure gives no hint on
    # its own.
    if status == 403 and path.startswith(".github/workflows/"):
        detail += (
            " Writing under .github/workflows/ needs the `workflow` scope on the token "
            "(fine-grained: Workflows → Read and write). Only --email needs it; adds without a "
            "delivery address write no workflow and work on a contents-only token."
        )
    return detail


def _clean_partial_write(vault: Vault, before: set[str]) -> list[str]:
    """Delete anything a failed `put_secret` managed to commit.

    A half-written secret is worse than none: `list_secrets` reads only `.meta`, so a stranded
    `.tle` is invisible, and the caller never learned its id. Best-effort — a cleanup failure must
    not mask the original error.
    """
    cleaned: list[str] = []
    try:
        orphans = sorted(set(vault.github.list_dir(SECRETS_DIR)) - before)
    except Exception:  # noqa: BLE001
        return cleaned

    for path in orphans:
        with contextlib.suppress(Exception):
            vault.github.delete_file(path, "cleanup: partial write")
            cleaned.append(path)

    for secret_id in {PurePosixPath(p).stem for p in orphans}:
        with contextlib.suppress(Exception):
            vault.github.delete_file(_workflow_path(secret_id), "cleanup: partial write")
    return cleaned


# ── status / list ────────────────────────────────────────────────────────────
def status(
    *,
    secret_id: str | None = None,
    name: str | None = None,
    vault: Vault | None = None,
    selector: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Readiness for one secret, or for every secret when no selector is given.

    `ready` is the scheduled answer — wall clock against the stored unlock time. `reveal` is the
    cryptographic one; near the boundary they can disagree by a drand round (~3s).
    """
    v = _vault_for(vault, selector)
    with _github_errors("could not list the vault"):
        secrets = v.list_secrets()

    if secret_id or name:
        return _status_row(_find(secrets, secret_id, name), now)
    return [_status_row(s, now) for s in secrets]


def _status_row(secret: Secret, now: datetime | None = None) -> dict[str, Any]:
    return {
        "id": secret.id,
        "name": secret.name,
        "unlock_at": secret.unlock_at.astimezone(timezone.utc).isoformat(),
        "ready": secret.is_ready(now),
        "seconds_remaining": _seconds_remaining(secret, now),
    }


def list_secrets(
    *,
    vault: Vault | None = None,
    selector: str | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Full metadata for every secret in the vault."""
    v = _vault_for(vault, selector)
    with _github_errors("could not list the vault"):
        secrets = v.list_secrets()
    return [
        {
            "id": s.id,
            "name": s.name,
            "unlock_at": s.unlock_at.astimezone(timezone.utc).isoformat(),
            "created_at": s.created_at.astimezone(timezone.utc).isoformat(),
            "round": s.drand_round,
            "chain": s.drand_chain,
            "delivery_email": s.delivery_email,
            "ready": s.is_ready(now),
        }
        for s in secrets
    ]


# ── reveal ───────────────────────────────────────────────────────────────────
def reveal(
    *,
    secret_id: str | None = None,
    name: str | None = None,
    vault: Vault | None = None,
    selector: str | None = None,
    now: datetime | None = None,
) -> str:
    """Decrypt a secret locally and return its plaintext.

    Raises NotReadyError (exit 3) from two independent gates: the metadata pre-check, which avoids
    fetching the ciphertext at all, and tlock's own refusal, which catches clock skew.
    """
    v = _vault_for(vault, selector)
    with _github_errors("could not list the vault"):
        secrets = v.list_secrets()
    secret = _find(secrets, secret_id, name)

    remaining = _seconds_remaining(secret, now)
    if not secret.is_ready(now):
        raise NotReadyError(
            f"{secret.name} unlocks at {secret.unlock_at.astimezone(timezone.utc).isoformat()}.",
            id=secret.id,
            seconds_remaining=remaining,
        )

    try:
        with _github_errors("could not read the ciphertext"):
            return v.reveal(secret)
    except tle.NotYetUnlocked as exc:
        raise NotReadyError(
            "The drand round for this secret has not been published yet.",
            id=secret.id,
            seconds_remaining=remaining,
        ) from exc
    except tle.TleError as exc:
        raise VaultError(f"Decryption failed: {exc}") from exc
    except FileNotFoundError as exc:
        raise VaultError(f"Ciphertext missing for {secret.id}.") from exc


# ── init ─────────────────────────────────────────────────────────────────────
def init(
    *,
    repo: str,
    name: str,
    token: str,
    create: bool = False,
    github: Any = None,
    registry: VaultRegistry | None = None,
    credentials: CredentialStore | None = None,
) -> dict[str, Any]:
    """Create and/or initialize a vault repo, and register it locally.

    Idempotent by design — unlike the TUI's Initialize screen, which errors on an already-set-up
    vault. A provisioning script must be safe to re-run, and pointing this at an existing vault is
    also how a second machine registers one (the TUI's "connect").
    """
    if not is_valid_repo(repo):
        raise UsageError(f"{repo!r} must be owner/repo — init cannot take a registry name.")
    if not token:
        raise UsageError("No token supplied. Set TIMESAFE_GITHUB_TOKEN or pass --token-stdin.")

    client = github if github is not None else GitHubClient(repo, token)
    registry = VaultRegistry.load() if registry is None else registry
    credentials = KeyringCredentialStore() if credentials is None else credentials

    created = False
    with _github_errors("could not reach the repo"):
        if not client.repo_exists():
            if not create:
                raise VaultError(
                    f"{repo} does not exist. Pass --create to make it, or create it yourself first."
                )
            client.create_repo()
            created = True

    vault = Vault(client)
    initialized = False
    with _github_errors("could not initialize the vault"):
        if not vault.is_initialized():
            vault.init(_now().isoformat())
            initialized = True

    registered = False
    if not registry.reload().contains(repo):
        registry.add(VaultRef(name, repo))
        registry.save()
        registered = True

    token_saved = True
    try:
        credentials.put(repo, token)
    except Exception:  # noqa: BLE001 — headless boxes have no keychain; env vars still work
        token_saved = False

    return {
        "repo": repo,
        "created": created,
        "initialized": initialized,
        "registered": registered,
        "token_saved": token_saved,
    }


__all__ = ["add", "status", "list_secrets", "reveal", "init"]
