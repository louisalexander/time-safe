import io

import pytest
from rich.console import Console
from textual.screen import Screen

from timesafe.app import TimeSafeApp
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRegistry

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
