# Python Plan 1 — Vault Registry, Keychain Credentials & App Shell

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task. Steps use `- [ ]`.

**Goal:** Stand up the Python project foundation — a vault registry (the only local on-disk state), keychain-backed PAT storage, the Textual app shell, and a vault-picker home screen.

**Architecture:** `timesafe/config/registry.py` persists `VaultRef{name, repo}` to `~/.timesafe/vaults.json`; `timesafe/config/credentials.py` stores PATs via `keyring` (with an in-memory fake for tests); `timesafe/app.py` is the Textual `App` holding the registry + credential store and pushing screens; `timesafe/screens/vault_picker.py` is the home screen.

**Tech Stack:** Python 3.12+, Textual, keyring, pytest. Run everything via `uv run` (e.g. `uv run pytest`). Per spec §2: start clean (no legacy migration).

---

## File Structure
- Create `timesafe/config/registry.py` — `VaultRef`, `VaultRegistry`
- Create `timesafe/config/credentials.py` — `CredentialStore` protocol, `KeyringCredentialStore`, `InMemoryCredentialStore`
- Create `timesafe/app.py` — `TimeSafeApp(App)`
- Create `timesafe/screens/vault_picker.py` — `VaultPickerScreen`
- Create `timesafe/__main__.py` — `main()` entry point
- Tests: `tests/test_registry.py`, `tests/test_credentials.py`, `tests/test_vault_picker.py`

---

## Task 1: VaultRegistry

**Files:** Create `timesafe/config/registry.py`; Test `tests/test_registry.py`

- [ ] **Write failing tests** `tests/test_registry.py`:

```python
from timesafe.config.registry import VaultRef, VaultRegistry


def test_load_missing_is_empty(tmp_path):
    r = VaultRegistry.load(tmp_path / "vaults.json")
    assert r.vaults == []


def test_add_save_reload(tmp_path):
    p = tmp_path / "vaults.json"
    r = VaultRegistry.load(p)
    r.add(VaultRef("fort-knox", "timesafevault/fort-knox"))
    r.save(p)
    reloaded = VaultRegistry.load(p)
    assert [v.repo for v in reloaded.vaults] == ["timesafevault/fort-knox"]
    assert reloaded.vaults[0].name == "fort-knox"


def test_add_is_idempotent_by_repo():
    r = VaultRegistry([])
    r.add(VaultRef("a", "owner/repo"))
    r.add(VaultRef("b", "owner/repo"))
    assert len(r.vaults) == 1
    assert r.contains("owner/repo")


def test_remove_by_repo():
    r = VaultRegistry([])
    r.add(VaultRef("a", "owner/repo"))
    r.remove("owner/repo")
    assert not r.contains("owner/repo")
```

- [ ] **Run, expect fail:** `uv run pytest tests/test_registry.py -q`
- [ ] **Implement** `timesafe/config/registry.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_PATH = Path.home() / ".timesafe" / "vaults.json"


@dataclass
class VaultRef:
    """A pointer to a vault: a label and the GitHub repo that backs it. No credentials."""

    name: str
    repo: str  # "owner/repo"


class VaultRegistry:
    """The on-disk list of known vaults — the ONLY local persistence of vault state."""

    def __init__(self, vaults: list[VaultRef]) -> None:
        self._vaults = vaults

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "VaultRegistry":
        p = Path(path)
        if not p.exists():
            return cls([])
        data = json.loads(p.read_text())
        return cls([VaultRef(**item) for item in data])

    def save(self, path: Path = DEFAULT_PATH) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([asdict(v) for v in self._vaults], indent=2))

    @property
    def vaults(self) -> list[VaultRef]:
        return list(self._vaults)

    def contains(self, repo: str) -> bool:
        return any(v.repo == repo for v in self._vaults)

    def add(self, ref: VaultRef) -> None:
        if not self.contains(ref.repo):
            self._vaults.append(ref)

    def remove(self, repo: str) -> None:
        self._vaults = [v for v in self._vaults if v.repo != repo]
```

- [ ] **Run, expect pass.** Commit `feat(config): vault registry persisted to ~/.timesafe/vaults.json`.

---

## Task 2: CredentialStore (keyring)

**Files:** Create `timesafe/config/credentials.py`; Test `tests/test_credentials.py`

- [ ] **Write failing tests** `tests/test_credentials.py`:

```python
from timesafe.config.credentials import InMemoryCredentialStore, service_name


def test_service_is_repo_scoped():
    assert service_name("owner/repo") == "timesafe:owner/repo"


def test_in_memory_put_get_delete():
    s = InMemoryCredentialStore()
    assert s.get("owner/repo") is None
    s.put("owner/repo", "ghp_x")
    assert s.get("owner/repo") == "ghp_x"
    s.put("owner/repo", "ghp_y")  # upsert
    assert s.get("owner/repo") == "ghp_y"
    s.delete("owner/repo")
    assert s.get("owner/repo") is None
```

- [ ] **Run, expect fail.** **Implement** `timesafe/config/credentials.py`:

```python
from __future__ import annotations

from typing import Protocol

import keyring
import keyring.errors

SERVICE_PREFIX = "timesafe"
ACCOUNT = "timesafe"


def service_name(repo: str) -> str:
    return f"{SERVICE_PREFIX}:{repo}"


class CredentialStore(Protocol):
    """Stores a GitHub PAT per vault repo. Implementations never persist tokens in plaintext files."""

    def get(self, repo: str) -> str | None: ...
    def put(self, repo: str, token: str) -> None: ...
    def delete(self, repo: str) -> None: ...


class KeyringCredentialStore:
    """PATs in the OS keychain via `keyring`, one entry per vault repo."""

    def get(self, repo: str) -> str | None:
        return keyring.get_password(service_name(repo), ACCOUNT)

    def put(self, repo: str, token: str) -> None:
        keyring.set_password(service_name(repo), ACCOUNT, token)

    def delete(self, repo: str) -> None:
        try:
            keyring.delete_password(service_name(repo), ACCOUNT)
        except keyring.errors.PasswordDeleteError:
            pass  # already absent — fine


class InMemoryCredentialStore:
    """Non-persistent CredentialStore for tests and headless runs."""

    def __init__(self) -> None:
        self._tokens: dict[str, str] = {}

    def get(self, repo: str) -> str | None:
        return self._tokens.get(repo)

    def put(self, repo: str, token: str) -> None:
        self._tokens[repo] = token

    def delete(self, repo: str) -> None:
        self._tokens.pop(repo, None)
```

- [ ] **Run, expect pass.** Commit `feat(config): keyring-backed credential store + in-memory fake`.

---

## Task 3: Textual app shell + vault picker

**Files:** Create `timesafe/screens/vault_picker.py`, `timesafe/app.py`, `timesafe/__main__.py`; Test `tests/test_vault_picker.py`

- [ ] **Write failing test** `tests/test_vault_picker.py` (Textual `Pilot`, async):

```python
import pytest

from timesafe.app import TimeSafeApp
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRef, VaultRegistry


@pytest.mark.asyncio
async def test_picker_lists_vaults():
    reg = VaultRegistry([VaultRef("fort-knox", "timesafevault/fort-knox")])
    app = TimeSafeApp(registry=reg, credentials=InMemoryCredentialStore())
    async with app.run_test() as pilot:
        await pilot.pause()
        # The picker's option list contains the vault's repo somewhere in the rendered tree.
        from textual.widgets import ListView

        listview = app.screen.query_one(ListView)
        assert listview is not None
        # one row per vault
        assert len(listview) == 1
```

> Textual's `run_test()` needs `pytest-asyncio` OR Textual's own runner. We use Textual's built-in: mark async tests and rely on `pytest-textual-snapshot`'s asyncio support; if collection errors on the async test, add `asyncio_mode = "auto"` under `[tool.pytest.ini_options]` and the `pytest-asyncio` dev dep. (Resolve at run time — see Step 2.)

- [ ] **Run, expect fail** (`TimeSafeApp` missing). If the failure is "async def not natively supported", add to `pyproject.toml` dev deps `"pytest-asyncio>=0.23"` and `asyncio_mode = "auto"` to `[tool.pytest.ini_options]`, then `uv sync`.
- [ ] **Implement** `timesafe/screens/vault_picker.py`:

```python
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView

from timesafe.config.registry import VaultRef


class VaultPickerScreen(Screen):
    """Home screen: pick a vault to open, or initialize/connect one."""

    BINDINGS = [
        ("n", "new_vault", "new"),
        ("c", "connect_vault", "connect"),
        ("r", "remove_vault", "remove"),
        ("q", "quit", "quit"),
    ]

    def __init__(self, vaults: list[VaultRef]) -> None:
        super().__init__()
        self._vaults = vaults

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield Label("Vaults")
            if self._vaults:
                yield ListView(
                    *[
                        ListItem(Label(f"{v.name}   ({v.repo})"), id=f"vault-{i}")
                        for i, v in enumerate(self._vaults)
                    ]
                )
            else:
                yield Label("No vaults yet — press n to initialize or c to connect.")
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = int(event.item.id.split("-")[1])
        self.app.open_vault(self._vaults[index])  # type: ignore[attr-defined]

    def action_new_vault(self) -> None:
        self.app.bell()  # wired to InitVaultScreen in Plan 3

    def action_connect_vault(self) -> None:
        self.app.bell()  # wired to ConnectVaultScreen in Plan 3

    def action_remove_vault(self) -> None:
        self.app.bell()  # implemented with confirm in a later task
```

- [ ] **Implement** `timesafe/app.py`:

```python
from __future__ import annotations

from textual.app import App

from timesafe.config.credentials import CredentialStore, KeyringCredentialStore
from timesafe.config.registry import VaultRef, VaultRegistry
from timesafe.screens.vault_picker import VaultPickerScreen


class TimeSafeApp(App):
    """Textual application root: holds the registry + credential store, drives the screen stack."""

    TITLE = "time-safe"

    def __init__(
        self,
        registry: VaultRegistry | None = None,
        credentials: CredentialStore | None = None,
    ) -> None:
        super().__init__()
        self.registry = registry if registry is not None else VaultRegistry.load()
        self.credentials = credentials if credentials is not None else KeyringCredentialStore()

    def on_mount(self) -> None:
        self.push_screen(VaultPickerScreen(self.registry.vaults))

    def open_vault(self, ref: VaultRef) -> None:
        """Open a vault. Plan 2 replaces this with a secrets-list screen + in-memory load."""
        token = self.credentials.get(ref.repo)
        if token is None:
            self.notify(f"No stored token for {ref.repo}", severity="error")
            return
        self.notify(f"Opened {ref.repo}")  # placeholder until Plan 2
```

- [ ] **Implement** `timesafe/__main__.py`:

```python
from __future__ import annotations

from timesafe.app import TimeSafeApp


def main() -> None:
    TimeSafeApp().run()


if __name__ == "__main__":
    main()
```

- [ ] **Run, expect pass:** `uv run pytest -q`
- [ ] **Manual:** `uv run timesafe` shows the vault list (or empty-state) and quits on `q`.
- [ ] Commit `feat(ui): Textual app shell + vault picker screen`.

---

## Self-Review
- Spec coverage: vaults.json as only local state (Task 1) ✓; PAT in keychain via keyring (Task 2) ✓; app shell + picker, single screen entry (Task 3) ✓; no legacy migration (start-clean) ✓. Deferred per spec §9: init/connect ('n'/'c' wired in Plan 3), secrets load (Plan 2).
- Placeholder scan: `action_new/connect/remove` intentionally `bell()` placeholders are documented as Plan-3 wiring, not silent gaps.
- Type consistency: `VaultRef(name, repo)`, `VaultRegistry.vaults/contains/add/remove/load/save`, `CredentialStore.get/put/delete`, `TimeSafeApp(registry, credentials)`, `open_vault(VaultRef)` used consistently.
