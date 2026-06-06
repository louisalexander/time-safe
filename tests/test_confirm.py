from timesafe.app import TimeSafeApp
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRegistry
from timesafe.screens.confirm import ConfirmScreen


def _app(tmp_path):
    path = tmp_path / "vaults.json"
    reg = VaultRegistry([], path)
    reg.save()
    return TimeSafeApp(registry=reg, credentials=InMemoryCredentialStore())


async def test_confirm_yes_returns_true(tmp_path):
    results: list[bool] = []
    app = _app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(ConfirmScreen("Delete it?", "Delete", danger=True), results.append)
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    assert results == [True]


async def test_confirm_no_returns_false(tmp_path):
    results: list[bool] = []
    app = _app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(ConfirmScreen("Delete it?"), results.append)
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
    assert results == [False]


async def test_confirm_escape_cancels(tmp_path):
    results: list[bool] = []
    app = _app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.push_screen(ConfirmScreen("Delete it?"), results.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert results == [False]
