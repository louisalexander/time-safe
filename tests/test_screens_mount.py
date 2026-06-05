from datetime import datetime, timedelta, timezone

from textual.widgets import Header

from timesafe.app import TimeSafeApp
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRef, VaultRegistry
from timesafe.screens.add_secret import AddSecretScreen
from timesafe.screens.connect_vault import ConnectVaultScreen
from timesafe.screens.gmail_link import GmailLinkScreen
from timesafe.screens.init_vault import InitVaultScreen
from timesafe.screens.renew import RenewScreen
from timesafe.screens.reveal import RevealScreen
from timesafe.screens.secret_detail import SecretDetailScreen
from timesafe.screens.secrets_list import SecretsListScreen
from timesafe.vault.secret import Secret


class FakeVault:
    def list_secrets(self):
        return []


async def test_every_screen_mounts_without_error():
    app = TimeSafeApp(registry=VaultRegistry([]), credentials=InMemoryCredentialStore())
    ref = VaultRef("x", "o/r")
    secret = Secret.create("S", datetime.now(timezone.utc) + timedelta(days=1), 1, "c", "a@b.co")
    screens = [
        SecretsListScreen(FakeVault(), ref),
        SecretDetailScreen(FakeVault(), secret),
        RenewScreen(FakeVault(), secret),
        RevealScreen("S", "the plaintext"),
        AddSecretScreen(FakeVault()),
        GmailLinkScreen(FakeVault()),
        InitVaultScreen(),
        ConnectVaultScreen(),
    ]
    async with app.run_test() as pilot:
        await pilot.pause()
        for screen in screens:
            await app.push_screen(screen)
            await pilot.pause()
            assert app.screen is screen
            assert app.screen.query(Header)  # composed
            app.pop_screen()
            await pilot.pause()
