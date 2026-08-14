from __future__ import annotations

import asyncio

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label

from timesafe import api
from timesafe.errors import TimesafeError
from timesafe.screens.errors import message_of
from timesafe.validation import parse_duration


class RenewScreen(Screen):
    """Re-lock a ready secret for a new duration (decrypt now → re-encrypt to a new round)."""

    BINDINGS = [("escape", "app.pop_screen", "back")]

    def __init__(self, vault, secret) -> None:
        super().__init__()
        self.vault = vault
        self.secret = secret

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Label(f"Renew lock — {self.secret.name}", classes="title")
            yield Label("New duration  (e.g. 30m, 2h, 7d, 1d12h)")
            yield Input(value="7d", id="duration")
            yield Label("", id="error")
            yield Button("Renew", id="renew", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "renew":
            self._renew()

    def _renew(self) -> None:
        error = self.query_one("#error", Label)
        raw = self.query_one("#duration", Input).value
        try:
            duration = parse_duration(raw)
        except ValueError as exc:
            error.update(str(exc))
            return
        from timesafe.screens.confirm import ConfirmScreen

        def after(confirmed: bool | None) -> None:
            if confirmed:
                self._do_renew(duration)

        self.app.push_screen(
            ConfirmScreen(
                f"Re-lock “{self.secret.name}” for {raw.strip()}? "
                "You won't be able to read it until then.",
                "Renew",
            ),
            after,
        )

    @work
    async def _do_renew(self, duration) -> None:
        error = self.query_one("#error", Label)
        try:
            await asyncio.to_thread(
                api.renew, vault=self.vault, secret=self.secret, duration=duration
            )
        except TimesafeError as exc:
            error.update(message_of(exc))
            return
        self.notify(f"Re-locked {self.secret.name}")
        self.app.pop_screen()  # remove this renew screen -> back to the detail
        self.app.pop_screen()  # remove the (now stale) detail -> secrets list reloads on resume
