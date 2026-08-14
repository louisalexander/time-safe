import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from tests.fakes import FailingGitHub, FakeGitHub
from timesafe import api
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRegistry
from timesafe.errors import (
    AmbiguousNameError,
    NetworkError,
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
        api.add(name="n", duration="1d", secret=SECRET, email="a@b.co", vault=Vault(gh))

    message = str(exc.value)
    assert "403" in message
    assert ".github/workflows/" in message


def test_a_403_on_the_workflow_path_names_the_missing_scope(faked):
    # Only an add with --email writes a workflow, so a contents-only token fails here and nowhere
    # else — and only for that add.
    gh = _http_failing(403, ".github/workflows/unlock-x.yml")
    with pytest.raises(VaultError) as exc:
        api.add(name="n", duration="1d", secret=SECRET, email="a@b.co", vault=Vault(gh))
    assert "workflow" in str(exc.value).lower()
    assert "scope" in str(exc.value).lower()


def test_a_403_on_the_workflow_path_says_the_scope_is_only_needed_for_email(faked):
    """The old message told operators the scope was mandatory for every add. It no longer is, and
    an error that sends someone to widen a token needlessly is worse than none."""
    gh = _http_failing(403, ".github/workflows/unlock-x.yml")
    with pytest.raises(VaultError) as exc:
        api.add(name="n", duration="1d", secret=SECRET, email="a@b.co", vault=Vault(gh))
    message = str(exc.value).lower()
    assert "--email" in message
    assert "every add" not in message


def test_add_without_an_email_succeeds_on_a_token_that_cannot_write_workflows(faked):
    """The motivating bug: local-reveal-only automation had to hand over the `workflow` scope."""
    gh = _http_failing(403, ".github/workflows/unlock-x.yml")
    result = api.add(name="n", duration="1d", secret=SECRET, vault=Vault(gh))
    assert result["pushed"] is True
    assert not [p for p in gh.files if p.startswith(".github/workflows/")]


def test_a_403_elsewhere_does_not_blame_the_workflow_scope(faked):
    gh = _http_failing(403, "vault/secrets/x.tle")
    with pytest.raises(VaultError) as exc:
        api.add(name="n", duration="1d", secret=SECRET, vault=Vault(gh))
    assert "scope" not in str(exc.value).lower()


def test_the_http_failure_message_still_never_contains_the_plaintext(faked):
    gh = _http_failing(403, ".github/workflows/unlock-x.yml")
    with pytest.raises(VaultError) as exc:
        api.add(name="n", duration="1d", secret=SECRET, email="a@b.co", vault=Vault(gh))
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
    # The workflow is written last and only for a delivery address, so this is the add that can
    # strand one.
    gh = FailingGitHub(fail_on_path_suffix=".yml")
    with pytest.raises(VaultError):
        api.add(name="n", duration="1d", secret=SECRET, email="a@b.co", vault=Vault(gh))
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


def test_status_by_id_reads_only_that_secrets_meta(faked):
    """A known id must not cost a vault scan. The CLI exists to be polled from cron, and a scan is
    one request per secret against a 5000/hr limit — a 50-secret vault would die at 49 polls/hr."""
    vault = _vault()
    added = api.add(name="n", duration="1d", secret=SECRET, vault=vault)
    for extra in range(4):
        api.add(name=f"other{extra}", duration="1d", secret=SECRET, vault=vault)
    gh = vault.github
    gh.reads.clear()
    gh.listings.clear()

    api.status(secret_id=added["id"], vault=vault)

    assert gh.listings == []
    assert gh.reads == [f"{SECRETS_DIR}/{added['id']}.meta"]


def test_status_by_id_stays_constant_as_the_vault_grows(faked):
    small, large = _vault(), _vault()
    one = api.add(name="n", duration="1d", secret=SECRET, vault=small)
    many = api.add(name="n", duration="1d", secret=SECRET, vault=large)
    for extra in range(20):
        api.add(name=f"o{extra}", duration="1d", secret=SECRET, vault=large)

    for vault, added in ((small, one), (large, many)):
        vault.github.reads.clear()
        api.status(secret_id=added["id"], vault=vault)

    assert len(small.github.reads) == len(large.github.reads)


def test_status_by_id_for_an_unknown_id_is_still_not_found(faked):
    # Was "scanned everything, no match"; it is now a 404 on one path. Same exit code either way.
    vault = _vault()
    api.add(name="n", duration="1d", secret=SECRET, vault=vault)
    with pytest.raises(NotFoundError):
        api.status(secret_id="no-such-id", vault=vault)


def test_status_by_name_still_scans_because_it_has_to(faked):
    """Names aren't paths — resolving one genuinely requires reading every meta."""
    vault = _vault()
    api.add(name="findme", duration="1d", secret=SECRET, vault=vault)
    vault.github.listings.clear()

    assert api.status(name="findme", vault=vault)["name"] == "findme"
    assert vault.github.listings == [SECRETS_DIR]


# ── reveal ───────────────────────────────────────────────────────────────────
def test_reveal_by_id_reads_only_the_meta_and_the_ciphertext(faked):
    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)
    for extra in range(4):
        vault.put_secret(f"other{extra}", _past(), SECRET, None)
    gh = vault.github
    gh.reads.clear()
    gh.listings.clear()

    assert api.reveal(secret_id=secret.id, vault=vault) == SECRET

    assert gh.listings == []
    assert gh.reads == [
        f"{SECRETS_DIR}/{secret.id}.meta",
        f"{SECRETS_DIR}/{secret.id}.tle",
    ]


def test_reveal_by_id_for_an_unknown_id_is_still_not_found(faked):
    vault = _vault()
    vault.put_secret("ready", _past(), SECRET, None)
    with pytest.raises(NotFoundError):
        api.reveal(secret_id="no-such-id", vault=vault)


def test_reveal_without_a_selector_costs_no_requests_at_all(faked):
    """A pure argument error must not reach the network first."""
    vault = _vault()
    api.add(name="n", duration="1d", secret=SECRET, vault=vault)
    gh = vault.github
    gh.reads.clear()
    gh.listings.clear()

    with pytest.raises(UsageError):
        api.reveal(vault=vault)

    assert gh.reads == [] and gh.listings == []


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


# ── delete ───────────────────────────────────────────────────────────────────
def test_delete_removes_every_file_the_secret_owns(faked):
    gh = FakeGitHub()
    vault = _vault(gh)
    added = api.add(name="n", duration="1d", secret=SECRET, vault=vault)

    result = api.delete(secret_id=added["id"], vault=vault)

    assert result == {"id": added["id"], "name": "n", "deleted": True}
    assert gh.files == {}


def test_delete_by_name_when_unambiguous(faked):
    vault = _vault()
    api.add(name="unique", duration="1d", secret=SECRET, vault=vault)
    assert api.delete(name="unique", vault=vault)["deleted"] is True
    assert api.list_secrets(vault=vault) == []


def test_delete_of_an_unknown_id_is_not_found(faked):
    with pytest.raises(NotFoundError):
        api.delete(secret_id="nope", vault=_vault())


def test_delete_without_a_selector_is_a_usage_error(faked):
    """No selector must never mean 'all' — that would empty a vault on a typo."""
    with pytest.raises(UsageError):
        api.delete(vault=_vault())


def test_delete_works_on_a_still_locked_secret(faked):
    """Unlike renew, delete needs no plaintext, so a locked secret is removable."""
    vault = _vault()
    added = api.add(name="n", duration="365d", secret=SECRET, vault=vault)
    assert api.delete(secret_id=added["id"], vault=vault)["deleted"] is True


# ── renew ────────────────────────────────────────────────────────────────────
def test_renew_re_locks_a_ready_secret_for_a_new_duration(faked):
    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)

    result = api.renew(secret_id=secret.id, duration="2h", vault=vault)

    assert result["id"] == secret.id
    assert result["renewed"] is True
    unlock = datetime.fromisoformat(result["unlock_at"])
    assert timedelta(hours=2) - (unlock - datetime.now(timezone.utc)) < timedelta(seconds=5)
    # The plaintext survived the round trip.
    reloaded = next(s for s in vault.list_secrets() if s.id == secret.id)
    reloaded.unlock_at = _past()
    assert vault.reveal(reloaded) == SECRET


def test_renew_of_a_locked_secret_reuses_reveals_not_ready_path(faked):
    """A locked tlock ciphertext cannot be re-timed because it cannot be read — exit 3, not a fault."""
    vault = _vault()
    added = api.add(name="n", duration="1d", secret=SECRET, vault=vault)

    with pytest.raises(NotReadyError) as exc:
        api.renew(secret_id=added["id"], duration="2h", vault=vault)

    assert exc.value.exit_code == 3
    assert exc.value.extra["seconds_remaining"] > 0


def test_renew_does_not_touch_the_vault_when_the_secret_is_locked(faked):
    vault = _vault()
    added = api.add(name="n", duration="1d", secret=SECRET, vault=vault)
    before = dict(vault.github.files)

    with pytest.raises(NotReadyError):
        api.renew(secret_id=added["id"], duration="2h", vault=vault)

    assert vault.github.files == before


def test_renew_rejects_a_bad_duration(faked):
    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)
    with pytest.raises(UsageError):
        api.renew(secret_id=secret.id, duration="whenever", vault=vault)


def test_renew_of_an_unknown_id_is_not_found(faked):
    with pytest.raises(NotFoundError):
        api.renew(secret_id="nope", duration="1d", vault=_vault())


def test_renew_maps_a_late_tlock_refusal_to_not_ready(faked, monkeypatch):
    from timesafe.timelock import tle

    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)
    monkeypatch.setattr(
        tle, "decrypt", lambda ct, **k: (_ for _ in ()).throw(tle.NotYetUnlocked("too early"))
    )

    with pytest.raises(NotReadyError):
        api.renew(secret_id=secret.id, duration="1d", vault=vault)


def test_renew_keeps_the_delivery_email_and_rewrites_the_workflow(faked):
    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, "a@b.co")

    api.renew(secret_id=secret.id, duration="1d", vault=vault)

    (row,) = api.list_secrets(vault=vault)
    assert row["delivery_email"] == "a@b.co"
    assert _workflow_path(secret.id) in vault.github.files


def test_renew_of_an_email_less_secret_still_writes_no_workflow(faked):
    """`add` without --email writes no workflow so the token needs no `workflow` scope. Renewing
    through the API must not quietly undo that and start demanding it."""
    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)

    api.renew(secret_id=secret.id, duration="1d", vault=vault)

    assert _workflow_path(secret.id) not in vault.github.files


# ── send ─────────────────────────────────────────────────────────────────────
def test_send_dispatches_the_delivery_workflow(faked):
    vault = _vault()
    secret = vault.put_secret("n", _past(), SECRET, "a@b.co")

    result = api.send(secret_id=secret.id, vault=vault)

    assert result == {
        "id": secret.id,
        "name": "n",
        "delivery_email": "a@b.co",
        "dispatched": True,
    }
    assert vault.github.dispatched == [(f"unlock-{secret.id}.yml", "main")]


def test_send_writes_the_workflow_when_add_left_none_behind(faked):
    """A secret added without an email has no workflow file; adding one later must still work."""
    vault = _vault()
    secret = vault.put_secret("n", _past(), SECRET, "a@b.co")
    vault.github.delete_file(_workflow_path(secret.id), "simulate an add with no email")

    api.send(secret_id=secret.id, vault=vault)

    assert _workflow_path(secret.id) in vault.github.files
    assert vault.github.dispatched


def test_send_refuses_a_secret_with_no_delivery_address(faked):
    """There is nowhere to send it, and dispatching would write a workflow that emails no one."""
    vault = _vault()
    secret = vault.put_secret("n", _past(), SECRET, None)

    with pytest.raises(UsageError):
        api.send(secret_id=secret.id, vault=vault)

    assert vault.github.dispatched == []


def test_send_works_before_the_unlock_time(faked):
    """The workflow is the time gate — tlock refuses server-side until the round lands."""
    vault = _vault()
    added = api.add(name="n", duration="1d", secret=SECRET, email="a@b.co", vault=vault)
    assert api.send(secret_id=added["id"], vault=vault)["dispatched"] is True


def test_send_of_an_unknown_id_is_not_found(faked):
    with pytest.raises(NotFoundError):
        api.send(secret_id="nope", vault=_vault())


# ── link-gmail ───────────────────────────────────────────────────────────────
def test_link_gmail_seals_the_four_actions_secrets(faked):
    gh = FakeGitHub()

    result = api.link_gmail(
        gmail_address="vault@gmail.com",
        client_id="cid",
        client_secret="csec",
        refresh_token="1//rt",
        vault=_vault(gh),
    )

    assert result["linked"] is True
    assert result["gmail_address"] == "vault@gmail.com"
    assert set(gh.secrets) == {
        "GMAIL_ADDRESS",
        "OAUTH_CLIENT_ID",
        "OAUTH_CLIENT_SECRET",
        "GMAIL_REFRESH_TOKEN",
    }
    # The reported names must be what was really written, not a list that can drift from it.
    assert set(result["secrets"]) == set(gh.secrets)


def test_link_gmail_reports_the_secret_names_but_never_their_values(faked):
    gh = FakeGitHub()
    result = api.link_gmail(
        gmail_address="v@gmail.com", client_id="cid", client_secret="csec",
        refresh_token="1//rt", vault=_vault(gh),
    )
    assert result["secrets"] == [
        "GMAIL_ADDRESS", "OAUTH_CLIENT_ID", "OAUTH_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN",
    ]
    assert "1//rt" not in json.dumps(result)
    assert "csec" not in json.dumps(result)


def test_link_gmail_rejects_a_malformed_address(faked):
    with pytest.raises(UsageError):
        api.link_gmail(
            gmail_address="not-an-email", client_id="cid", client_secret="csec",
            refresh_token="rt", vault=_vault(),
        )


@pytest.mark.parametrize("missing", ["client_id", "client_secret", "refresh_token"])
def test_link_gmail_requires_every_credential(faked, missing):
    kwargs = dict(
        gmail_address="v@gmail.com", client_id="cid", client_secret="csec", refresh_token="rt"
    )
    kwargs[missing] = ""
    with pytest.raises(UsageError):
        api.link_gmail(vault=_vault(), **kwargs)


def test_link_gmail_refreshes_the_delivery_script(faked):
    from timesafe.vault.vault import SCRIPT_PATH

    gh = FakeGitHub()
    api.link_gmail(
        gmail_address="v@gmail.com", client_id="cid", client_secret="csec",
        refresh_token="rt", vault=_vault(gh),
    )
    assert SCRIPT_PATH in gh.files


# ── retry, at the level a cron job feels it ──────────────────────────────────
#
# `status --id` is the per-minute poll the whole retry layer exists to protect. It reads exactly one
# `.meta`, through get_text_file — so these drive the real GitHubClient rather than FakeGitHub,
# which has no transport to fail.
META_PATH = "vault/secrets/the-id.meta"
META_JSON = json.dumps(
    {
        "id": "the-id",
        "name": "break-glass",
        "unlock_at": "2027-01-01T00:00:00+00:00",
        "drand_round": 1,
        "drand_chain": "chainhash",
        "created_at": "2026-01-01T00:00:00+00:00",
        "delivery_email": None,
    }
).encode()


def _meta_response(_request=None):
    """One `.meta`, as the Contents API inlines it. Takes the request so respx can call it repeatedly."""
    import base64

    return httpx.Response(
        200,
        json={
            "encoding": "base64",
            "content": base64.b64encode(META_JSON).decode(),
            "sha": "metasha",
        },
    )


def _live_vault(slept, **kwargs):
    from timesafe.github.client import API, GitHubClient

    http = httpx.Client(base_url=API, headers={"Authorization": "Bearer t"})
    return Vault(GitHubClient("owner/repo", "t", client=http, sleep=slept.append, **kwargs))


@respx.mock
def test_status_by_id_survives_a_transient_5xx_on_the_meta_read(faked):
    from timesafe.github.client import API

    slept = []
    respx.get(f"{API}/repos/owner/repo/contents/{META_PATH}").mock(
        side_effect=[httpx.Response(500), _meta_response()]
    )

    row = api.status(secret_id="the-id", vault=_live_vault(slept))

    assert row["id"] == "the-id"
    assert len(slept) == 1


@respx.mock
def test_no_retry_still_fails_the_meta_read_on_the_first_attempt(faked):
    from timesafe.github.client import API

    slept = []
    route = respx.get(f"{API}/repos/owner/repo/contents/{META_PATH}").mock(
        side_effect=[httpx.Response(500), _meta_response()]
    )

    with pytest.raises(VaultError):
        api.status(secret_id="the-id", vault=_live_vault(slept, retries=1))

    assert route.call_count == 1
    assert slept == []


@respx.mock
def test_renew_by_id_reads_one_meta_and_retries_it(faked):
    """renew --id must be constant-cost too, not a full scan behind a retried read."""
    from timesafe.github.client import API

    slept = []
    meta = respx.get(f"{API}/repos/owner/repo/contents/{META_PATH}").mock(
        side_effect=[httpx.Response(503), _meta_response()]
    )
    listing = respx.get(f"{API}/repos/owner/repo/contents/{SECRETS_DIR}").respond(json=[])

    # Still locked, so it stops at the readiness gate — after the lookup, which is what we measure.
    with pytest.raises(NotReadyError):
        api.renew(secret_id="the-id", duration="1d", vault=_live_vault(slept))

    assert meta.call_count == 2  # one failure, one retry
    assert listing.call_count == 0  # never scanned the vault
    assert len(slept) == 1


@respx.mock
def test_delete_by_id_never_scans_the_vault(faked):
    from timesafe.github.client import API

    slept = []
    respx.get(f"{API}/repos/owner/repo/contents/{META_PATH}").mock(side_effect=_meta_response)
    listing = respx.get(f"{API}/repos/owner/repo/contents/{SECRETS_DIR}").respond(json=[])
    respx.get(f"{API}/repos/owner/repo/contents/vault/secrets/the-id.tle").respond(404)
    respx.get(f"{API}/repos/owner/repo/contents/.github/workflows/unlock-the-id.yml").respond(404)
    respx.delete(f"{API}/repos/owner/repo/contents/{META_PATH}").respond(200, json={})

    assert api.delete(secret_id="the-id", vault=_live_vault(slept))["deleted"] is True
    assert listing.call_count == 0


@respx.mock
def test_send_by_id_never_scans_the_vault(faked):
    from timesafe.github.client import API

    slept = []
    respx.get(f"{API}/repos/owner/repo/contents/{META_PATH}").mock(side_effect=_meta_response)
    listing = respx.get(f"{API}/repos/owner/repo/contents/{SECRETS_DIR}").respond(json=[])

    # This fixture has no delivery address, so send stops right after the lookup — which is the
    # part being measured.
    with pytest.raises(UsageError):
        api.send(secret_id="the-id", vault=_live_vault(slept))

    assert listing.call_count == 0


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


# ── operations on an already-resolved secret ─────────────────────────────────
def test_secrets_returns_the_objects_not_json(faked):
    vault = _vault()
    added = api.add(name="n", duration="1d", secret=SECRET, vault=vault)
    (only,) = api.secrets(vault=vault)
    assert only.id == added["id"]
    assert only.name == "n"


def test_secrets_types_a_transport_failure(faked):
    class Offline(FakeGitHub):
        def list_dir(self, path):
            raise httpx.ConnectError("no route to host")

    with pytest.raises(NetworkError):
        api.secrets(vault=Vault(Offline()))


def test_secrets_types_a_malformed_meta_rather_than_raising_through_the_ui(faked):
    vault = _vault()
    vault.put_secret("n", _past(), SECRET, None)
    vault.github.files[f"{SECRETS_DIR}/broken.meta"] = b"not json"

    with pytest.raises(VaultError):
        api.secrets(vault=vault)


def test_reveal_secret_returns_the_plaintext_once_unlocked(faked):
    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)
    assert api.reveal_secret(vault=vault, secret=secret) == SECRET


def test_reveal_secret_before_the_unlock_time_is_not_ready_with_a_countdown(faked):
    vault = _vault()
    api.add(name="n", duration="1d", secret=SECRET, vault=vault)
    (secret,) = api.secrets(vault=vault)

    with pytest.raises(NotReadyError) as exc:
        api.reveal_secret(vault=vault, secret=secret)

    assert exc.value.extra["seconds_remaining"] > 0
    assert exc.value.extra["id"] == secret.id


def test_reveal_secret_maps_a_late_tlock_refusal_to_not_ready(faked, monkeypatch):
    from timesafe.timelock import tle

    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)
    monkeypatch.setattr(
        tle, "decrypt", lambda ct, **k: (_ for _ in ()).throw(tle.NotYetUnlocked("too early"))
    )

    with pytest.raises(NotReadyError):
        api.reveal_secret(vault=vault, secret=secret)


# ── renew ────────────────────────────────────────────────────────────────────
def test_renew_relocks_a_ready_secret_to_a_later_round(faked):
    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)

    result = api.renew_secret(vault=vault, secret=secret, duration="7d")

    assert result["id"] == secret.id
    assert datetime.fromisoformat(result["unlock_at"]) > datetime.now(timezone.utc)
    assert vault.list_secrets()[0].is_ready() is False


def test_renew_of_a_still_locked_secret_is_not_ready(faked):
    vault = _vault()
    api.add(name="n", duration="1d", secret=SECRET, vault=vault)
    (secret,) = api.secrets(vault=vault)

    with pytest.raises(NotReadyError):
        api.renew_secret(vault=vault, secret=secret, duration="7d")


def test_renew_secret_rejects_a_bad_duration(faked):
    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)
    with pytest.raises(UsageError):
        api.renew_secret(vault=vault, secret=secret, duration="tomorrow")


def test_renew_rejects_a_bad_duration_before_spending_any_requests(faked):
    """A malformed duration is a usage error even when the secret would also fail the ready gate."""
    vault = _vault()
    added = api.add(name="n", duration="365d", secret=SECRET, vault=vault)
    reads: list[str] = []
    vault.github.get_text_file = lambda p: reads.append(p)  # type: ignore[assignment]

    with pytest.raises(UsageError):
        api.renew(secret_id=added["id"], duration="whenever", vault=vault)

    assert reads == []


def test_renew_explains_a_403_on_the_workflow_path(faked):
    """The same non-obvious scope failure add explains — renew rewrites the workflow too.

    Only for a secret with a delivery address: that is the only kind that has a workflow at all.
    """
    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, "a@b.co")
    vault.github = _relay_then_403(vault.github, ".yml")

    with pytest.raises(VaultError) as exc:
        api.renew_secret(vault=vault, secret=secret, duration="7d")
    assert "workflow" in str(exc.value).lower()
    assert "scope" in str(exc.value).lower()


def test_renewing_a_secret_with_no_delivery_address_needs_no_workflow_scope(faked):
    """It writes no workflow, so a contents-only token renews it fine."""
    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, None)
    vault.github = _relay_then_403(vault.github, ".yml")

    assert api.renew_secret(vault=vault, secret=secret, duration="7d")["id"] == secret.id


def test_renew_never_echoes_the_plaintext_on_failure(faked):
    vault = _vault()
    secret = vault.put_secret("ready", _past(), SECRET, "a@b.co")
    vault.github = _relay_then_403(vault.github, ".yml")

    with pytest.raises(VaultError) as exc:
        api.renew_secret(vault=vault, secret=secret, duration="7d")
    assert SECRET not in json.dumps(exc.value.to_json())


def _relay_then_403(inner, suffix: str):
    """Wrap a FakeGitHub so writes to `suffix` raise a real 403, and everything else passes through."""

    class Relay:
        def __getattr__(self, name):
            return getattr(inner, name)

        def put_file(self, path, content, message):
            if path.endswith(suffix):
                request = httpx.Request("PUT", f"https://api.github.com/repos/o/r/contents/{path}")
                raise httpx.HTTPStatusError(
                    "boom", request=request, response=httpx.Response(403, request=request)
                )
            inner.put_file(path, content, message)

    return Relay()


# ── delete / send_email ──────────────────────────────────────────────────────
def test_delete_removes_ciphertext_metadata_and_workflow(faked):
    vault = _vault()
    secret = vault.put_secret("n", _past(), SECRET, None)

    api.delete_secret(vault=vault, secret=secret)

    assert vault.github.files == {}


def test_delete_types_a_failure_instead_of_leaking_the_exception(faked):
    class Stubborn(FakeGitHub):
        def delete_file(self, path, message):
            raise RuntimeError("boom")

    vault = Vault(Stubborn())
    secret = vault.put_secret("n", _past(), SECRET, None)
    with pytest.raises(VaultError):
        api.delete_secret(vault=vault, secret=secret)


def test_send_email_dispatches_the_unlock_workflow(faked):
    vault = _vault()
    secret = vault.put_secret("n", _past(), SECRET, "a@b.co")

    api.send_email(vault=vault, secret=secret)

    assert vault.github.dispatched == [(f"unlock-{secret.id}.yml", "main")]


def test_send_email_without_a_delivery_address_is_a_usage_error(faked):
    vault = _vault()
    secret = vault.put_secret("n", _past(), SECRET, None)
    with pytest.raises(UsageError):
        api.send_email(vault=vault, secret=secret)
