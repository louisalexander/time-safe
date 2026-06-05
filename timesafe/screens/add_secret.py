from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, TextArea


def is_valid_email(raw: str | None) -> bool:
    if not raw:
        return False
    s = raw.strip()
    if not s or any(c.isspace() for c in s) or s.count("@") != 1:
        return False
    local, _, domain = s.partition("@")
    if not local or "." not in domain:
        return False
    return all(label for label in domain.split("."))


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
            yield Label("Unlock in (days)")
            yield Input(value="30", id="days")
            yield Label("Delivery email (optional)")
            yield Input(id="email")
            yield Label("Secret text")
            yield TextArea(id="text")
            yield Label("", id="error")
            yield Button("Save", id="save", variant="primary")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save()

    def _save(self) -> None:
        name = self.query_one("#name", Input).value.strip()
        days_raw = self.query_one("#days", Input).value.strip()
        email = self.query_one("#email", Input).value.strip()
        text = self.query_one("#text", TextArea).text.strip()
        error = self.query_one("#error", Label)
        if not name or not text:
            error.update("Name and secret text are required.")
            return
        try:
            days = int(days_raw)
            if days <= 0:
                raise ValueError
        except ValueError:
            error.update("Unlock days must be a positive integer.")
            return
        if email and not is_valid_email(email):
            error.update("Delivery email is not valid.")
            return
        unlock_at = datetime.now(timezone.utc) + timedelta(days=days)
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
