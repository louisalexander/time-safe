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
from timesafe.github import retry
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


NO_SELECTOR = "Specify a secret with --id (preferred) or --name."


def _find_by_name(secrets: Iterable[Secret], name: str) -> Secret:
    """Resolve a secret by name, when that name is unambiguous.

    Names are not unique — nothing in the vault enforces it, and the TUI will happily create two
    secrets with the same label — so a duplicate name is an error, never a silent pick.
    """
    matches = [s for s in secrets if s.name == name]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise NotFoundError(f"No secret named {name!r}.")
    raise AmbiguousNameError(
        f"{len(matches)} secrets are named {name!r}; look them up by id instead.",
        ids=sorted(s.id for s in matches),
    )


def _lookup(vault: Vault, secret_id: str | None, name: str | None) -> Secret:
    """Fetch one secret, scanning the vault only when the lookup genuinely needs it.

    An id is the path to its own `.meta`, so it costs a constant two requests. A name is not — it
    can only be resolved by reading every `.meta`, at a request per secret. That difference decides
    whether a per-minute cron poll fits inside the 5000/hr rate limit, so the two paths stay apart.
    """
    if not secret_id and not name:
        raise UsageError(NO_SELECTOR)

    if secret_id:
        with _github_errors("could not read the secret"):
            found = vault.get_secret(secret_id)
        if found is None:
            raise NotFoundError(f"No secret with id {secret_id}.")
        return found

    with _github_errors("could not list the vault"):
        return _find_by_name(vault.list_secrets(), name)


def _seconds_remaining(secret: Secret, now: datetime | None = None) -> int:
    delta = (secret.unlock_at - (now or _now())).total_seconds()
    return max(0, int(delta))


def _ready_secret(
    v: Vault, *, secret_id: str | None, name: str | None, now: datetime | None
) -> Secret:
    """Find a secret, refusing it if its unlock time has not passed.

    Shared by reveal and renew: both need the plaintext, so both fail identically — one exit code,
    one `code` string — when the ciphertext still cannot be read. Goes through `_lookup`, so
    `renew --id` inherits the same constant-cost fetch `reveal --id` gets.
    """
    secret = _lookup(v, secret_id, name)

    if not secret.is_ready(now):
        raise NotReadyError(
            f"{secret.name} unlocks at {secret.unlock_at.astimezone(timezone.utc).isoformat()}.",
            id=secret.id,
            seconds_remaining=_seconds_remaining(secret, now),
        )
    return secret


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
    if secret_id or name:
        return _status_row(_lookup(v, secret_id, name), now)

    with _github_errors("could not list the vault"):
        return [_status_row(s, now) for s in v.list_secrets()]


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
    secret = _ready_secret(v, secret_id=secret_id, name=name, now=now)
    remaining = _seconds_remaining(secret, now)

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


# ── delete ───────────────────────────────────────────────────────────────────
def delete(
    *,
    secret_id: str | None = None,
    name: str | None = None,
    vault: Vault | None = None,
    selector: str | None = None,
) -> dict[str, Any]:
    """Remove a secret's ciphertext, metadata and workflow. Irreversible.

    A selector is always required — the TUI deletes one row at a time, and there is deliberately no
    way to spell "everything", so a missing `--id` can never empty a vault.
    """
    v = _vault_for(vault, selector)
    secret = _lookup(v, secret_id, name)

    with _github_errors("could not delete the secret"):
        v.delete(secret)

    return {"id": secret.id, "name": secret.name, "deleted": True}


# ── renew ────────────────────────────────────────────────────────────────────
def renew(
    *,
    duration: str | timedelta,
    secret_id: str | None = None,
    name: str | None = None,
    vault: Vault | None = None,
    selector: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Re-lock an already-unlocked secret for a fresh duration.

    Only unlocked secrets can be renewed: renewing means decrypting and re-encrypting to a later
    round, and a still-locked ciphertext cannot be read. That is `reveal`'s exit-3 condition
    exactly, so it raises the same NotReadyError rather than inventing a second failure mode.
    """
    new_unlock_at = _now() + _as_duration(duration)
    v = _vault_for(vault, selector)
    secret = _ready_secret(v, secret_id=secret_id, name=name, now=now)

    try:
        with _github_errors("could not renew the secret"):
            renewed = v.renew(secret, new_unlock_at)
    except tle.NotYetUnlocked as exc:
        raise NotReadyError(
            "The drand round for this secret has not been published yet.",
            id=secret.id,
            seconds_remaining=_seconds_remaining(secret, now),
        ) from exc
    except tle.TleError as exc:
        raise VaultError(f"Decryption failed: {exc}") from exc
    except FileNotFoundError as exc:
        raise VaultError(f"Ciphertext missing for {secret.id}.") from exc

    return {
        "id": renewed.id,
        "name": renewed.name,
        "unlock_at": renewed.unlock_at.astimezone(timezone.utc).isoformat(),
        "round": renewed.drand_round,
        "renewed": True,
    }


# ── send ─────────────────────────────────────────────────────────────────────
def send(
    *,
    secret_id: str | None = None,
    name: str | None = None,
    vault: Vault | None = None,
    selector: str | None = None,
) -> dict[str, Any]:
    """Dispatch the secret's delivery workflow, which emails the plaintext once its round lands.

    Safe to call before the unlock time: the workflow's own tlock decrypt is the server-side gate,
    and exits without sending while the secret is still locked.
    """
    v = _vault_for(vault, selector)
    secret = _lookup(v, secret_id, name)

    if not secret.delivery_email:
        raise UsageError(
            f"{secret.name} has no delivery address, so there is nothing to send it to. "
            "Only a secret added with --email can be delivered."
        )

    # dispatch_email re-writes the workflow first, so this works even for a secret whose workflow
    # was never written or was removed.
    with _github_errors("could not dispatch the delivery workflow"):
        v.dispatch_email(secret)

    return {
        "id": secret.id,
        "name": secret.name,
        "delivery_email": secret.delivery_email,
        "dispatched": True,
    }


# ── gmail ────────────────────────────────────────────────────────────────────
GMAIL_SECRET_NAMES = ["GMAIL_ADDRESS", "OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET",
                      "GMAIL_REFRESH_TOKEN"]


def link_gmail(
    *,
    gmail_address: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    vault: Vault | None = None,
    selector: str | None = None,
) -> dict[str, Any]:
    """Seal an existing Gmail OAuth credential into the vault's Actions secrets.

    The browser consent that mints the refresh token stays interactive — Google will not issue
    `gmail.send` through the device flow — but it only has to happen once, on any machine. This is
    how that result gets onto a host with no browser and no TUI.
    """
    if not is_valid_email(gmail_address):
        raise UsageError(f"{gmail_address!r} is not a valid Gmail address.")
    for label, value in (
        ("client id", client_id),
        ("client secret", client_secret),
        ("refresh token", refresh_token),
    ):
        if not value or not value.strip():
            raise UsageError(f"The OAuth {label} is empty.")

    v = _vault_for(vault, selector)
    with _github_errors("could not store the Gmail credentials"):
        v.relink_gmail(gmail_address, client_id, client_secret, refresh_token)

    # Names only — the values are write-only from here on, and echoing them would put a live
    # refresh token in a provisioning log.
    return {"gmail_address": gmail_address, "secrets": list(GMAIL_SECRET_NAMES), "linked": True}


# ── init ─────────────────────────────────────────────────────────────────────
def init(
    *,
    repo: str,
    name: str,
    token: str,
    create: bool = False,
    retries: int = retry.ATTEMPTS,
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

    client = github if github is not None else GitHubClient(repo, token, retries=retries)
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


__all__ = [
    "add",
    "status",
    "list_secrets",
    "reveal",
    "delete",
    "renew",
    "send",
    "link_gmail",
    "init",
]
