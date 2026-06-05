from __future__ import annotations

import asyncio

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label

from timesafe.config.registry import VaultRef
from timesafe.github.client import GitHubClient
from timesafe.screens.init_vault import describe_github_error, is_valid_repo
from timesafe.vault.vault import Vault


class ConnectVaultScreen(Screen):
    """Connect to an already-initialized vault (requires the sentinel to exist)."""

    BINDINGS = [("escape", "app.pop_screen", "back")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Label("Connect to existing vault", classes="title")
            yield Label("GitHub repo (owner/repo)")
            yield Input(id="repo")
            yield Label("GitHub token")
            yield Input(password=True, id="token")
            yield Label("", id="error")
            yield Button("Connect", id="connect", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "connect":
            self._connect()

    def _connect(self) -> None:
        repo = self.query_one("#repo", Input).value.strip()
        token = self.query_one("#token", Input).value.strip()
        error = self.query_one("#error", Label)
        if not (repo and token):
            error.update("All fields are required.")
            return
        if not is_valid_repo(repo):
            error.update("Repo must be owner/repo (one slash, no spaces).")
            return
        if self.app.registry.contains(repo):  # type: ignore[attr-defined]
            error.update("This vault is already in your list.")
            return
        self._do_connect(repo, token)

    @work
    async def _do_connect(self, repo, token) -> None:
        error = self.query_one("#error", Label)

        def blocking() -> None:
            vault = Vault(GitHubClient(repo, token))
            if not vault.is_initialized():
                raise RuntimeError(
                    "This vault has not been initialized. Use 'Initialize new vault'."
                )

        try:
            await asyncio.to_thread(blocking)
        except RuntimeError as exc:
            error.update(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            error.update(describe_github_error(exc))
            return

        name = repo.split("/")[1]
        self.app.credentials.put(repo, token)  # type: ignore[attr-defined]
        self.app.registry.add(VaultRef(name, repo))  # type: ignore[attr-defined]
        self.app.registry.save()  # type: ignore[attr-defined]
        self.app.pop_screen()
