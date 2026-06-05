import json

from textual.widgets import Input

from timesafe.app import TimeSafeApp
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRegistry
from timesafe.screens.connect_vault import ConnectVaultScreen
from timesafe.screens.init_vault import InitVaultScreen


class _FakeVault:
    def __init__(self, initialized: bool):
        self._initialized = initialized
        self.inited = False

    def is_initialized(self):
        return self._initialized

    def init(self, ts):
        self.inited = True


async def test_connect_persists_vault_to_disk(tmp_path):
    reg_path = tmp_path / "vaults.json"
    app = TimeSafeApp(registry=VaultRegistry.load(reg_path), credentials=InMemoryCredentialStore())
    app.make_vault = lambda repo, token: _FakeVault(initialized=True)  # type: ignore[assignment]

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = ConnectVaultScreen()
        await app.push_screen(screen)
        await pilot.pause()
        screen.query_one("#repo", Input).value = "owner/repo"
        screen.query_one("#token", Input).value = "ghp_test"
        screen._connect()
        await app.workers.wait_for_complete()
        await pilot.pause()

    saved = json.loads(reg_path.read_text())
    assert [v["repo"] for v in saved] == ["owner/repo"]
    assert app.credentials.get("owner/repo") == "ghp_test"


async def test_init_persists_vault_to_disk(tmp_path):
    reg_path = tmp_path / "vaults.json"
    app = TimeSafeApp(registry=VaultRegistry.load(reg_path), credentials=InMemoryCredentialStore())
    fake = _FakeVault(initialized=False)
    app.make_vault = lambda repo, token: fake  # type: ignore[assignment]

    async with app.run_test() as pilot:
        await pilot.pause()
        screen = InitVaultScreen()
        await app.push_screen(screen)
        await pilot.pause()
        screen.query_one("#name", Input).value = "myvault"
        screen.query_one("#repo", Input).value = "owner/repo"
        screen.query_one("#token", Input).value = "ghp_test"
        screen._create()
        await app.workers.wait_for_complete()
        await pilot.pause()

    saved = json.loads(reg_path.read_text())
    assert [v["repo"] for v in saved] == ["owner/repo"]
    assert fake.inited is True
    assert app.credentials.get("owner/repo") == "ghp_test"
