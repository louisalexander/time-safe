from datetime import datetime, timedelta, timezone

from tests.fakes import FakeGitHub
from timesafe.vault.vault import SCRIPT_PATH, SECRETS_DIR, SENTINEL, Vault, _workflow_path

# FakeGitHub and the `faked` fixture live in tests/fakes.py + tests/conftest.py so the api and cli
# suites share them.


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
