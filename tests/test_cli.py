import io
import json
from datetime import datetime, timedelta, timezone

import pytest

from tests.fakes import FakeGitHub
from timesafe import cli
from timesafe.vault.vault import Vault

SECRET = "correct-horse-battery-staple"


class _Tty(io.BytesIO):
    def isatty(self):
        return True


def run(argv, stdin=b"", vault=None):
    out, err = io.BytesIO(), io.BytesIO()
    stream = stdin if hasattr(stdin, "read") else io.BytesIO(stdin)
    code = cli.main(argv, stdin=stream, stdout=out, stderr=err, vault=vault)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def vault(faked):
    return Vault(FakeGitHub())


def _add(vault, name="n", duration="1d", secret=SECRET):
    code, out, _ = run(
        ["add", "--name", name, "--duration", duration, "--secret-stdin"],
        stdin=secret.encode(),
        vault=vault,
    )
    assert code == 0
    return json.loads(out)


def _ready_secret(vault, name="ready", plaintext=SECRET):
    return vault.put_secret(name, datetime.now(timezone.utc) - timedelta(seconds=5), plaintext, None)


# ── add ──────────────────────────────────────────────────────────────────────
def test_add_prints_json_and_exits_zero(vault):
    code, out, err = run(
        ["add", "--name", "break-glass", "--duration", "10d", "--secret-stdin"],
        stdin=SECRET.encode(),
        vault=vault,
    )

    assert code == 0
    assert err == b""
    payload = json.loads(out)
    assert set(payload) == {"id", "name", "unlock_at", "round", "vault_path", "pushed"}
    assert payload["name"] == "break-glass"


def test_add_strips_exactly_one_trailing_newline(vault):
    # `echo secret |` appends one \n; that shouldn't become part of the secret.
    added = _add(vault, secret="hunter2")
    code, out, _ = run(["reveal", "--id", added["id"]], vault=vault)
    assert code == 3  # still locked, but the write already happened

    ready = vault.put_secret("x", datetime.now(timezone.utc) - timedelta(seconds=5), "hunter2", None)
    _, plain, _ = run(["reveal", "--id", ready.id], vault=vault)
    assert plain == b"hunter2"


def test_add_preserves_a_secret_that_legitimately_ends_in_whitespace(vault):
    code, out, _ = run(
        ["add", "--name", "n", "--duration", "1d", "--secret-stdin"],
        stdin=b"two spaces  \n",
        vault=vault,
    )
    assert code == 0
    secret_id = json.loads(out)["id"]
    stored = next(s for s in vault.list_secrets() if s.id == secret_id)
    stored.unlock_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    assert vault.reveal(stored) == "two spaces  "


def test_add_strips_a_windows_line_ending_whole(vault):
    code, out, _ = run(
        ["add", "--name", "n", "--duration", "1d", "--secret-stdin"],
        stdin=b"windows\r\n",
        vault=vault,
    )
    stored = next(s for s in vault.list_secrets() if s.id == json.loads(out)["id"])
    stored.unlock_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    assert vault.reveal(stored) == "windows"


def test_add_with_empty_stdin_is_a_usage_error(vault):
    code, out, err = run(
        ["add", "--name", "n", "--duration", "1d", "--secret-stdin"], stdin=b"", vault=vault
    )
    assert code == 2
    assert out == b""
    assert json.loads(err)["code"] == "empty_stdin"


def test_add_with_only_a_newline_on_stdin_is_empty(vault):
    code, _, err = run(
        ["add", "--name", "n", "--duration", "1d", "--secret-stdin"], stdin=b"\n", vault=vault
    )
    assert code == 2
    assert json.loads(err)["code"] == "empty_stdin"


def test_add_refuses_a_tty_rather_than_blocking(vault):
    # Blocking on a terminal read would hang a cron job forever.
    code, _, err = run(
        ["add", "--name", "n", "--duration", "1d", "--secret-stdin"], stdin=_Tty(), vault=vault
    )
    assert code == 2
    assert "stdin" in json.loads(err)["error"].lower()


def test_add_rejects_non_utf8_stdin(vault):
    code, _, err = run(
        ["add", "--name", "n", "--duration", "1d", "--secret-stdin"],
        stdin=b"\xff\xfe\x00binary",
        vault=vault,
    )
    assert code == 2
    assert json.loads(err)["code"] == "usage"


def test_add_takes_no_positional_arguments(vault):
    code, _, _ = run(
        ["add", "--name", "n", "--duration", "1d", "--secret-stdin", SECRET], vault=vault
    )
    assert code == 2


def test_a_secret_typed_as_a_positional_is_never_echoed_back(vault):
    # argparse's default "unrecognized arguments: X" would print the secret. It must not.
    code, out, err = run(
        ["add", "--name", "n", "--duration", "1d", "--secret-stdin", SECRET], vault=vault
    )
    assert code == 2
    assert SECRET.encode() not in out
    assert SECRET.encode() not in err


def test_there_is_no_flag_for_passing_a_secret_inline(vault):
    code, _, _ = run(["add", "--name", "n", "--duration", "1d", "--secret", SECRET], vault=vault)
    assert code == 2


def test_add_rejects_a_bad_duration(vault):
    code, _, err = run(
        ["add", "--name", "n", "--duration", "whenever", "--secret-stdin"],
        stdin=SECRET.encode(),
        vault=vault,
    )
    assert code == 2
    assert json.loads(err)["code"] == "usage"


# ── status ───────────────────────────────────────────────────────────────────
def test_status_by_id_as_json(vault):
    added = _add(vault)
    code, out, _ = run(["status", "--id", added["id"], "--json"], vault=vault)

    assert code == 0
    payload = json.loads(out)
    assert set(payload) == {"id", "name", "unlock_at", "ready", "seconds_remaining"}
    assert payload["ready"] is False


def test_status_without_a_selector_lists_every_secret(vault):
    _add(vault, name="a")
    _add(vault, name="b")
    code, out, _ = run(["status", "--json"], vault=vault)
    assert code == 0
    assert {row["name"] for row in json.loads(out)} == {"a", "b"}


def test_status_without_json_prints_a_human_table(vault):
    _add(vault, name="break-glass")
    code, out, _ = run(["status"], vault=vault)
    assert code == 0
    assert b"break-glass" in out
    assert not out.startswith(b"{")


def test_status_for_an_unknown_id_exits_five(vault):
    code, out, err = run(["status", "--id", "nope", "--json"], vault=vault)
    assert code == 5
    assert out == b""
    assert json.loads(err)["code"] == "not_found"


def test_status_of_a_ready_secret_reports_zero_remaining(vault):
    secret = _ready_secret(vault)
    code, out, _ = run(["status", "--id", secret.id, "--json"], vault=vault)
    assert code == 0
    assert json.loads(out) == {
        "id": secret.id,
        "name": "ready",
        "unlock_at": secret.unlock_at.astimezone(timezone.utc).isoformat(),
        "ready": True,
        "seconds_remaining": 0,
    }


# ── reveal ───────────────────────────────────────────────────────────────────
def test_reveal_prints_only_the_plaintext_with_no_trailing_newline(vault):
    secret = _ready_secret(vault, plaintext="s3cr3t")
    code, out, err = run(["reveal", "--id", secret.id], vault=vault)

    assert code == 0
    assert out == b"s3cr3t"
    assert err == b""


def test_reveal_of_a_locked_secret_exits_three_with_nothing_on_stdout(vault):
    added = _add(vault)
    code, out, err = run(["reveal", "--id", added["id"]], vault=vault)

    assert code == 3
    assert out == b""
    assert json.loads(err)["code"] == "not_ready"


def test_reveal_ignores_json_rather_than_rejecting_it(vault):
    # The flag exists on every command for uniform scripting, but reveal still prints raw plaintext.
    secret = _ready_secret(vault, plaintext="s3cr3t")
    code, out, _ = run(["reveal", "--id", secret.id, "--json"], vault=vault)
    assert code == 0
    assert out == b"s3cr3t"


def test_reveal_for_an_unknown_id_exits_five(vault):
    code, _, err = run(["reveal", "--id", "nope"], vault=vault)
    assert code == 5
    assert json.loads(err)["code"] == "not_found"


def test_reveal_needs_a_selector(vault):
    code, _, err = run(["reveal"], vault=vault)
    assert code == 2
    assert json.loads(err)["code"] == "usage"


# ── name lookup ──────────────────────────────────────────────────────────────
def test_a_duplicate_name_exits_two_and_lists_the_candidate_ids(vault):
    first = _add(vault, name="dup")
    second = _add(vault, name="dup", duration="2d")

    code, out, err = run(["reveal", "--name", "dup"], vault=vault)

    assert code == 2
    assert out == b""
    payload = json.loads(err)
    assert payload["code"] == "ambiguous_name"
    assert sorted(payload["ids"]) == sorted([first["id"], second["id"]])


# ── list ─────────────────────────────────────────────────────────────────────
def test_list_json_carries_the_full_metadata(vault):
    added = _add(vault)
    code, out, _ = run(["list", "--json"], vault=vault)
    assert code == 0
    (row,) = json.loads(out)
    assert row["id"] == added["id"]
    assert set(row) == {
        "id", "name", "unlock_at", "created_at", "round", "chain", "delivery_email", "ready",
    }


def test_list_of_an_empty_vault_is_an_empty_array(vault):
    code, out, _ = run(["list", "--json"], vault=vault)
    assert code == 0
    assert json.loads(out) == []


# ── delete ───────────────────────────────────────────────────────────────────
def test_delete_needs_yes_and_changes_nothing_without_it(vault):
    added = _add(vault)
    code, out, err = run(["delete", "--id", added["id"]], vault=vault)

    assert code == 2
    assert out == b""
    assert json.loads(err)["code"] == "usage"
    assert [s.id for s in vault.list_secrets()] == [added["id"]]


def test_delete_with_yes_removes_the_secret(vault):
    added = _add(vault)
    code, out, err = run(["delete", "--id", added["id"], "--yes", "--json"], vault=vault)

    assert code == 0
    assert err == b""
    assert json.loads(out) == {"id": added["id"], "name": "n", "deleted": True}
    assert vault.list_secrets() == []


def test_delete_without_json_prints_a_human_line(vault):
    added = _add(vault)
    code, out, _ = run(["delete", "--id", added["id"], "--yes"], vault=vault)
    assert code == 0
    assert added["id"].encode() in out
    assert not out.startswith(b"{")


def test_delete_of_an_unknown_id_exits_five(vault):
    code, _, err = run(["delete", "--id", "nope", "--yes"], vault=vault)
    assert code == 5
    assert json.loads(err)["code"] == "not_found"


def test_delete_refuses_to_run_without_a_selector(vault):
    # A bare `delete --yes` must never mean "everything".
    _add(vault)
    code, _, err = run(["delete", "--yes"], vault=vault)
    assert code == 2
    assert json.loads(err)["code"] == "usage"
    assert len(vault.list_secrets()) == 1


# ── renew ────────────────────────────────────────────────────────────────────
def test_renew_re_locks_a_ready_secret(vault):
    secret = _ready_secret(vault, plaintext="s3cr3t")
    code, out, err = run(["renew", "--id", secret.id, "--duration", "2h", "--json"], vault=vault)

    assert code == 0
    assert err == b""
    payload = json.loads(out)
    assert payload["id"] == secret.id
    assert payload["renewed"] is True
    assert datetime.fromisoformat(payload["unlock_at"]) > datetime.now(timezone.utc)


def test_renew_of_a_locked_secret_exits_three_like_reveal(vault):
    added = _add(vault)
    code, out, err = run(["renew", "--id", added["id"], "--duration", "2h"], vault=vault)

    assert code == 3
    assert out == b""
    assert json.loads(err)["code"] == "not_ready"


def test_renew_requires_a_duration(vault):
    secret = _ready_secret(vault)
    code, _, err = run(["renew", "--id", secret.id], vault=vault)
    assert code == 2
    assert json.loads(err)["code"] == "usage"


def test_renew_rejects_a_bad_duration(vault):
    secret = _ready_secret(vault)
    code, _, err = run(["renew", "--id", secret.id, "--duration", "whenever"], vault=vault)
    assert code == 2
    assert json.loads(err)["code"] == "usage"


def test_renew_never_prints_the_plaintext_it_had_to_decrypt(vault):
    secret = _ready_secret(vault, plaintext=SECRET)
    code, out, err = run(["renew", "--id", secret.id, "--duration", "1d", "--json"], vault=vault)
    assert code == 0
    assert SECRET.encode() not in out
    assert SECRET.encode() not in err


# ── send ─────────────────────────────────────────────────────────────────────
def test_send_dispatches_the_delivery_workflow(vault):
    secret = vault.put_secret("n", datetime.now(timezone.utc) + timedelta(days=1), SECRET, "a@b.co")
    code, out, err = run(["send", "--id", secret.id, "--json"], vault=vault)

    assert code == 0
    assert err == b""
    assert json.loads(out)["dispatched"] is True
    assert vault.github.dispatched == [(f"unlock-{secret.id}.yml", "main")]


def test_send_of_a_secret_with_no_email_is_a_usage_error(vault):
    added = _add(vault)
    code, _, err = run(["send", "--id", added["id"]], vault=vault)
    assert code == 2
    assert json.loads(err)["code"] == "usage"
    assert vault.github.dispatched == []


def test_send_of_an_unknown_id_exits_five(vault):
    code, _, err = run(["send", "--id", "nope"], vault=vault)
    assert code == 5
    assert json.loads(err)["code"] == "not_found"


# ── link-gmail ───────────────────────────────────────────────────────────────
def _gmail_env(monkeypatch, secret="csec"):
    monkeypatch.setenv(cli.GMAIL_CLIENT_SECRET_ENV, secret)


def test_link_gmail_reads_the_refresh_token_from_stdin(vault, monkeypatch):
    _gmail_env(monkeypatch)
    code, out, err = run(
        ["link-gmail", "--gmail", "v@gmail.com", "--client-id", "cid", "--token-stdin", "--json"],
        stdin=b"1//refresh\n",
        vault=vault,
    )

    assert code == 0
    assert err == b""
    assert json.loads(out)["linked"] is True
    assert vault.github.secrets["GMAIL_REFRESH_TOKEN"] == ("sealed:1//refresh", "kid")


def test_link_gmail_never_echoes_the_refresh_token(vault, monkeypatch):
    _gmail_env(monkeypatch)
    _, out, err = run(
        ["link-gmail", "--gmail", "v@gmail.com", "--client-id", "cid", "--token-stdin", "--json"],
        stdin=b"1//refresh",
        vault=vault,
    )
    assert b"1//refresh" not in out
    assert b"1//refresh" not in err
    assert b"csec" not in out


def test_link_gmail_without_a_client_secret_is_a_usage_error(vault, monkeypatch):
    monkeypatch.delenv(cli.GMAIL_CLIENT_SECRET_ENV, raising=False)
    code, _, err = run(
        ["link-gmail", "--gmail", "v@gmail.com", "--client-id", "cid", "--token-stdin"],
        stdin=b"1//refresh",
        vault=vault,
    )
    assert code == 2
    assert cli.GMAIL_CLIENT_SECRET_ENV.encode() in err


def test_link_gmail_with_empty_stdin_is_a_usage_error(vault, monkeypatch):
    _gmail_env(monkeypatch)
    code, _, err = run(
        ["link-gmail", "--gmail", "v@gmail.com", "--client-id", "cid", "--token-stdin"],
        stdin=b"",
        vault=vault,
    )
    assert code == 2
    assert json.loads(err)["code"] == "empty_stdin"


def test_link_gmail_takes_no_flag_that_could_carry_the_refresh_token(vault, monkeypatch):
    _gmail_env(monkeypatch)
    code, _, _ = run(
        ["link-gmail", "--gmail", "v@gmail.com", "--client-id", "cid", "--refresh-token", "1//rt"],
        vault=vault,
    )
    assert code == 2


def test_link_gmail_rejects_a_malformed_address(vault, monkeypatch):
    _gmail_env(monkeypatch)
    code, _, err = run(
        ["link-gmail", "--gmail", "nope", "--client-id", "cid", "--token-stdin"],
        stdin=b"1//rt",
        vault=vault,
    )
    assert code == 2
    assert json.loads(err)["code"] == "usage"


# ── framing ──────────────────────────────────────────────────────────────────
def test_help_exits_zero(vault):
    code, out, _ = run(["--help"], vault=vault)
    assert code == 0
    assert b"add" in out


def test_no_subcommand_is_a_usage_error(vault):
    code, _, err = run([], vault=vault)
    assert code == 2
    assert json.loads(err)["code"] == "usage"


def test_unknown_subcommand_does_not_echo_the_argument(vault):
    code, _, err = run(["frobnicate"], vault=vault)
    assert code == 2
    assert b"frobnicate" not in err


def test_version_exits_zero(vault):
    code, out, _ = run(["--version"], vault=vault)
    assert code == 0
    assert out.strip()


def test_an_unexpected_failure_exits_four_without_a_traceback(vault, monkeypatch):
    def boom(**kwargs):
        raise ZeroDivisionError("internal detail")

    monkeypatch.setattr("timesafe.cli.api.list_secrets", boom)

    code, out, err = run(["list", "--json"], vault=vault)

    assert code == 4
    assert out == b""
    assert b"Traceback" not in err
    assert b"ZeroDivisionError" not in err
    assert json.loads(err)["code"] == "vault"


def test_errors_go_to_stderr_never_stdout(vault):
    _, out, err = run(["status", "--id", "nope", "--json"], vault=vault)
    assert out == b""
    assert err


def test_json_output_ends_with_a_newline_so_line_readers_work(vault):
    added = _add(vault)
    _, out, _ = run(["status", "--id", added["id"], "--json"], vault=vault)
    assert out.endswith(b"\n")
