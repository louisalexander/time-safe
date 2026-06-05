from __future__ import annotations

from pathlib import Path

from textual.app import App

from timesafe.config.credentials import CredentialStore, KeyringCredentialStore
from timesafe.config.registry import VaultRef, VaultRegistry
from timesafe.github.client import GitHubClient
from timesafe.screens.secrets_list import SecretsListScreen
from timesafe.screens.vault_picker import VaultPickerScreen
from timesafe.vault.vault import Vault


class TimeSafeApp(App):
    """Textual application root: holds the registry + credential store, drives the screen stack."""

    TITLE = "time-safe"
    CSS_PATH = Path(__file__).with_name("app.tcss")

    def __init__(
        self,
        registry: VaultRegistry | None = None,
        credentials: CredentialStore | None = None,
    ) -> None:
        super().__init__()
        self.registry = registry if registry is not None else VaultRegistry.load()
        self.credentials = credentials if credentials is not None else KeyringCredentialStore()

    def on_mount(self) -> None:
        self.push_screen(VaultPickerScreen())

    def open_vault(self, ref: VaultRef) -> None:
        token = self.credentials.get(ref.repo)
        if token is None:
            self.notify(f"No stored token for {ref.repo} — re-add the vault.", severity="error")
            return
        self.push_screen(SecretsListScreen(self.make_vault(ref.repo, token), ref))

    def make_vault(self, repo: str, token: str) -> Vault:
        """Build a Vault for a repo+token. Overridable in tests to inject a fake."""
        return Vault(GitHubClient(repo, token))

    def register_vault(self, name: str, repo: str, token: str) -> None:
        """Persist a vault: registry FIRST (durable on disk), then the token in the keychain."""
        self.registry.add(VaultRef(name, repo))
        self.registry.save()
        self.credentials.put(repo, token)
