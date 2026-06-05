from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView

from timesafe.config.registry import VaultRef


class VaultPickerScreen(Screen):
    """Home screen: pick a vault to open, or initialize/connect one."""

    BINDINGS = [
        ("n", "new_vault", "new"),
        ("c", "connect_vault", "connect"),
        ("r", "remove_vault", "remove"),
        ("q", "quit", "quit"),
    ]

    def __init__(self, vaults: list[VaultRef]) -> None:
        super().__init__()
        self._vaults = vaults

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Label("Vaults")
            if self._vaults:
                yield ListView(
                    *[
                        ListItem(Label(f"{v.name}   ({v.repo})"), id=f"vault-{i}")
                        for i, v in enumerate(self._vaults)
                    ]
                )
            else:
                yield Label("No vaults yet — press n to initialize or c to connect.")
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = int(event.item.id.split("-")[1])
        self.app.open_vault(self._vaults[index])  # type: ignore[attr-defined]

    def action_new_vault(self) -> None:
        self.app.bell()  # wired to InitVaultScreen in Plan 3

    def action_connect_vault(self) -> None:
        self.app.bell()  # wired to ConnectVaultScreen in Plan 3

    def action_remove_vault(self) -> None:
        self.app.bell()  # implemented with a confirm step in a later task
