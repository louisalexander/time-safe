from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmScreen(ModalScreen[bool]):
    """A yes/no modal. Dismisses with True (confirmed) or False (cancelled)."""

    BINDINGS = [
        ("y", "confirm", "yes"),
        ("n", "cancel", "no"),
        ("escape", "cancel", "cancel"),
    ]

    def __init__(self, message: str, confirm_label: str = "Confirm", danger: bool = False) -> None:
        super().__init__()
        self._message = message
        self._confirm_label = confirm_label
        self._danger = danger

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static(self._message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button(
                    self._confirm_label,
                    id="confirm",
                    variant="error" if self._danger else "primary",
                )
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
