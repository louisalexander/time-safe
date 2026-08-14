from __future__ import annotations

import asyncio
from typing import Any

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label

from timesafe import api
from timesafe.errors import TimesafeError
from timesafe.screens.errors import message_of
from timesafe.screens.gmail_link import GmailLinkScreen
from timesafe.validation import is_valid_repo

__all__ = ["AddVaultScreen", "is_valid_repo"]


class AddVaultScreen(Screen):
    """Add a vault: create and/or initialize the repo on GitHub, then register it locally.

    One screen where there were two. Whether the repo exists and whether it is already initialized
    are facts the app can check for itself, so asking the user to know them before typing anything —
    and bouncing them back to the picker when they guessed wrong — was never necessary. `api.init` is
    idempotent for the same reason a provisioning script must be safe to re-run.
    """

    BINDINGS = [("escape", "app.pop_screen", "back")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Label("Add vault", classes="title")
            yield Label("Vault name")
            yield Input(id="name")
            yield Label("GitHub repo (owner/repo)")
            yield Input(id="repo")
            yield Label("GitHub token")
            yield Input(password=True, id="token")
            yield Checkbox("Create the repo if it doesn't exist", id="create")
            yield Label("", id="error")
            yield Button("Add", id="add", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add":
            self._add()

    def _add(self) -> None:
        name = self.query_one("#name", Input).value.strip()
        repo = self.query_one("#repo", Input).value.strip()
        token = self.query_one("#token", Input).value.strip()
        create = self.query_one("#create", Checkbox).value
        error = self.query_one("#error", Label)
        if not (name and repo and token):
            error.update("All fields are required.")
            return
        if not is_valid_repo(repo):
            error.update("Repo must be owner/repo (one slash, no spaces).")
            return
        self._do_add(name, repo, token, create)

    @work
    async def _do_add(self, name: str, repo: str, token: str, create: bool) -> None:
        error = self.query_one("#error", Label)
        try:
            result = await asyncio.to_thread(
                api.init,
                repo=repo,
                name=name,
                token=token,
                create=create,
                github=self.app.make_github(repo, token),  # type: ignore[attr-defined]
                registry=self.app.registry,  # type: ignore[attr-defined]
                credentials=self.app.credentials,  # type: ignore[attr-defined]
            )
        except TimesafeError as exc:
            # api.init's wording points at the CLI's --create; this screen has a checkbox instead.
            if exc.extra.get("repo_missing"):
                error.update(f"{repo} does not exist on GitHub. Tick the box above to create it.")
            else:
                error.update(message_of(exc))
            return

        self.notify(_summary(repo, result))
        if not result["token_saved"]:
            # Not a failure: the repo-side work is done and the registry entry written. Only the
            # keychain refused, and TIMESAFE_GITHUB_TOKEN opens the vault without it.
            self.notify(
                "The token could not be saved to your keychain — set TIMESAFE_GITHUB_TOKEN to use "
                "this vault.",
                severity="warning",
                timeout=10,
            )

        self.app.pop_screen()
        if result["initialized"]:
            # A brand-new vault cannot deliver email until Gmail is linked once.
            vault = self.app.make_vault(repo, token)  # type: ignore[attr-defined]
            self.app.push_screen(GmailLinkScreen(vault, after_init=True))


def _summary(repo: str, result: dict[str, Any]) -> str:
    """Report what actually happened, from the returned flags rather than from which screen was used."""
    did = [
        word
        for flag, word in (
            ("created", "created"),
            ("initialized", "initialized"),
            ("registered", "added to your list"),
        )
        if result[flag]
    ]
    return f"{repo} — {' · '.join(did)}" if did else f"{repo} was already set up."
