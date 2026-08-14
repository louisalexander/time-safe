import io
from types import SimpleNamespace

import pytest
from rich.console import Console
from textual.screen import Screen

from timesafe.app import TimeSafeApp
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRef, VaultRegistry

SENTINEL = "correct-horse-battery-staple"


class _Exploding(Screen):
    def on_mount(self) -> None:
        plaintext = SENTINEL  # noqa: F841 — a live frame local, exactly like the add path's
        raise RuntimeError("something went wrong")


async def _crash(tmp_path) -> str:
    """Crash the app under a recording error console and return everything it printed on the way out."""
    app = TimeSafeApp(
        registry=VaultRegistry([], tmp_path / "vaults.json"),
        credentials=InMemoryCredentialStore(),
    )
    recorded = Console(file=io.StringIO(), record=True, width=200)
    with pytest.raises(RuntimeError):
        async with app.run_test() as pilot:
            await pilot.pause()
            app.error_console = recorded
            app.push_screen(_Exploding())
            await pilot.pause()
    return recorded.export_text()


async def test_crash_never_renders_frame_locals(tmp_path):
    output = await _crash(tmp_path)
    assert SENTINEL not in output
    assert "plaintext" not in output
    assert "Traceback" not in output


async def test_crash_debug_mode_shows_the_exception_but_still_no_frames(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMESAFE_DEBUG", "1")
    output = await _crash(tmp_path)
    assert "RuntimeError: something went wrong" in output
    assert SENTINEL not in output
    assert "plaintext" not in output


# ── token resolution ─────────────────────────────────────────────────────────
class _RaisingCredentialStore:
    """A keyring backend that raises rather than returning None — a locked or absent keychain."""

    def get(self, repo):
        raise RuntimeError("no Secret Service running")

    def put(self, repo, token):
        raise RuntimeError("no Secret Service running")

    def delete(self, repo):
        pass


def _app(tmp_path, credentials=None) -> TimeSafeApp:
    return TimeSafeApp(
        registry=VaultRegistry([VaultRef("v", "o/r")], tmp_path / "vaults.json"),
        credentials=credentials if credentials is not None else InMemoryCredentialStore(),
    )


async def _open(app: TimeSafeApp) -> list[str]:
    """Open the registered vault, recording the tokens make_vault was handed."""
    tokens: list[str] = []
    app.make_vault = lambda repo, token: tokens.append(token) or SimpleNamespace(  # type: ignore[assignment]
        list_secrets=lambda: []
    )
    async with app.run_test() as pilot:
        await pilot.pause()
        app.open_vault(VaultRef("v", "o/r"))
        await pilot.pause()
    return tokens


async def test_open_vault_uses_the_environment_token(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMESAFE_GITHUB_TOKEN", "ghp_from_env")
    assert await _open(_app(tmp_path)) == ["ghp_from_env"]


async def test_open_vault_falls_back_to_the_keychain(tmp_path, monkeypatch):
    monkeypatch.delenv("TIMESAFE_GITHUB_TOKEN", raising=False)
    credentials = InMemoryCredentialStore()
    credentials.put("o/r", "ghp_from_keychain")
    assert await _open(_app(tmp_path, credentials)) == ["ghp_from_keychain"]


async def test_open_vault_survives_a_keyring_backend_that_raises(tmp_path, monkeypatch):
    """A headless box has no unlocked keychain, and keyring raises there rather than returning None."""
    monkeypatch.setenv("TIMESAFE_GITHUB_TOKEN", "ghp_from_env")
    assert await _open(_app(tmp_path, _RaisingCredentialStore())) == ["ghp_from_env"]


async def test_open_vault_with_no_token_anywhere_reports_instead_of_crashing(tmp_path, monkeypatch):
    monkeypatch.delenv("TIMESAFE_GITHUB_TOKEN", raising=False)
    assert await _open(_app(tmp_path, _RaisingCredentialStore())) == []
