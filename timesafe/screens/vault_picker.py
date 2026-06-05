from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView


class VaultPickerScreen(Screen):
    """Home screen: pick a vault to open, or initialize/connect one. Reads the app's registry."""

    BINDINGS = [
        ("n", "new_vault", "new"),
        ("c", "connect_vault", "connect"),
        ("r", "remove_vault", "remove"),
        ("q", "quit", "quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Label("Vaults", classes="title")
            yield ListView(id="vaults")
            yield Label("", id="empty")
        yield Footer()

    async def on_mount(self) -> None:
        await self._rebuild()

    async def on_screen_resume(self) -> None:
        # Refresh after returning from init/connect/remove so new vaults show immediately.
        await self._rebuild()

    async def _rebuild(self) -> None:
        self._vaults = self.app.registry.vaults  # type: ignore[attr-defined]
        listview = self.query_one("#vaults", ListView)
        await listview.clear()
        empty = self.query_one("#empty", Label)
        if self._vaults:
            empty.update("")
            for i, v in enumerate(self._vaults):
                await listview.append(ListItem(Label(f"{v.name}   ({v.repo})"), id=f"vault-{i}"))
            listview.index = 0
            listview.focus()
        else:
            empty.update("No vaults yet — press n to initialize or c to connect.")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = int(event.item.id.split("-")[1])
        self.app.open_vault(self._vaults[index])  # type: ignore[attr-defined]

    def action_new_vault(self) -> None:
        from timesafe.screens.init_vault import InitVaultScreen

        self.app.push_screen(InitVaultScreen())

    def action_connect_vault(self) -> None:
        from timesafe.screens.connect_vault import ConnectVaultScreen

        self.app.push_screen(ConnectVaultScreen())

    async def action_remove_vault(self) -> None:
        listview = self.query_one("#vaults", ListView)
        index = listview.index
        if index is None or index >= len(self._vaults):
            self.app.bell()
            return
        self.app.registry.remove(self._vaults[index].repo)  # type: ignore[attr-defined]
        self.app.registry.save()  # type: ignore[attr-defined]
        await self._rebuild()

    def action_quit(self) -> None:
        self.app.exit()
