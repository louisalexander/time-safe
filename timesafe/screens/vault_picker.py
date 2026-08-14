from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView


class VaultPickerScreen(Screen):
    """Home screen: pick a vault to open, or add one. Reads the app's registry."""

    BINDINGS = [
        ("n", "add_vault", "add"),
        # 'c' used to open a separate Connect screen. Add vault subsumes it, but the key stays so
        # muscle memory keeps working.
        Binding("c", "add_vault", "add", show=False),
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
        self._vaults = self.app.registry.reload().vaults  # type: ignore[attr-defined]
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
            empty.update("No vaults yet — press n to add one.")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = int(event.item.id.split("-")[1])
        self.app.open_vault(self._vaults[index])  # type: ignore[attr-defined]

    def action_add_vault(self) -> None:
        from timesafe.screens.add_vault import AddVaultScreen

        self.app.push_screen(AddVaultScreen())

    async def action_remove_vault(self) -> None:
        listview = self.query_one("#vaults", ListView)
        index = listview.index
        if index is None or index >= len(self._vaults):
            self.app.bell()
            return
        repo = self._vaults[index].repo
        self.app.registry.reload()  # type: ignore[attr-defined]  # merge other instances first
        self.app.registry.remove(repo)  # type: ignore[attr-defined]
        self.app.registry.save()  # type: ignore[attr-defined]
        await self._rebuild()

    def action_quit(self) -> None:
        self.app.exit()
