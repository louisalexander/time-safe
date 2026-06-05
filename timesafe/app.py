from __future__ import annotations

from textual.app import App

from timesafe.config.credentials import CredentialStore, KeyringCredentialStore
from timesafe.config.registry import VaultRef, VaultRegistry
from timesafe.screens.vault_picker import VaultPickerScreen


class TimeSafeApp(App):
    """Textual application root: holds the registry + credential store, drives the screen stack."""

    TITLE = "time-safe"

    def __init__(
        self,
        registry: VaultRegistry | None = None,
        credentials: CredentialStore | None = None,
    ) -> None:
        super().__init__()
        self.registry = registry if registry is not None else VaultRegistry.load()
        self.credentials = credentials if credentials is not None else KeyringCredentialStore()

    def on_mount(self) -> None:
        self.push_screen(VaultPickerScreen(self.registry.vaults))

    def open_vault(self, ref: VaultRef) -> None:
        """Open a vault. Plan 2 replaces this with a secrets-list screen + in-memory load."""
        token = self.credentials.get(ref.repo)
        if token is None:
            self.notify(f"No stored token for {ref.repo}", severity="error")
            return
        self.notify(f"Opened {ref.repo}")  # placeholder until Plan 2
