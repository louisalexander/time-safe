import pytest
from textual.widgets import Input, Label

from tests.fakes import FailingGitHub, FakeGitHub
from timesafe.app import TimeSafeApp
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRegistry
from timesafe.screens.add_secret import AddSecretScreen
from timesafe.vault.vault import Vault

SECRET = "  spaces matter  "


async def _add(vault, *, name="n", duration="7d", text=SECRET, email="") -> str:
    """Drive the add screen to completion and return whatever it painted into #error.

    A successful add pops the screen, so an empty string means it worked.
    """
    app = TimeSafeApp(registry=VaultRegistry([]), credentials=InMemoryCredentialStore())
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = AddSecretScreen(vault)
        await app.push_screen(screen)
        await pilot.pause()
        screen.query_one("#name", Input).value = name
        screen.query_one("#duration", Input).value = duration
        screen.query_one("#text", Input).value = text
        screen.query_one("#email", Input).value = email
        screen._save()
        await app.workers.wait_for_complete()
        await pilot.pause()
        if not screen.is_attached:
            return ""
        return str(screen.query_one("#error", Label).content)


async def test_the_secret_is_locked_byte_for_byte(faked):
    """A secret added in the TUI and read back through `timesafe reveal` must be the same bytes."""
    vault = Vault(FakeGitHub())
    assert await _add(vault) == ""
    (secret,) = vault.list_secrets()
    assert vault.reveal(secret) == SECRET


async def test_a_secret_of_only_whitespace_is_accepted(faked):
    """The CLI accepts it, so the emptiness check must test the value, not the stripped value."""
    vault = Vault(FakeGitHub())
    assert await _add(vault, text="   ") == ""
    assert vault.reveal(vault.list_secrets()[0]) == "   "


async def test_an_empty_secret_is_still_refused(faked):
    vault = Vault(FakeGitHub())
    assert "required" in await _add(vault, text="")
    assert vault.list_secrets() == []


async def test_a_failed_write_leaves_no_orphan_in_the_repo(faked):
    """A stranded .tle is invisible — list_secrets reads only .meta — and its id was never shown."""
    gh = FailingGitHub(fail_on_path_suffix=".meta")
    message = await _add(Vault(gh))

    assert gh.files == {}
    assert "Nothing was left behind" in message


async def test_a_failure_never_paints_the_plaintext(faked):
    gh = FailingGitHub(fail_on_path_suffix=".tle")
    assert SECRET.strip() not in await _add(Vault(gh))


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"duration": "tomorrow"}, "duration"),
        ({"email": "not-an-email"}, "email"),
        ({"name": "  "}, "required"),
    ],
)
async def test_validation_still_happens_on_the_screen(faked, kwargs, expected):
    vault = Vault(FakeGitHub())
    assert expected in (await _add(vault, **kwargs)).lower()
    assert vault.list_secrets() == []
