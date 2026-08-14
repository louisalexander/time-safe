from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView

from timesafe.format import humanize_seconds
from timesafe.screens.secret_detail import SecretDetailScreen
from timesafe.vault.secret import Secret

READY = "● ready"


def status_text(secret: Secret, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if secret.is_ready(now):
        return READY
    return humanize_seconds(int((secret.unlock_at - now).total_seconds()), ready=READY)


class SecretsListScreen(Screen):
    BINDINGS = [
        ("a", "add", "add"),
        ("g", "relink_gmail", "re-link gmail"),
        ("escape", "app.pop_screen", "back"),
        ("q", "quit", "quit"),
    ]

    def __init__(self, vault, ref) -> None:
        super().__init__()
        self.vault = vault
        self.ref = ref
        self._secrets: list[Secret] = []
        self._row_labels: list[Label] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Label(f"Secrets — {self.ref.name}", classes="title")
            yield ListView(id="secrets")
            yield Label("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.load()
        self.set_interval(1.0, self._tick)

    def on_screen_resume(self) -> None:
        # Reload after returning from add/renew/delete so the list reflects the change.
        self.load()

    @work(exclusive=True)
    async def load(self) -> None:
        status = self.query_one("#status", Label)
        status.update("Loading…")
        try:
            self._secrets = await asyncio.to_thread(self.vault.list_secrets)
        except Exception as exc:  # noqa: BLE001
            status.update(f"Couldn't load secrets: {exc}")
            return
        status.update("" if self._secrets else "No secrets yet — press a to add one.")
        listview = self.query_one("#secrets", ListView)
        await listview.clear()
        self._row_labels = []
        for i, secret in enumerate(self._secrets):
            label = Label(self._row_text(secret))
            self._row_labels.append(label)
            await listview.append(ListItem(label, id=f"secret-{i}"))

    def _row_text(self, secret: Secret) -> str:
        return f"{secret.name:<28} {status_text(secret)}"

    def _tick(self) -> None:
        for secret, label in zip(self._secrets, self._row_labels):
            label.update(self._row_text(secret))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = int(event.item.id.split("-")[1])
        self.app.push_screen(SecretDetailScreen(self.vault, self._secrets[index]))

    def action_add(self) -> None:
        from timesafe.screens.add_secret import AddSecretScreen

        self.app.push_screen(AddSecretScreen(self.vault))  # list reloads on resume

    def action_relink_gmail(self) -> None:
        from timesafe.screens.gmail_link import GmailLinkScreen

        self.app.push_screen(GmailLinkScreen(self.vault))
