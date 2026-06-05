from __future__ import annotations

import asyncio
from collections.abc import Callable

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label

from timesafe.oauth import loopback_flow


class GmailLinkScreen(Screen):
    """Device-flow Gmail linking: enter address + your OAuth client id/secret, authorize, store."""

    BINDINGS = [("escape", "app.pop_screen", "back")]

    def __init__(self, vault, after_init: bool = False, on_done: Callable[[], None] | None = None):
        super().__init__()
        self.vault = vault
        self._after_init = after_init
        self._on_done = on_done

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Label("Link Gmail (opens your browser)", classes="title")
            yield Label("Vault Gmail address")
            yield Input(id="gmail")
            yield Label("OAuth client id")
            yield Input(id="client_id")
            yield Label("OAuth client secret")
            yield Input(password=True, id="client_secret")
            yield Label("", id="status")
            yield Button("Link", id="link", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "link":
            gmail = self.query_one("#gmail", Input).value.strip()
            cid = self.query_one("#client_id", Input).value.strip()
            csec = self.query_one("#client_secret", Input).value.strip()
            status = self.query_one("#status", Label)
            if not (gmail and cid and csec):
                status.update("All fields are required.")
                return
            self._do_link(gmail, cid, csec)

    @work
    async def _do_link(self, gmail, client_id, client_secret) -> None:
        status = self.query_one("#status", Label)
        status.update("Opening your browser to authorize…")

        def on_prompt(url: str) -> None:
            self.app.call_from_thread(
                status.update, f"Authorize in your browser. If it didn't open, visit:\n{url}"
            )

        def blocking():
            refresh_token = loopback_flow.run(client_id, client_secret, on_prompt)
            self.vault.relink_gmail(gmail, client_id, client_secret, refresh_token)

        try:
            await asyncio.to_thread(blocking)
        except Exception as exc:  # noqa: BLE001
            status.update(f"Failed: {exc}")
            return
        self.notify("Gmail linked" if not self._after_init else "Vault initialized and Gmail linked")
        if self._on_done:
            self._on_done()
        self.app.pop_screen()
