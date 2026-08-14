from datetime import datetime, timedelta, timezone

from textual.widgets import Label

from tests.fakes import FakeGitHub
from timesafe.app import TimeSafeApp
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRegistry
from timesafe.screens.secret_detail import SecretDetailScreen
from timesafe.vault.vault import Vault

SECRET = "correct-horse-battery-staple"


def _past():
    return datetime.now(timezone.utc) - timedelta(seconds=5)


async def _detail(vault, secret, call=None):
    """Mount the detail screen, optionally invoke one of its methods, and collect what it said."""
    app = TimeSafeApp(registry=VaultRegistry([]), credentials=InMemoryCredentialStore())
    notes: list[tuple[str, str]] = []
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = SecretDetailScreen(vault, secret)
        await app.push_screen(screen)
        await pilot.pause()
        screen.notify = lambda msg, **kw: notes.append((msg, kw.get("severity", "information")))
        labels = [str(label.content) for label in screen.query(Label)]
        if call is not None:
            getattr(screen, call)()
            await app.workers.wait_for_complete()
            await pilot.pause()
    return labels, notes


# ── the id (#37) ─────────────────────────────────────────────────────────────
async def test_the_detail_screen_shows_the_secret_id(faked):
    vault = Vault(FakeGitHub())
    secret = vault.put_secret("n", _past(), SECRET, None)
    labels, _ = await _detail(vault, secret)
    assert any(secret.id in text for text in labels)


async def test_copy_puts_the_id_on_the_clipboard(faked):
    vault = Vault(FakeGitHub())
    secret = vault.put_secret("n", _past(), SECRET, None)
    app = TimeSafeApp(registry=VaultRegistry([]), credentials=InMemoryCredentialStore())
    copied: list[str] = []
    async with app.run_test() as pilot:
        await pilot.pause()
        app.copy_to_clipboard = copied.append  # type: ignore[method-assign]
        await app.push_screen(SecretDetailScreen(vault, secret))
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
    assert copied == [secret.id]


# ── typed errors (#33, #34) ──────────────────────────────────────────────────
async def test_revealing_a_locked_secret_warns_with_a_countdown(faked):
    vault = Vault(FakeGitHub())
    secret = vault.put_secret("n", datetime.now(timezone.utc) + timedelta(hours=2), SECRET, None)

    _, notes = await _detail(vault, secret, call="action_reveal")

    (message, severity) = notes[0]
    assert severity == "warning"  # waiting is not a fault
    assert "1h 59m" in message


async def test_a_failed_delete_is_explained_not_dumped(faked):
    """A raw httpx exception is multi-line, names a request URL, and says nothing actionable."""

    class Stubborn(FakeGitHub):
        def delete_file(self, path, message):
            raise RuntimeError("connection reset by peer")

    vault = Vault(Stubborn())
    secret = vault.put_secret("n", _past(), SECRET, None)

    _, notes = await _detail(vault, secret, call="_do_delete")

    (message, severity) = notes[0]
    assert severity == "error"
    assert message.startswith("Failed to delete n.")
    assert "connection reset by peer" not in message


async def test_emailing_a_secret_with_no_address_is_refused(faked):
    vault = Vault(FakeGitHub())
    secret = vault.put_secret("n", _past(), SECRET, None)
    _, notes = await _detail(vault, secret, call="action_email")
    assert notes  # bell alone leaves the user guessing


async def test_email_dispatches_the_unlock_workflow(faked):
    vault = Vault(FakeGitHub())
    secret = vault.put_secret("n", _past(), SECRET, "a@b.co")
    await _detail(vault, secret, call="action_email")
    assert vault.github.dispatched == [(f"unlock-{secret.id}.yml", "main")]
