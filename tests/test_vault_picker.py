from textual.widgets import Label, ListView

from timesafe.app import TimeSafeApp
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRef, VaultRegistry


def _app(vaults, tmp_path):
    # Back the registry with a real file so the picker's reload-from-disk reads these vaults.
    path = tmp_path / "vaults.json"
    registry = VaultRegistry(list(vaults), path)
    registry.save()
    return TimeSafeApp(registry=registry, credentials=InMemoryCredentialStore())


async def test_picker_lists_vaults(tmp_path):
    app = _app([VaultRef("fort-knox", "timesafevault/fort-knox")], tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.screen.query_one(ListView)) == 1


async def test_picker_empty_state_message(tmp_path):
    app = _app([], tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert len(app.screen.query_one(ListView)) == 0
        assert app.screen.query_one("#empty", Label)


async def test_selecting_a_vault_calls_open_vault(tmp_path):
    app = _app([VaultRef("fort-knox", "timesafevault/fort-knox")], tmp_path)
    opened: list[str] = []
    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_vault = lambda ref: opened.append(ref.repo)  # type: ignore[method-assign]
        await pilot.press("enter")
        await pilot.pause()
    assert opened == ["timesafevault/fort-knox"]


async def test_remove_deletes_highlighted_vault(tmp_path):
    app = _app([VaultRef("a", "o/a"), VaultRef("b", "o/b")], tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("r")  # remove highlighted (index 0)
        await pilot.pause()
    assert [v.repo for v in app.registry.vaults] == ["o/b"]
