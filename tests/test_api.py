import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.fakes import FailingGitHub, FakeGitHub
from timesafe import api
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRegistry
from timesafe.errors import (
    AmbiguousNameError,
    NotFoundError,
    NotReadyError,
    UsageError,
    VaultError,
)
from timesafe.vault.vault import SECRETS_DIR, Vault, _workflow_path

SECRET = "correct-horse-battery-staple"


def _vault(gh=None):
    return Vault(gh or FakeGitHub())


def _past():
    return datetime.now(timezone.utc) - timedelta(seconds=5)


# ── add ──────────────────────────────────────────────────────────────────────
def test_add_returns_the_authoritative_id_and_locks_the_secret(faked):
    vault = _vault()
    result = api.add(name="break-glass", duration="10d", secret=SECRET, vault=vault)

    assert result["name"] == "break-glass"
    assert result["pushed"] is True
    assert result["vault_path"] == f"{SECRETS_DIR}/{result['id']}.tle"
    assert isinstance(result["round"], int)
    # The id is the vault's, not derived from the name — callers must persist what they're handed.
    assert result["id"] != "break-glass"
    assert vault.reveal(next(s for s in vault.list_secrets() if s.id == result["id"])) == SECRET


def test_add_unlock_at_is_iso8601_utc_at_the_requested_offset(faked):
    before = datetime.now(timezone.utc)
    result = api.add(name="n", duration="2h", secret=SECRET, vault=_vault())
    unlock = datetime.fromisoformat(result["unlock_at"])
    assert timedelta(hours=2) - (unlock - before) < timedelta(seconds=5)


def test_add_accepts_a_timedelta_as_well_as_a_string(faked):
    result = api.add(name="n", duration=timedelta(days=3), secret=SECRET, vault=_vault())
    assert result["id"]


def test_add_rejects_an_empty_secret(faked):
    with pytest.raises(UsageError):
        api.add(name="n", duration="1d", secret="", vault=_vault())


def test_add_rejects_a_blank_name(faked):
    with pytest.raises(UsageError):
        api.add(name="   ", duration="1d", secret=SECRET, vault=_vault())


def test_add_rejects_a_bad_duration(faked):
    with pytest.raises(UsageError):
        api.add(name="n", duration="tomorrow", secret=SECRET, vault=_vault())


def test_add_rejects_an_invalid_delivery_email(faked):
    with pytest.raises(UsageError):
        api.add(name="n", duration="1d", secret=SECRET, email="not-an-email", vault=_vault())


def test_add_records_a_valid_delivery_email(faked):
    vault = _vault()
    result = api.add(name="n", duration="1d", secret=SECRET, email="a@b.co", vault=vault)
    assert vault.list_secrets()[0].delivery_email == "a@b.co"
    assert result["id"]


def test_a_failed_write_leaves_no_orphan_behind(faked):
    """A half-written secret is invisible to list_secrets and unrecoverable, so it must be removed."""
    gh = FailingGitHub(fail_on_path_suffix=".meta")
    with pytest.raises(VaultError):
        api.add(name="n", duration="1d", secret=SECRET, vault=Vault(gh))

    assert gh.files == {}


def test_a_failed_write_reports_what_it_cleaned_up(faked):
    gh = FailingGitHub(fail_on_path_suffix=".meta")
    with pytest.raises(VaultError) as exc:
        api.add(name="n", duration="1d", secret=SECRET, vault=Vault(gh))
    assert exc.value.extra["cleaned"]


def test_a_failed_write_never_echoes_the_plaintext(faked):
    gh = FailingGitHub(fail_on_path_suffix=".tle")
    with pytest.raises(VaultError) as exc:
        api.add(name="n", duration="1d", secret=SECRET, vault=Vault(gh))
    assert SECRET not in str(exc.value)
    assert SECRET not in repr(exc.value.to_json())


def test_a_failed_write_reports_the_status_code_and_path(faked):
    """'(HTTPStatusError)' tells an operator nothing. The status and path cost no secrecy."""
    gh = _http_failing(403, ".github/workflows/unlock-x.yml")
    with pytest.raises(VaultError) as exc:
        api.add(name="n", duration="1d", secret=SECRET, vault=Vault(gh))

    message = str(exc.value)
    assert "403" in message
    assert ".github/workflows/" in message


def test_a_403_on_the_workflow_path_names_the_missing_scope(faked):
    # Every add writes a per-secret workflow, so a contents-only token fails here and nowhere else.
    gh = _http_failing(403, ".github/workflows/unlock-x.yml")
    with pytest.raises(VaultError) as exc:
        api.add(name="n", duration="1d", secret=SECRET, vault=Vault(gh))
    assert "workflow" in str(exc.value).lower()
    assert "scope" in str(exc.value).lower()


def test_a_403_elsewhere_does_not_blame_the_workflow_scope(faked):
    gh = _http_failing(403, "vault/secrets/x.tle")
    with pytest.raises(VaultError) as exc:
        api.add(name="n", duration="1d", secret=SECRET, vault=Vault(gh))
    assert "scope" not in str(exc.value).lower()


def test_the_http_failure_message_still_never_contains_the_plaintext(faked):
    gh = _http_failing(403, ".github/workflows/unlock-x.yml")
    with pytest.raises(VaultError) as exc:
        api.add(name="n", duration="1d", secret=SECRET, vault=Vault(gh))
    assert SECRET not in str(exc.value)
    assert SECRET not in json.dumps(exc.value.to_json())


def _http_failing(status: int, path_suffix: str):
    """A FakeGitHub whose put_file raises a real httpx.HTTPStatusError for one path."""

    class HttpFailingGitHub(FakeGitHub):
        def put_file(self, path, content, message):
            if path.endswith(path_suffix.rsplit("/", 1)[-1]) or path.startswith(
                path_suffix.rsplit("/", 1)[0]
            ):
                request = httpx.Request("PUT", f"https://api.github.com/repos/o/r/contents/{path}")
                raise httpx.HTTPStatusError(
                    "boom", request=request, response=httpx.Response(status, request=request)
                )
            super().put_file(path, content, message)

    return HttpFailingGitHub()


def test_cleanup_removes_the_workflow_too(faked):
    gh = FailingGitHub(fail_on_path_suffix=".yml")
    with pytest.raises(VaultError):
        api.add(name="n", duration="1d", secret=SECRET, vault=Vault(gh))
    assert gh.files == {}


# ── status ───────────────────────────────────────────────────────────────────
def test_status_of_a_locked_secret(faked):
    vault = _vault()
    added = api.add(name="n", duration="1d", secret=SECRET, vault=vault)

    st = api.status(secret_id=added["id"], vault=vault)

    assert st["id"] == added["id"]
    assert st["name"] == "n"
    assert st["ready"] is False
    assert 0 < st["seconds_remaining"] <= 86400


def test_status_of_a_ready_secret_clamps_seconds_remaining_at_zero(faked):
    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)

    st = api.status(secret_id=secret.id, vault=vault)

    assert st["ready"] is True
    assert st["seconds_remaining"] == 0


def test_status_with_no_selector_covers_every_secret(faked):
    vault = _vault()
    api.add(name="a", duration="1d", secret=SECRET, vault=vault)
    api.add(name="b", duration="2d", secret=SECRET, vault=vault)

    assert {s["name"] for s in api.status(vault=vault)} == {"a", "b"}


def test_status_for_an_unknown_id_is_not_found(faked):
    with pytest.raises(NotFoundError) as exc:
        api.status(secret_id="nope", vault=_vault())
    assert exc.value.exit_code == 5


# ── name lookup ──────────────────────────────────────────────────────────────
def test_name_lookup_works_when_unambiguous(faked):
    vault = _vault()
    added = api.add(name="unique", duration="1d", secret=SECRET, vault=vault)
    assert api.status(name="unique", vault=vault)["id"] == added["id"]


def test_a_duplicate_name_fails_loudly_instead_of_picking_one(faked):
    vault = _vault()
    first = api.add(name="dup", duration="1d", secret=SECRET, vault=vault)
    second = api.add(name="dup", duration="2d", secret=SECRET, vault=vault)

    with pytest.raises(AmbiguousNameError) as exc:
        api.status(name="dup", vault=vault)

    assert exc.value.exit_code == 2
    assert sorted(exc.value.extra["ids"]) == sorted([first["id"], second["id"]])


def test_an_unknown_name_is_not_found(faked):
    with pytest.raises(NotFoundError):
        api.status(name="ghost", vault=_vault())


# ── reveal ───────────────────────────────────────────────────────────────────
def test_reveal_returns_the_plaintext_once_unlocked(faked):
    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)
    assert api.reveal(secret_id=secret.id, vault=vault) == SECRET


def test_reveal_before_the_unlock_time_raises_not_ready(faked):
    vault = _vault()
    added = api.add(name="n", duration="1d", secret=SECRET, vault=vault)

    with pytest.raises(NotReadyError) as exc:
        api.reveal(secret_id=added["id"], vault=vault)

    assert exc.value.exit_code == 3
    assert exc.value.extra["seconds_remaining"] > 0


def test_reveal_does_not_fetch_the_ciphertext_when_the_meta_says_locked(faked):
    """The pre-check must short-circuit, so a locked poll costs one listing and no blob fetch."""
    vault = _vault()
    added = api.add(name="n", duration="1d", secret=SECRET, vault=vault)
    fetched = []
    original = vault.github.get_file
    vault.github.get_file = lambda p: (fetched.append(p), original(p))[1]

    with pytest.raises(NotReadyError):
        api.reveal(secret_id=added["id"], vault=vault)

    assert not any(p.endswith(".tle") for p in fetched)


def test_reveal_maps_a_late_tlock_refusal_to_not_ready(faked, monkeypatch):
    """Clock skew: meta says ready but the drand round hasn't published. Still exit 3, not a fault."""
    from timesafe.timelock import tle

    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)

    def too_early(ct, **k):
        raise tle.NotYetUnlocked("too early to decrypt")

    monkeypatch.setattr(tle, "decrypt", too_early)

    with pytest.raises(NotReadyError):
        api.reveal(secret_id=secret.id, vault=vault)


def test_reveal_maps_a_real_tlock_failure_to_a_vault_error(faked, monkeypatch):
    from timesafe.timelock import tle

    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)
    monkeypatch.setattr(tle, "decrypt", lambda ct, **k: (_ for _ in ()).throw(tle.TleError("boom")))

    with pytest.raises(VaultError):
        api.reveal(secret_id=secret.id, vault=vault)


def test_reveal_without_a_selector_is_a_usage_error(faked):
    with pytest.raises(UsageError):
        api.reveal(vault=_vault())


# ── list ─────────────────────────────────────────────────────────────────────
def test_list_returns_full_metadata(faked):
    vault = _vault()
    added = api.add(name="n", duration="1d", secret=SECRET, email="a@b.co", vault=vault)

    (row,) = api.list_secrets(vault=vault)

    assert row["id"] == added["id"]
    assert row["name"] == "n"
    assert row["delivery_email"] == "a@b.co"
    assert row["ready"] is False
    assert row["round"] == added["round"]
    assert row["chain"]
    assert row["created_at"]


def test_list_is_empty_for_a_fresh_vault(faked):
    assert api.list_secrets(vault=_vault()) == []


# ── init ─────────────────────────────────────────────────────────────────────
def _init_deps(tmp_path):
    return VaultRegistry([], tmp_path / "vaults.json"), InMemoryCredentialStore()


def test_init_initializes_an_existing_repo_and_registers_it(faked, tmp_path):
    registry, creds = _init_deps(tmp_path)
    gh = FakeGitHub("me/vault", exists=True)

    result = api.init(
        repo="me/vault", name="seedbox", token="tok",
        github=gh, registry=registry, credentials=creds,
    )

    assert result == {
        "repo": "me/vault", "created": False, "initialized": True,
        "registered": True, "token_saved": True,
    }
    assert registry.reload().contains("me/vault")
    assert creds.get("me/vault") == "tok"


def test_init_is_idempotent(faked, tmp_path):
    registry, creds = _init_deps(tmp_path)
    gh = FakeGitHub("me/vault", exists=True)
    common = dict(repo="me/vault", name="seedbox", token="tok", registry=registry, credentials=creds)

    api.init(github=gh, **common)
    second = api.init(github=gh, **common)

    assert second["created"] is False
    assert second["initialized"] is False
    assert second["registered"] is False


def test_init_with_create_makes_a_private_repo(faked, tmp_path):
    registry, creds = _init_deps(tmp_path)
    gh = FakeGitHub("me/vault", exists=False)

    result = api.init(
        repo="me/vault", name="v", token="tok", create=True,
        github=gh, registry=registry, credentials=creds,
    )

    assert result["created"] is True
    assert gh.created == [{"repo": "me/vault", "auto_init": True}]


def test_init_without_create_on_a_missing_repo_is_a_vault_error(faked, tmp_path):
    registry, creds = _init_deps(tmp_path)
    gh = FakeGitHub("me/vault", exists=False)

    with pytest.raises(VaultError) as exc:
        api.init(
            repo="me/vault", name="v", token="tok",
            github=gh, registry=registry, credentials=creds,
        )
    assert "--create" in str(exc.value)


def test_init_rejects_a_malformed_repo(faked, tmp_path):
    registry, creds = _init_deps(tmp_path)
    with pytest.raises(UsageError):
        api.init(
            repo="seedbox", name="v", token="tok",
            github=FakeGitHub(), registry=registry, credentials=creds,
        )


def test_init_survives_an_unusable_keychain(faked, tmp_path):
    """A headless box has no keychain; the repo-side work still counts as done."""
    registry, _ = _init_deps(tmp_path)

    class HeadlessStore(InMemoryCredentialStore):
        def put(self, repo, token):
            raise RuntimeError("no keyring backend")

    result = api.init(
        repo="me/vault", name="v", token="tok",
        github=FakeGitHub("me/vault", exists=True),
        registry=registry, credentials=HeadlessStore(),
    )

    assert result["initialized"] is True
    assert result["token_saved"] is False


def test_init_writes_the_delivery_script_and_sentinel(faked, tmp_path):
    from timesafe.vault.vault import SCRIPT_PATH, SENTINEL

    registry, creds = _init_deps(tmp_path)
    gh = FakeGitHub("me/vault", exists=True)

    api.init(
        repo="me/vault", name="v", token="tok",
        github=gh, registry=registry, credentials=creds,
    )

    assert SCRIPT_PATH in gh.files
    assert SENTINEL in gh.files


def test_workflow_path_helper_is_still_what_cleanup_targets(faked):
    # Guards the cleanup path against a rename of the workflow naming scheme.
    assert _workflow_path("abc") == ".github/workflows/unlock-abc.yml"
