from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label

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
        text = self.query_one("#text", Input).value.strip()
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
        unlock_at = datetime.now(timezone.utc) + duration
        self._do_save(name, unlock_at, text, email or None)

    @work
    async def _do_save(self, name, unlock_at, text, email) -> None:
        error = self.query_one("#error", Label)
        try:
            await asyncio.to_thread(self.vault.put_secret, name, unlock_at, text, email)
        except Exception as exc:  # noqa: BLE001
            error.update(f"Failed: {exc}")
            return
        self.notify(f"Locked {name}")
        if self._on_done:
            self._on_done()
        self.app.pop_screen()
