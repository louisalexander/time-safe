from datetime import datetime, timedelta, timezone

from timesafe.screens.init_vault import describe_github_error
from timesafe.screens.secret_detail import visible_actions
from timesafe.screens.secrets_list import status_text
from timesafe.vault.secret import Secret

# parse_duration / is_valid_email / is_valid_repo now live in timesafe.validation —
# see tests/test_validation.py.


def _secret(ready: bool, email="a@b.co"):
    when = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
        if ready
        else datetime.now(timezone.utc) + timedelta(days=2)
    )
    return Secret.create("S", when, 1, "chain", email)


# ── secret-detail gating ─────────────────────────────────────────────────────
def test_locked_hides_reveal_email_renew():
    actions = visible_actions(_secret(ready=False))
    assert "reveal" not in actions
    assert "email" not in actions
    assert "renew" not in actions
    assert "delete" in actions


def test_ready_shows_reveal_email_renew_delete():
    actions = visible_actions(_secret(ready=True))
    assert actions == ["reveal", "email", "renew", "delete"]


def test_ready_without_email_still_has_reveal_and_renew():
    actions = visible_actions(_secret(ready=True, email=None))
    assert actions == ["reveal", "renew", "delete"]


def test_no_extend_action_ever():
    assert "extend" not in visible_actions(_secret(ready=True))


# ── status text ──────────────────────────────────────────────────────────────
def test_status_text_ready():
    assert status_text(_secret(ready=True)) == "● ready"


def test_status_text_countdown_shows_days():
    s = _secret(ready=False)  # ~2 days out
    assert "d " in status_text(s)


def test_status_text_short_durations_tick_in_seconds():
    now = datetime.now(timezone.utc)
    s = Secret.create("S", now + timedelta(seconds=90), 1, "c", None)
    assert status_text(s, now) == "1m 30s"


def test_describe_github_error():
    assert "404" in describe_github_error(Exception("GitHub API 404 GET /repos/x"))
    assert "403" in describe_github_error(Exception("GitHub API 403"))
