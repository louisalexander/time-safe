from textual.widgets import ListView

from timesafe.app import TimeSafeApp
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRef, VaultRegistry


async def test_picker_lists_vaults():
    reg = VaultRegistry([VaultRef("fort-knox", "timesafevault/fort-knox")])
    app = TimeSafeApp(registry=reg, credentials=InMemoryCredentialStore())
    async with app.run_test() as pilot:
        await pilot.pause()
        listview = app.screen.query_one(ListView)
        assert len(listview) == 1


async def test_picker_empty_state_has_no_listview():
    app = TimeSafeApp(registry=VaultRegistry([]), credentials=InMemoryCredentialStore())
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.screen.query(ListView)


async def test_selecting_a_vault_calls_open_vault():
    reg = VaultRegistry([VaultRef("fort-knox", "timesafevault/fort-knox")])
    creds = InMemoryCredentialStore()
    creds.put("timesafevault/fort-knox", "ghp_token")
    app = TimeSafeApp(registry=reg, credentials=creds)
    opened: list[str] = []
    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_vault = lambda ref: opened.append(ref.repo)  # type: ignore[method-assign]
        await pilot.press("enter")
        await pilot.pause()
    assert opened == ["timesafevault/fort-knox"]
