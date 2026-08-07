from __future__ import annotations

import os
from collections.abc import Mapping

from timesafe.config.credentials import CredentialStore, KeyringCredentialStore
from timesafe.config.registry import VaultRegistry
from timesafe.errors import UsageError, VaultError
from timesafe.github.client import GitHubClient
from timesafe.validation import is_valid_repo
from timesafe.vault.vault import Vault

"""Headless vault + credential resolution.

Nothing here may prompt, block, or require a TTY — this is the path a cron job takes.
"""

VAULT_ENV = "TIMESAFE_VAULT"
TOKEN_ENV = "TIMESAFE_GITHUB_TOKEN"


def resolve_repo(
    selector: str | None,
    registry: VaultRegistry,
    env: Mapping[str, str],
) -> str:
    """Pick the vault repo: explicit selector, then $TIMESAFE_VAULT, then a lone registered vault.

    Two or more registered vaults with no selector is an error listing the candidates — never a
    guess, so a script can't silently start writing to a different vault because one was added.
    """
    choice = selector or env.get(VAULT_ENV) or ""
    choice = choice.strip()

    if choice:
        if "/" in choice:
            if not is_valid_repo(choice):
                raise UsageError(f"'{choice}' is not a valid owner/repo.")
            return choice
        for ref in registry.vaults:
            if ref.name == choice:
                return ref.repo
        raise UsageError(
            f"No vault named '{choice}'. Use owner/repo, or one of: "
            f"{', '.join(v.name for v in registry.vaults) or '(none registered)'}.",
            vaults=[v.name for v in registry.vaults],
        )

    vaults = registry.vaults
    if len(vaults) == 1:
        return vaults[0].repo
    if not vaults:
        raise UsageError(
            f"No vault specified and none registered. Pass --vault owner/repo or set {VAULT_ENV}."
        )
    raise UsageError(
        f"Multiple vaults registered; pass --vault or set {VAULT_ENV}.",
        vaults=[v.name for v in vaults],
    )


def resolve_token(repo: str, credentials: CredentialStore, env: Mapping[str, str]) -> str:
    """Find the PAT for `repo`: environment first, then the OS keychain.

    Environment-first is what makes cron and systemd work — a headless session has no unlocked
    keychain, and `keyring` may raise there rather than returning None.
    """
    token = (env.get(TOKEN_ENV) or "").strip()
    if token:
        return token

    try:
        stored = credentials.get(repo)
    except Exception:  # noqa: BLE001 — any keyring backend failure means "no token here"
        stored = None
    if stored:
        return stored

    raise VaultError(
        f"No GitHub token for {repo}. Set {TOKEN_ENV}, or add the vault in the TUI so the token is "
        "stored in your keychain."
    )


def resolve_vault(
    selector: str | None = None,
    *,
    registry: VaultRegistry | None = None,
    credentials: CredentialStore | None = None,
    env: Mapping[str, str] | None = None,
) -> Vault:
    """Build a ready-to-use Vault from the ambient configuration."""
    env = os.environ if env is None else env
    registry = VaultRegistry.load() if registry is None else registry
    credentials = KeyringCredentialStore() if credentials is None else credentials

    repo = resolve_repo(selector, registry, env)
    token = resolve_token(repo, credentials, env)
    return Vault(GitHubClient(repo, token))
