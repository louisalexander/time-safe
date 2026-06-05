"""Generate SVG screenshots of the TUI screens (run: uv run python scripts/make_screenshots.py)."""

from __future__ import annotations

import asyncio
import pathlib
from datetime import datetime, timedelta, timezone

from timesafe.app import TimeSafeApp
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRef, VaultRegistry
from timesafe.screens.add_secret import AddSecretScreen
from timesafe.screens.reveal import RevealScreen
from timesafe.screens.secret_detail import SecretDetailScreen
from timesafe.screens.secrets_list import SecretsListScreen
from timesafe.vault.secret import Secret

OUT = pathlib.Path("docs/screenshots")
OUT.mkdir(parents=True, exist_ok=True)
SIZE = (96, 28)


def secret(name: str, delta: timedelta, email: str | None) -> Secret:
    return Secret.create(name, datetime.now(timezone.utc) + delta, 1, "quicknet", email)


SECRETS = [
    secret("GitHub recovery codes", timedelta(days=210, hours=4, minutes=9), "me@example.com"),
    secret("Cold-wallet seed phrase", timedelta(days=29, hours=1, minutes=33), "me@example.com"),
    secret("Diary — open in 2030", timedelta(seconds=-5), "me@example.com"),
    secret("Quick test", timedelta(minutes=2, seconds=14), None),
]


class FakeVault:
    def __init__(self, secrets):
        self._secrets = secrets

    def list_secrets(self):
        return self._secrets


def fresh_app():
    reg = VaultRegistry([VaultRef("personal", "me/vault"), VaultRef("work", "acme/secrets")])
    return TimeSafeApp(registry=reg, credentials=InMemoryCredentialStore())


async def capture(app, screen, name, settle=0.0):
    async with app.run_test(size=SIZE) as pilot:
        await pilot.pause()
        if screen is not None:
            await app.push_screen(screen)
            await pilot.pause()
        if settle:
            await asyncio.sleep(settle)
            await pilot.pause()
        await pilot.pause()
        (OUT / f"{name}.svg").write_text(app.export_screenshot(title="time-safe"))
        print("wrote", OUT / f"{name}.svg")


async def main():
    ref = VaultRef("personal", "me/vault")
    fake = FakeVault(SECRETS)
    await capture(fresh_app(), None, "01-vault-picker")  # default screen is the picker
    await capture(fresh_app(), SecretsListScreen(fake, ref), "02-secrets-list", settle=0.4)
    await capture(fresh_app(), SecretDetailScreen(fake, SECRETS[2]), "03-secret-detail-ready")
    await capture(fresh_app(), AddSecretScreen(fake), "04-add-secret")
    await capture(
        fresh_app(),
        RevealScreen("Diary — open in 2030", "Dear future me,\n\nremember why you locked this.\n"),
        "05-reveal",
    )


if __name__ == "__main__":
    asyncio.run(main())
