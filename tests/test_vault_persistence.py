import json

from textual.widgets import Checkbox, Input, Label

from tests.fakes import FakeGitHub
from timesafe.app import TimeSafeApp
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRegistry
from timesafe.screens.add_vault import AddVaultScreen
from timesafe.vault.vault import SENTINEL


async def _add_vault(tmp_path, github, *, credentials=None, name="myvault", create=False):
    """Drive the add-vault screen and return (app, error text, notifications)."""
    app = TimeSafeApp(
        registry=VaultRegistry.load(tmp_path / "vaults.json"),
        credentials=credentials if credentials is not None else InMemoryCredentialStore(),
    )
    app.make_github = lambda repo, token: github  # type: ignore[assignment]
    notes: list[tuple[str, str]] = []
    error = ""
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = AddVaultScreen()
        await app.push_screen(screen)
        await pilot.pause()
        screen.notify = lambda msg, **kw: notes.append((msg, kw.get("severity", "information")))
        screen.query_one("#name", Input).value = name
        screen.query_one("#repo", Input).value = "owner/repo"
        screen.query_one("#token", Input).value = "ghp_test"
        screen.query_one("#create", Checkbox).value = create
        screen._add()
        await app.workers.wait_for_complete()
        await pilot.pause()
        if screen.is_attached:
            error = str(screen.query_one("#error", Label).content)
    return app, error, notes


def _saved(tmp_path) -> list[dict]:
    path = tmp_path / "vaults.json"
    return json.loads(path.read_text()) if path.exists() else []


async def test_adding_an_uninitialized_vault_initializes_registers_and_stores(faked, tmp_path):
    gh = FakeGitHub("owner/repo", exists=True)

    app, error, _ = await _add_vault(tmp_path, gh)

    assert error == ""
    assert SENTINEL in gh.files
    assert [v["repo"] for v in _saved(tmp_path)] == ["owner/repo"]
    assert app.credentials.get("owner/repo") == "ghp_test"


async def test_adding_an_already_initialized_vault_just_registers_it(faked, tmp_path):
    """This used to be a hard error telling the user to go and pick the other screen."""
    gh = FakeGitHub("owner/repo", exists=True)
    gh.files[SENTINEL] = b"{}"

    _, error, notes = await _add_vault(tmp_path, gh)

    assert error == ""
    assert [v["repo"] for v in _saved(tmp_path)] == ["owner/repo"]
    assert any("added to your list" in message for message, _ in notes)


async def test_adding_the_same_vault_twice_is_safe(faked, tmp_path):
    gh = FakeGitHub("owner/repo", exists=True)
    await _add_vault(tmp_path, gh)

    _, error, notes = await _add_vault(tmp_path, gh)

    assert error == ""
    assert [v["repo"] for v in _saved(tmp_path)] == ["owner/repo"]
    assert any("already set up" in message for message, _ in notes)


async def test_the_create_checkbox_makes_a_missing_repo(faked, tmp_path):
    gh = FakeGitHub("owner/repo", exists=False)

    _, error, _ = await _add_vault(tmp_path, gh, create=True)

    assert error == ""
    assert gh.created == [{"repo": "owner/repo", "auto_init": True}]


async def test_a_missing_repo_without_the_checkbox_points_at_the_checkbox(faked, tmp_path):
    """api.init's own message names the CLI's --create, which this screen does not have."""
    gh = FakeGitHub("owner/repo", exists=False)

    _, error, _ = await _add_vault(tmp_path, gh, create=False)

    assert "--create" not in error
    assert "does not exist" in error
    assert _saved(tmp_path) == []


async def test_a_keychain_that_cannot_store_is_reported_as_itself(faked, tmp_path):
    """The registry write succeeded; saying "saving locally failed" was simply untrue."""

    class Headless(InMemoryCredentialStore):
        def put(self, repo, token):
            raise RuntimeError("no keyring backend")

    _, error, notes = await _add_vault(tmp_path, FakeGitHub("owner/repo"), credentials=Headless())

    assert error == ""  # the screen completed rather than stalling on work that succeeded
    assert [v["repo"] for v in _saved(tmp_path)] == ["owner/repo"]
    warning = next(message for message, severity in notes if severity == "warning")
    assert "keychain" in warning
    assert "TIMESAFE_GITHUB_TOKEN" in warning
    assert "ghp_test" not in warning


async def test_the_vault_keeps_the_name_the_user_chose(faked, tmp_path):
    """Connect derived a name from the repo, so a second machine labelled the vault differently."""
    gh = FakeGitHub("owner/repo", exists=True)
    gh.files[SENTINEL] = b"{}"

    await _add_vault(tmp_path, gh, name="fort-knox")

    assert [v["name"] for v in _saved(tmp_path)] == ["fort-knox"]
