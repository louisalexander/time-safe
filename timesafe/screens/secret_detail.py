from __future__ import annotations

import asyncio

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label

from timesafe.screens.reveal import RevealScreen
from timesafe.timelock.tle import NotYetUnlocked
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
            delete = Label("x  Delete")
            delete.add_class("delete")
            yield delete
        yield Footer()

    # ── actions ───────────────────────────────────────────────────────────────
    def action_reveal(self) -> None:
        if not self.secret.is_ready():
            self.app.bell()
            return
        self._do_reveal()

    def action_email(self) -> None:
        if not (self.secret.is_ready() and self.secret.delivery_email):
            self.app.bell()
            return
        self._do_email()

    def action_renew(self) -> None:
        if not self.secret.is_ready():
            self.app.bell()
            return
        from timesafe.screens.renew import RenewScreen

        self.app.push_screen(RenewScreen(self.vault, self.secret))

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

    @work
    async def _do_reveal(self) -> None:
        try:
            plaintext = await asyncio.to_thread(self.vault.reveal, self.secret)
        except NotYetUnlocked:
            self.notify("Not unlocked yet.", severity="warning")
            return
        except Exception as exc:  # noqa: BLE001 - surface any reveal failure to the user
            self.notify(f"Reveal failed: {exc}", severity="error")
            return
        self.app.push_screen(RevealScreen(self.secret.name, plaintext))

    @work
    async def _do_email(self) -> None:
        try:
            await asyncio.to_thread(self.vault.dispatch_email, self.secret)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Couldn't trigger delivery: {exc}", severity="error")
            return
        self.notify(f"Emailing {self.secret.name} to {self.secret.delivery_email}…")

    @work
    async def _do_delete(self) -> None:
        try:
            await asyncio.to_thread(self.vault.delete, self.secret)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Delete failed: {exc}", severity="error")
            return
        self.notify(f"Deleted {self.secret.name}")
        self.app.pop_screen()
