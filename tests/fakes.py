"""Shared test doubles for the vault, api and cli suites."""

from __future__ import annotations

from timesafe.timelock import drand, tle
from timesafe.timelock.drand import DrandInfo


class FakeGitHub:
    """In-memory stand-in for GitHubClient. Mirrors its full surface, including repo creation."""

    def __init__(self, repo: str = "owner/repo", *, login: str = "owner", exists: bool = True):
        self.repo = repo
        self.files: dict[str, bytes] = {}
        self.dispatched: list[tuple[str, str]] = []
        self.secrets: dict[str, tuple[str, str]] = {}
        self.login = login
        self.exists = exists
        self.created: list[dict] = []

    # ── contents ──────────────────────────────────────────────────────────────
    def get_file(self, path):
        return self.files.get(path)

    def put_file(self, path, content, message):
        self.files[path] = content

    def delete_file(self, path, message):
        self.files.pop(path, None)

    def list_dir(self, path):
        return [p for p in self.files if p.startswith(path + "/")]

    # ── repo / workflows ──────────────────────────────────────────────────────
    def default_branch(self):
        return "main"

    def dispatch_workflow(self, wf, ref):
        self.dispatched.append((wf, ref))

    def get_authenticated_login(self):
        return self.login

    def repo_exists(self):
        return self.exists

    def create_repo(self, *, auto_init=True):
        if self.exists:
            raise AssertionError("create_repo called on a repo that already exists")
        self.created.append({"repo": self.repo, "auto_init": auto_init})
        self.exists = True

    # ── actions secrets ───────────────────────────────────────────────────────
    def actions_public_key(self):
        return ("kid", "pubkey")

    def put_actions_secret(self, name, value, key_id):
        self.secrets[name] = (value, key_id)

    def delete_actions_secret(self, name):
        self.secrets.pop(name, None)


class FailingGitHub(FakeGitHub):
    """A FakeGitHub whose Nth put_file raises — for exercising partial-write recovery."""

    def __init__(self, *args, fail_on_path_suffix: str, **kwargs):
        super().__init__(*args, **kwargs)
        self._fail_suffix = fail_on_path_suffix

    def put_file(self, path, content, message):
        if path.endswith(self._fail_suffix):
            raise RuntimeError("GitHub API 500 write failed")
        super().put_file(path, content, message)


def fake_timelock(monkeypatch) -> None:
    """Replace drand + tlock with hermetic fakes: no network, reversible 'CT:' ciphertext."""
    monkeypatch.setattr(drand, "fetch_info", lambda http: DrandInfo(0, 3, "chainhash"))
    monkeypatch.setattr(tle, "encrypt", lambda pt, rnd, **k: b"CT:" + pt)

    def fake_dec(ct, **k):
        if ct.startswith(b"CT:"):
            return ct[3:]
        raise tle.TleError("bad ciphertext")

    monkeypatch.setattr(tle, "decrypt", fake_dec)
