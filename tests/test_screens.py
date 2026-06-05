from datetime import datetime, timedelta, timezone

from timesafe.screens.add_secret import is_valid_email
from timesafe.screens.init_vault import describe_github_error, is_valid_repo
from timesafe.screens.secret_detail import visible_actions
from timesafe.screens.secrets_list import status_text
from timesafe.vault.secret import Secret


def _secret(ready: bool, email="a@b.co"):
    when = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
        if ready
        else datetime.now(timezone.utc) + timedelta(days=2)
    )
    return Secret.create("S", when, 1, "chain", email)


# ── secret-detail gating ─────────────────────────────────────────────────────
def test_locked_hides_reveal_and_email():
    actions = visible_actions(_secret(ready=False))
    assert "reveal" not in actions
    assert "email" not in actions
    assert "delete" in actions


def test_ready_shows_reveal_and_email():
    actions = visible_actions(_secret(ready=True))
    assert actions == ["reveal", "email", "delete"]


def test_ready_without_email_hides_email():
    actions = visible_actions(_secret(ready=True, email=None))
    assert "reveal" in actions
    assert "email" not in actions


def test_no_extend_action_ever():
    assert "extend" not in visible_actions(_secret(ready=True))


# ── status text ──────────────────────────────────────────────────────────────
def test_status_text_ready():
    assert status_text(_secret(ready=True)) == "● ready"


def test_status_text_countdown_shows_days():
    s = _secret(ready=False)  # ~2 days out
    assert "d " in status_text(s)


# ── validators ───────────────────────────────────────────────────────────────
def test_is_valid_email():
    assert is_valid_email("a@b.co")
    assert is_valid_email("u+t@sub.example.org")
    for bad in [None, "", "a", "a@b", "a@b.", "@b.co", "a b@c.co", "a@b@c.co"]:
        assert not is_valid_email(bad)


def test_is_valid_repo():
    assert is_valid_repo("owner/repo")
    for bad in [None, "", "ownerrepo", "o/r/x", "o /r", "/r", "r/"]:
        assert not is_valid_repo(bad)


def test_describe_github_error():
    assert "404" in describe_github_error(Exception("GitHub API 404 GET /repos/x"))
    assert "403" in describe_github_error(Exception("GitHub API 403"))
