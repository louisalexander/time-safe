from textual.widgets import Label, ListView

from timesafe.app import TimeSafeApp
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRef, VaultRegistry


def _app(vaults):
    return TimeSafeApp(registry=VaultRegistry(vaults), credentials=InMemoryCredentialStore())


async def test_picker_lists_vaults():
    app = _app([VaultRef("fort-knox", "timesafevault/fort-knox")])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.screen.query_one(ListView)) == 1


async def test_picker_empty_state_message():
    app = _app([])
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.screen.query_one(ListView)) == 0
        assert app.screen.query_one("#empty", Label)  # empty-state label is present


async def test_selecting_a_vault_calls_open_vault():
    reg = [VaultRef("fort-knox", "timesafevault/fort-knox")]
    app = _app(reg)
    opened: list[str] = []
    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_vault = lambda ref: opened.append(ref.repo)  # type: ignore[method-assign]
        await pilot.press("enter")
        await pilot.pause()
    assert opened == ["timesafevault/fort-knox"]


async def test_remove_deletes_highlighted_vault():
    app = _app([VaultRef("a", "o/a"), VaultRef("b", "o/b")])
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("r")  # remove highlighted (index 0)
        await pilot.pause()
    assert [v.repo for v in app.registry.vaults] == ["o/b"]
