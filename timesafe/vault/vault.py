from __future__ import annotations

from datetime import datetime

import httpx

from timesafe.github.client import GitHubClient
from timesafe.github.secrets_api import seal
from timesafe.timelock import drand, tle
from timesafe.vault.secret import Secret
from timesafe.vault.workflow import SEND_SECRET_SCRIPT, build_unlock_workflow_yaml

SECRETS_DIR = "vault/secrets"
SCRIPT_PATH = "vault/scripts/send_secret.py"
SENTINEL = ".timesafe/initialized"


def _workflow_path(secret_id: str) -> str:
    return f".github/workflows/unlock-{secret_id}.yml"


class Vault:
    """Orchestrates a single vault repo: timelock-encrypt + push, list, reveal, delete, deliver."""

    def __init__(self, github: GitHubClient, *, http: httpx.Client | None = None) -> None:
        self.github = github
        self._http = http or httpx.Client(timeout=30)

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def is_initialized(self) -> bool:
        return self.github.get_file(SENTINEL) is not None

    def write_sentinel(self, iso_timestamp: str) -> None:
        body = ('{"initialized_at": "%s"}' % iso_timestamp).encode()
        self.github.put_file(SENTINEL, body, "chore: mark vault initialized")

    def init(self, iso_timestamp: str) -> None:
        self.github.put_file(SCRIPT_PATH, SEND_SECRET_SCRIPT.encode(), "chore: add delivery script")
        self.write_sentinel(iso_timestamp)

    # ── secrets ───────────────────────────────────────────────────────────────
    def put_secret(
        self,
        name: str,
        unlock_at: datetime,
        plaintext: str,
        delivery_email: str | None = None,
    ) -> Secret:
        info = drand.fetch_info(self._http)
        drand_round = drand.round_at(info, unlock_at)
        ciphertext = tle.encrypt(plaintext.encode(), drand_round)
        secret = Secret.create(name, unlock_at, drand_round, info.chain_hash, delivery_email)
        self.github.put_file(f"{SECRETS_DIR}/{secret.id}.tle", ciphertext, f"lock: add {name}")
        self.github.put_file(
            f"{SECRETS_DIR}/{secret.id}.meta", secret.to_meta_json().encode(), f"lock: meta {name}"
        )
        self.github.put_file(
            _workflow_path(secret.id),
            build_unlock_workflow_yaml(secret).encode(),
            f"lock: workflow {name}",
        )
        return secret

    def list_secrets(self) -> list[Secret]:
        secrets: list[Secret] = []
        for path in self.github.list_dir(SECRETS_DIR):
            if path.endswith(".meta"):
                content = self.github.get_file(path)
                if content is not None:
                    secrets.append(Secret.from_meta_json(content))
        return secrets

    def reveal(self, secret: Secret) -> str:
        """Decrypt the secret locally via tlock. Raises tle.NotYetUnlocked before the unlock round."""
        ciphertext = self.github.get_file(f"{SECRETS_DIR}/{secret.id}.tle")
        if ciphertext is None:
            raise FileNotFoundError(f"ciphertext missing for {secret.id}")
        return tle.decrypt(ciphertext).decode()

    def renew(self, secret: Secret, new_unlock_at: datetime) -> Secret:
        """Re-lock a *ready* secret for a new duration: decrypt now, re-encrypt to a new round.

        Only possible once a secret is unlocked — a still-locked tlock ciphertext can't be re-timed
        because it can't be read. Mutates and returns the secret with its new unlock time/round.
        """
        plaintext = self.reveal(secret)  # raises tle.NotYetUnlocked if still locked
        info = drand.fetch_info(self._http)
        new_round = drand.round_at(info, new_unlock_at)
        ciphertext = tle.encrypt(plaintext.encode(), new_round)
        secret.unlock_at = new_unlock_at
        secret.drand_round = new_round
        secret.drand_chain = info.chain_hash
        self.github.put_file(f"{SECRETS_DIR}/{secret.id}.tle", ciphertext, f"renew: {secret.name}")
        self.github.put_file(
            f"{SECRETS_DIR}/{secret.id}.meta",
            secret.to_meta_json().encode(),
            f"renew: meta {secret.name}",
        )
        self.github.put_file(
            _workflow_path(secret.id),
            build_unlock_workflow_yaml(secret).encode(),
            f"renew: workflow {secret.name}",
        )
        return secret

    def delete(self, secret: Secret) -> None:
        self.github.delete_file(f"{SECRETS_DIR}/{secret.id}.tle", f"delete {secret.name}")
        self.github.delete_file(f"{SECRETS_DIR}/{secret.id}.meta", f"delete {secret.name}")
        self.github.delete_file(_workflow_path(secret.id), f"delete {secret.name}")

    def dispatch_email(self, secret: Secret) -> None:
        """Trigger the workflow that decrypts at T and emails the plaintext to the secret's address."""
        self.github.put_file(
            _workflow_path(secret.id),
            build_unlock_workflow_yaml(secret).encode(),
            "ensure unlock workflow",
        )
        ref = self.github.default_branch()
        self.github.dispatch_workflow(f"unlock-{secret.id}.yml", ref)

    # ── gmail oauth ───────────────────────────────────────────────────────────
    def relink_gmail(
        self, gmail_address: str, client_id: str, client_secret: str, refresh_token: str
    ) -> None:
        key_id, public_key = self.github.actions_public_key()
        for name, value in (
            ("GMAIL_ADDRESS", gmail_address),
            ("OAUTH_CLIENT_ID", client_id),
            ("OAUTH_CLIENT_SECRET", client_secret),
            ("GMAIL_REFRESH_TOKEN", refresh_token),
        ):
            self.github.put_actions_secret(name, seal(public_key, value), key_id)
        self.github.put_file(SCRIPT_PATH, SEND_SECRET_SCRIPT.encode(), "chore: refresh delivery script")
