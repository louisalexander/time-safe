from datetime import datetime, timedelta, timezone

import pytest

from timesafe.timelock import drand, tle
from timesafe.timelock.drand import DrandInfo
from timesafe.vault.vault import SCRIPT_PATH, SECRETS_DIR, SENTINEL, Vault, _workflow_path


class FakeGitHub:
    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.dispatched: list[tuple[str, str]] = []
        self.secrets: dict[str, tuple[str, str]] = {}

    def get_file(self, path):
        return self.files.get(path)

    def put_file(self, path, content, message):
        self.files[path] = content

    def delete_file(self, path, message):
        self.files.pop(path, None)

    def list_dir(self, path):
        return [p for p in self.files if p.startswith(path + "/")]

    def default_branch(self):
        return "main"

    def dispatch_workflow(self, wf, ref):
        self.dispatched.append((wf, ref))

    def actions_public_key(self):
        return ("kid", "pubkey")

    def put_actions_secret(self, name, value, key_id):
        self.secrets[name] = (value, key_id)

    def delete_actions_secret(self, name):
        self.secrets.pop(name, None)


@pytest.fixture
def faked(monkeypatch):
    """Fake drand (no network) and tlock (reversible 'CT:' prefix) so vault logic is hermetic."""
    monkeypatch.setattr(drand, "fetch_info", lambda http: DrandInfo(0, 3, "chainhash"))
    monkeypatch.setattr(tle, "encrypt", lambda pt, rnd, **k: b"CT:" + pt)

    def fake_dec(ct, **k):
        if ct.startswith(b"CT:"):
            return ct[3:]
        raise tle.TleError("bad ciphertext")

    monkeypatch.setattr(tle, "decrypt", fake_dec)
    # secrets_api.seal is called by relink; replace with identity so no real crypto in this test
    monkeypatch.setattr("timesafe.vault.vault.seal", lambda pk, v: f"sealed:{v}")


def _future():
    return datetime.now(timezone.utc) + timedelta(days=30)


def test_put_secret_pushes_tle_meta_and_workflow(faked):
    gh = FakeGitHub()
    s = Vault(gh).put_secret("Name", _future(), "the secret", "a@b.co")
    assert gh.files[f"{SECRETS_DIR}/{s.id}.tle"] == b"CT:the secret"
    assert f"{SECRETS_DIR}/{s.id}.meta" in gh.files
    assert _workflow_path(s.id) in gh.files


def test_list_secrets_parses_meta(faked):
    gh = FakeGitHub()
    v = Vault(gh)
    s = v.put_secret("N", _future(), "x", None)
    assert [x.id for x in v.list_secrets()] == [s.id]


def test_reveal_decrypts(faked):
    gh = FakeGitHub()
    v = Vault(gh)
    s = v.put_secret("N", _future(), "topsecret", None)
    assert v.reveal(s) == "topsecret"


def test_renew_decrypts_then_re_encrypts_to_new_time(faked):
    gh = FakeGitHub()
    v = Vault(gh)
    s = v.put_secret("N", _future(), "topsecret", None)
    new_unlock = datetime.now(timezone.utc) + timedelta(days=60)
    v.renew(s, new_unlock)
    assert s.unlock_at == new_unlock
    # ciphertext was re-written (fake tlock is reversible 'CT:' prefix)
    assert gh.files[f"{SECRETS_DIR}/{s.id}.tle"] == b"CT:topsecret"
    import json

    meta = json.loads(gh.files[f"{SECRETS_DIR}/{s.id}.meta"].decode())
    assert meta["unlock_at"] == new_unlock.isoformat()


def test_delete_removes_all_files(faked):
    gh = FakeGitHub()
    v = Vault(gh)
    s = v.put_secret("N", _future(), "x", None)
    v.delete(s)
    assert f"{SECRETS_DIR}/{s.id}.tle" not in gh.files
    assert _workflow_path(s.id) not in gh.files


def test_init_and_is_initialized(faked):
    gh = FakeGitHub()
    v = Vault(gh)
    assert not v.is_initialized()
    v.init("2026-06-05T00:00:00Z")
    assert v.is_initialized()
    assert SCRIPT_PATH in gh.files
    assert SENTINEL in gh.files


def test_dispatch_email_ensures_workflow_then_dispatches(faked):
    gh = FakeGitHub()
    v = Vault(gh)
    s = v.put_secret("N", _future(), "x", "a@b.co")
    v.dispatch_email(s)
    assert gh.dispatched == [(f"unlock-{s.id}.yml", "main")]


def test_relink_gmail_writes_four_secrets(faked):
    gh = FakeGitHub()
    Vault(gh).relink_gmail("g@x.com", "cid", "csec", "rt")
    assert set(gh.secrets) == {
        "GMAIL_ADDRESS",
        "OAUTH_CLIENT_ID",
        "OAUTH_CLIENT_SECRET",
        "GMAIL_REFRESH_TOKEN",
    }
