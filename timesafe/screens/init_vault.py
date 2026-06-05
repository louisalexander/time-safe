from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label

from timesafe.screens.gmail_link import GmailLinkScreen
from timesafe.vault.vault import Vault

_REPO_RE = re.compile(r"^[^/\s]+/[^/\s]+$")


def is_valid_repo(repo: str | None) -> bool:
    return bool(repo) and _REPO_RE.match(repo) is not None


def describe_github_error(exc: Exception) -> str:
    msg = str(exc)
    if "404" in msg:
        return "GitHub 404 — repo not found or token lacks 'repo' scope."
    if "403" in msg:
        return "GitHub 403 — token lacks required scope ('repo' + 'workflow')."
    return f"Failed: {msg}"


class InitVaultScreen(Screen):
    """One-time initialize: name + repo + token, then flow into Gmail linking."""

    BINDINGS = [("escape", "app.pop_screen", "back")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Label("Initialize new vault", classes="title")
            yield Label("Vault name")
            yield Input(id="name")
            yield Label("GitHub repo (owner/repo)")
            yield Input(id="repo")
            yield Label("GitHub token")
            yield Input(password=True, id="token")
            yield Label("", id="error")
            yield Button("Create", id="create", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "create":
            self._create()

    def _create(self) -> None:
        name = self.query_one("#name", Input).value.strip()
        repo = self.query_one("#repo", Input).value.strip()
        token = self.query_one("#token", Input).value.strip()
        error = self.query_one("#error", Label)
        if not (name and repo and token):
            error.update("All fields are required.")
            return
        if not is_valid_repo(repo):
            error.update("Repo must be owner/repo (one slash, no spaces).")
            return
        self._do_init(name, repo, token)

    @work
    async def _do_init(self, name, repo, token) -> None:
        error = self.query_one("#error", Label)

        def blocking() -> Vault:
            vault = self.app.make_vault(repo, token)  # type: ignore[attr-defined]
            if vault.is_initialized():
                raise RuntimeError(
                    "This vault is already initialized. Use 'Connect to existing vault'."
                )
            vault.init(datetime.now(timezone.utc).isoformat())
            return vault

        try:
            vault = await asyncio.to_thread(blocking)
        except RuntimeError as exc:
            error.update(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            error.update(describe_github_error(exc))
            return

        try:
            self.app.register_vault(name, repo, token)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            error.update(f"Vault created on GitHub, but saving it locally failed: {exc}")
            return
        self.notify(f"Vault {repo} created and saved")
        self.app.pop_screen()
        self.app.push_screen(GmailLinkScreen(vault, after_init=True))
