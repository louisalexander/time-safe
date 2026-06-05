from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, TextArea


class RevealScreen(Screen):
    """Shows a locally-decrypted secret. Plaintext lives only here and is dropped on pop."""

    BINDINGS = [("escape", "app.pop_screen", "back")]

    def __init__(self, name: str, plaintext: str) -> None:
        super().__init__()
        self._name = name
        self._plaintext = plaintext

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            label = Label(f"{self._name} — revealed")
            label.add_class("ready")
            yield label
            area = TextArea(self._plaintext, read_only=True, id="plaintext")
            yield area
        yield Footer()
