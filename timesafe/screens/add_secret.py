from __future__ import annotations

import asyncio
from collections.abc import Callable

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label

from timesafe import api
from timesafe.errors import TimesafeError
from timesafe.screens.errors import message_of
from timesafe.validation import is_valid_email, parse_duration

__all__ = ["AddSecretScreen", "is_valid_email", "parse_duration"]


class AddSecretScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "back")]

    def __init__(self, vault, on_done: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.vault = vault
        self._on_done = on_done

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Label("Add secret", classes="title")
            yield Label("Name")
            yield Input(id="name")
            yield Label("Unlock in  (e.g. 30m, 2h, 7d, 1d12h)")
            yield Input(value="7d", id="duration")
            yield Label("Delivery email (optional)")
            yield Input(id="email")
            yield Label("Secret text")
            yield Input(password=True, id="text")
            yield Label("", id="error")
            yield Button("Save", id="save", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save()

    def _save(self) -> None:
        name = self.query_one("#name", Input).value.strip()
        duration_raw = self.query_one("#duration", Input).value.strip()
        email = self.query_one("#email", Input).value.strip()
        # Deliberately not stripped: a secret is the bytes the user chose, and `timesafe reveal` must
        # hand back exactly what was typed here — indented blocks, padded base64, deliberate spaces.
        text = self.query_one("#text", Input).value
        error = self.query_one("#error", Label)
        if not name or not text:
            error.update("Name and secret text are required.")
            return
        try:
            duration = parse_duration(duration_raw)
        except ValueError as exc:
            error.update(str(exc))
            return
        if email and not is_valid_email(email):
            error.update("Delivery email is not valid.")
            return
        self._do_save(name, duration, text, email or None)

    @work
    async def _do_save(self, name, duration, text, email) -> None:
        error = self.query_one("#error", Label)
        try:
            added = await asyncio.to_thread(
                api.add, name=name, duration=duration, secret=text, email=email, vault=self.vault
            )
        except TimesafeError as exc:
            # api.add has already cleaned up whatever the failed write committed, and says so.
            error.update(message_of(exc))
            return
        # The id is the vault's identity for this secret and is not derivable from the name, so this
        # is the one moment it is worth showing — it is what `timesafe reveal --id` wants.
        self.notify(f"Locked {name}\nid {added['id']}", timeout=10)
        if self._on_done:
            self._on_done()
        self.app.pop_screen()
