from __future__ import annotations

import os
import traceback
from pathlib import Path

from rich.text import Text
from textual.app import App

from timesafe.config.credentials import CredentialStore, KeyringCredentialStore
from timesafe.config.registry import VaultRef, VaultRegistry
from timesafe.github.client import GitHubClient
from timesafe.resolve import resolve_token
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

    # ── crash handling ────────────────────────────────────────────────────────
    def _handle_exception(self, error: Exception) -> None:
        """Exit on an unhandled exception without ever rendering a frame.

        Textual's default renders a rich traceback with `show_locals=True`, and on the add, renew and
        reveal paths the plaintext is a live local in several frames — from there it goes to
        scrollback, `script` logs, tmux buffers and CI output. This is the same rule the CLI keeps
        (`cli.main`), including printing `format_exception_only` rather than a traceback under
        TIMESAFE_DEBUG: deliberately no frames, so no locals.

        Overriding here rather than `_fatal_error` covers both of Textual's rendering paths — an
        exception defining `__rich__` is routed to `panic()`, which renders whatever it returns.
        """
        self._return_code = 1
        # run_test() re-raises this, so a test failure still names the real exception.
        if self._exception is None:
            self._exception = error
            self._exception_event.set()

        self.bell()
        message = "time-safe hit an internal error and exited. No traceback: it would show your secret."
        if os.environ.get("TIMESAFE_DEBUG") == "1":
            message += "\n" + "".join(traceback.format_exception_only(type(error), error)).rstrip()
        self._exit_renderables.append(Text(message))
        self._close_messages_no_wait()

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
        """Persist a vault: reload+merge (resilient to other instances), save, then keychain."""
        self.registry.reload()  # pick up anything another instance wrote
        self.registry.add(VaultRef(name, repo))
        self.registry.save()
        self.credentials.put(repo, token)
