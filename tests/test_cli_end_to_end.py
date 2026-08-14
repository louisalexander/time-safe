"""End-to-end tests: the real `timesafe` entry point, in a real subprocess, over real pipes.

These are the only tests that can prove the contract that actually matters to a cron job — no TTY,
stdin and stdout as pipes, byte-exact output, and documented exit codes. Everything is hermetic:
GitHub is a local stub and `tle` is a stub binary, so there is no network and no real crypto.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone

import pytest

from tests.stub_github import REPO, StubGitHub

SECRET = "correct-horse-battery-staple"

STUB_TLE = textwrap.dedent(
    """\
    #!%(python)s
    import sys
    args = sys.argv[1:]
    data = sys.stdin.buffer.read()
    # The marker is deliberately not valid UTF-8: real tlock ciphertext is binary, and the stub
    # GitHub reproduces the Contents API's habit of mangling anything that isn't text. Keeping the
    # ciphertext genuinely binary is what makes these tests notice if a read stops being byte-exact.
    if "-e" in args:
        sys.stdout.buffer.write(b"CT:\\xff\\x00" + data)
    elif "-d" in args:
        if not data.startswith(b"CT:\\xff\\x00"):
            sys.stderr.write("too early to decrypt")
            sys.exit(1)
        sys.stdout.buffer.write(data[5:])
    sys.exit(0)
    """
)


@pytest.fixture
def tle_stub(tmp_path):
    path = tmp_path / "tle"
    path.write_text(STUB_TLE % {"python": sys.executable})
    path.chmod(0o755)
    return path


@pytest.fixture
def github():
    with StubGitHub() as stub:
        yield stub


@pytest.fixture
def env(github, tle_stub, tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "TIMESAFE_GITHUB_API": github.url,
        "TIMESAFE_GITHUB_TOKEN": "ghp_stub_token",
        "TIMESAFE_VAULT": REPO,
        "TIMESAFE_TLE": str(tle_stub),
        "PYTHONPATH": str(tmp_path.parent),
    }


def run(env, args, stdin=b""):
    """Invoke the installed console script the way a cron job would: pipes on all three streams."""
    return subprocess.run(
        [sys.executable, "-m", "timesafe", *args],
        input=stdin,
        capture_output=True,
        env={**env, "PYTHONPATH": ""},
        cwd=_repo_root(),
    )


def _repo_root():
    from pathlib import Path

    return str(Path(__file__).resolve().parents[1])


def _add(env, name="break-glass", duration="10d", secret=SECRET):
    proc = run(env, ["add", "--name", name, "--duration", duration, "--secret-stdin"], secret.encode())
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


# ── the happy path ───────────────────────────────────────────────────────────
def test_add_over_a_pipe_prints_json_and_exits_zero(env):
    proc = run(
        env,
        ["add", "--name", "break-glass", "--duration", "10d", "--secret-stdin"],
        SECRET.encode(),
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["name"] == "break-glass"
    assert payload["pushed"] is True
    assert proc.stderr == b""


def test_the_secret_never_appears_in_the_process_arguments(env):
    # There is no flag that could carry it, so `ps` can never show it.
    proc = run(env, ["add", "--name", "n", "--duration", "1d", "--secret", SECRET])
    assert proc.returncode == 2
    assert SECRET.encode() not in proc.stdout
    assert SECRET.encode() not in proc.stderr


def test_status_round_trips_the_id_from_add(env):
    added = _add(env)
    proc = run(env, ["status", "--id", added["id"], "--json"])

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["id"] == added["id"]
    assert payload["ready"] is False
    assert payload["seconds_remaining"] > 0


def test_list_shows_the_added_secret(env):
    added = _add(env)
    proc = run(env, ["list", "--json"])
    assert proc.returncode == 0, proc.stderr
    assert [row["id"] for row in json.loads(proc.stdout)] == [added["id"]]


# ── the contract that matters to cron ────────────────────────────────────────
def test_reveal_writes_the_plaintext_with_no_trailing_newline(env, github):
    added = _add(env)
    _make_ready(github, added["id"])

    proc = run(env, ["reveal", "--id", added["id"]])

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == SECRET.encode()  # byte-exact: no newline, no decoration
    assert proc.stderr == b""


def test_reveal_of_a_locked_secret_exits_three_with_empty_stdout(env):
    added = _add(env)

    proc = run(env, ["reveal", "--id", added["id"]])

    assert proc.returncode == 3
    assert proc.stdout == b""
    assert json.loads(proc.stderr)["code"] == "not_ready"


def test_reveal_of_an_unknown_id_exits_five(env):
    _add(env)
    proc = run(env, ["reveal", "--id", "00000000-0000-0000-0000-000000000000"])
    assert proc.returncode == 5
    assert proc.stdout == b""
    assert json.loads(proc.stderr)["code"] == "not_found"


def test_empty_stdin_exits_two(env):
    proc = run(env, ["add", "--name", "n", "--duration", "1d", "--secret-stdin"], b"")
    assert proc.returncode == 2
    assert json.loads(proc.stderr)["code"] == "empty_stdin"


def test_a_secret_survives_the_pipe_byte_for_byte(env, github):
    tricky = 'line1\nline2\ttab "quoted" \\backslash\\ £ é 🔐'
    proc = run(
        env,
        ["add", "--name", "tricky", "--duration", "1d", "--secret-stdin"],
        tricky.encode() + b"\n",  # the one trailing newline a shell would add
    )
    assert proc.returncode == 0, proc.stderr
    added = json.loads(proc.stdout)
    _make_ready(github, added["id"])

    revealed = run(env, ["reveal", "--id", added["id"]])

    assert revealed.stdout.decode() == tricky


def test_no_vault_configured_exits_two(env):
    proc = run({**env, "TIMESAFE_VAULT": ""}, ["status", "--json"])
    assert proc.returncode == 2
    assert json.loads(proc.stderr)["code"] == "usage"


def test_no_token_configured_exits_four(env):
    proc = run({**env, "TIMESAFE_GITHUB_TOKEN": ""}, ["status", "--json"])
    assert proc.returncode == 4
    assert json.loads(proc.stderr)["code"] == "vault"


def test_help_exits_zero_without_a_vault(env):
    # What the CI image smoke test runs.
    proc = run({**env, "TIMESAFE_VAULT": "", "TIMESAFE_GITHUB_TOKEN": ""}, ["--help"])
    assert proc.returncode == 0
    assert b"reveal" in proc.stdout


def test_a_failure_never_prints_a_traceback(env):
    proc = run({**env, "TIMESAFE_GITHUB_API": "http://127.0.0.1:1"}, ["status", "--json"])
    assert proc.returncode in (4, 5)
    assert b"Traceback" not in proc.stderr
    assert json.loads(proc.stderr)["code"] in ("vault", "network")


def test_stdout_stays_parseable_when_piped_through_a_shell(env):
    """`timesafe status --json | python -c ...` must see nothing but JSON."""
    _add(env)
    proc = run(env, ["status", "--json"])
    assert proc.returncode == 0
    rows = json.loads(proc.stdout)
    assert isinstance(rows, list)


# ── delete / renew / send / link-gmail over the wire ─────────────────────────
def test_delete_without_yes_leaves_the_secret_alone(env, github):
    added = _add(env)
    proc = run(env, ["delete", "--id", added["id"]])

    assert proc.returncode == 2
    assert json.loads(proc.stderr)["code"] == "usage"
    assert f"vault/secrets/{added['id']}.tle" in github.files


def test_delete_with_yes_removes_every_file(env, github):
    added = _add(env)
    proc = run(env, ["delete", "--id", added["id"], "--yes", "--json"])

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["deleted"] is True
    assert not [p for p in github.files if added["id"] in p]


def test_renew_of_a_ready_secret_pushes_a_new_round(env, github):
    added = _add(env)
    _make_ready(github, added["id"])

    proc = run(env, ["renew", "--id", added["id"], "--duration", "30d", "--json"])

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["renewed"] is True
    assert payload["round"] > 0
    meta = json.loads(github.files[f"vault/secrets/{added['id']}.meta"].decode())
    assert meta["drand_round"] == payload["round"]


def test_renew_of_a_locked_secret_exits_three_and_writes_nothing(env, github):
    added = _add(env)
    before = dict(github.files)

    proc = run(env, ["renew", "--id", added["id"], "--duration", "30d"])

    assert proc.returncode == 3
    assert proc.stdout == b""
    assert json.loads(proc.stderr)["code"] == "not_ready"
    assert github.files == before


def test_renew_never_writes_the_plaintext_to_either_stream(env, github):
    added = _add(env)
    _make_ready(github, added["id"])

    proc = run(env, ["renew", "--id", added["id"], "--duration", "30d", "--json"])

    assert SECRET.encode() not in proc.stdout
    assert SECRET.encode() not in proc.stderr


def test_send_dispatches_the_workflow(env, github):
    added = _add(env, name="mailed")
    # `add --email` is the supported route; rewrite the meta so we do not depend on it here.
    _set_delivery_email(github, added["id"], "a@b.co")

    proc = run(env, ["send", "--id", added["id"], "--json"])

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["dispatched"] is True
    assert github.dispatched == [(f"unlock-{added['id']}.yml", "main")]


def test_send_without_a_delivery_address_exits_two(env):
    added = _add(env)
    proc = run(env, ["send", "--id", added["id"]])
    assert proc.returncode == 2
    assert json.loads(proc.stderr)["code"] == "usage"


def test_link_gmail_seals_the_credentials_into_actions_secrets(env, github):
    from tests.stub_github import unseal

    proc = run(
        {**env, "TIMESAFE_OAUTH_CLIENT_SECRET": "the-client-secret"},
        ["link-gmail", "--gmail", "vault@gmail.com", "--client-id", "cid", "--token-stdin", "--json"],
        b"1//the-refresh-token\n",
    )

    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["linked"] is True
    assert unseal(github.actions_secrets["GMAIL_REFRESH_TOKEN"]) == "1//the-refresh-token"
    assert unseal(github.actions_secrets["OAUTH_CLIENT_SECRET"]) == "the-client-secret"
    # Sealed on the way out, and never echoed back on the way in.
    assert b"1//the-refresh-token" not in proc.stdout
    assert b"the-client-secret" not in proc.stdout


def test_link_gmail_without_the_client_secret_in_the_environment_exits_two(env):
    proc = run(env, ["link-gmail", "--gmail", "v@gmail.com", "--client-id", "cid", "--token-stdin"],
               b"1//rt")
    assert proc.returncode == 2
    assert b"TIMESAFE_OAUTH_CLIENT_SECRET" in proc.stderr


def _set_delivery_email(github, secret_id, email):
    path = f"vault/secrets/{secret_id}.meta"
    meta = json.loads(github.files[path].decode())
    meta["delivery_email"] = email
    github.files[path] = json.dumps(meta).encode()


def _make_ready(github, secret_id):
    """Rewrite the stored metadata so the secret's unlock time is in the past."""
    path = f"vault/secrets/{secret_id}.meta"
    meta = json.loads(github.files[path].decode())
    meta["unlock_at"] = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    github.files[path] = json.dumps(meta).encode()
