from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label

from timesafe import api
from timesafe.errors import TimesafeError
from timesafe.format import humanize_seconds
from timesafe.screens.errors import message_of, severity_of
from timesafe.screens.reveal import RevealScreen
from timesafe.vault.secret import Secret


def visible_actions(secret: Secret) -> list[str]:
    """Action labels available for a secret. Reveal/Email/Renew only when ready."""
    actions: list[str] = []
    if secret.is_ready():
        actions.append("reveal")
        if secret.delivery_email:
            actions.append("email")
        actions.append("renew")
    actions.append("delete")
    return actions


class SecretDetailScreen(Screen):
    BINDINGS = [
        ("d", "reveal", "reveal"),
        ("s", "email", "email"),
        ("r", "renew", "renew"),
        ("c", "copy_id", "copy id"),
        ("x", "delete", "delete"),
        ("escape", "app.pop_screen", "back"),
    ]

    def __init__(self, vault, secret: Secret) -> None:
        super().__init__()
        self.vault = vault
        self.secret = secret

    def compose(self) -> ComposeResult:
        s = self.secret
        actions = visible_actions(s)
        yield Header(show_clock=False)
        with Vertical():
            status = Label(f"{s.name}    {'● ready' if s.is_ready() else 'locked'}")
            if s.is_ready():
                status.add_class("ready")
            yield status
            # The id, not the name, is what the vault and the CLI address a secret by, and it is not
            # derivable from the name — so a TUI that hides it strands its own secrets.
            yield Label(f"id         {s.id}")
            yield Label(f"unlocks    {s.unlock_at.isoformat(timespec='minutes')}")
            yield Label(f"delivery   {s.delivery_email or '—'}")
            yield Label(f"round      {s.drand_round}")
            yield Label("")
            if "reveal" in actions:
                yield Label("d  Reveal")
            else:
                yield Label("d  Reveal (locked)")
            if "email" in actions:
                yield Label("s  Email it")
            if "renew" in actions:
                yield Label("r  Renew lock")
            yield Label("c  Copy id")
            delete = Label("x  Delete")
            delete.add_class("delete")
            yield delete
        yield Footer()

    # ── actions ───────────────────────────────────────────────────────────────
    def action_reveal(self) -> None:
        if not self.secret.is_ready():
            self._not_ready()
            return
        self._do_reveal()

    def action_email(self) -> None:
        if not self.secret.is_ready():
            self._not_ready()
            return
        self._do_email()

    def action_renew(self) -> None:
        if not self.secret.is_ready():
            self._not_ready()
            return
        from timesafe.screens.renew import RenewScreen

        self.app.push_screen(RenewScreen(self.vault, self.secret))

    def action_copy_id(self) -> None:
        self.app.copy_to_clipboard(self.secret.id)
        self.notify("Secret id copied to clipboard.")

    def action_delete(self) -> None:
        from timesafe.screens.confirm import ConfirmScreen

        def after(confirmed: bool | None) -> None:
            if confirmed:
                self._do_delete()

        self.app.push_screen(
            ConfirmScreen(
                f"Delete “{self.secret.name}”? This is permanent.", "Delete", danger=True
            ),
            after,
        )

    # ── workers ───────────────────────────────────────────────────────────────
    @work
    async def _do_reveal(self) -> None:
        try:
            plaintext = await asyncio.to_thread(
                api.reveal_secret, vault=self.vault, secret=self.secret
            )
        except TimesafeError as exc:
            self._report(exc)
            return
        self.app.push_screen(RevealScreen(self.secret.name, plaintext))

    @work
    async def _do_email(self) -> None:
        try:
            await asyncio.to_thread(api.send_email, vault=self.vault, secret=self.secret)
        except TimesafeError as exc:
            self._report(exc)
            return
        self.notify(f"Emailing {self.secret.name} to {self.secret.delivery_email}…")

    @work
    async def _do_delete(self) -> None:
        try:
            await asyncio.to_thread(api.delete, vault=self.vault, secret=self.secret)
        except TimesafeError as exc:
            self._report(exc)
            return
        self.notify(f"Deleted {self.secret.name}")
        self.app.pop_screen()

    # ── reporting ─────────────────────────────────────────────────────────────
    def _report(self, exc: TimesafeError) -> None:
        self.notify(message_of(exc), severity=severity_of(exc))

    def _not_ready(self) -> None:
        """Say how long the wait is. A bell alone tells the user nothing about why nothing happened."""
        self.app.bell()
        remaining = int((self.secret.unlock_at - datetime.now(timezone.utc)).total_seconds())
        self.notify(
            f"{self.secret.name} is still locked. Ready in {humanize_seconds(remaining)}.",
            severity="warning",
        )
