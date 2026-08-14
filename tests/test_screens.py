from datetime import datetime, timedelta, timezone

import pytest

from timesafe.config.registry import VaultRef
from timesafe.errors import (
    NetworkError,
    NotFoundError,
    NotReadyError,
    UsageError,
    VaultError,
)
from timesafe.screens.errors import message_of, severity_of
from timesafe.screens.secret_detail import visible_actions
from timesafe.screens.secrets_list import SecretsListScreen, status_text
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


# ── list rows ────────────────────────────────────────────────────────────────
def _row(secret) -> str:
    return SecretsListScreen(object(), VaultRef("v", "o/r"))._row_text(secret)


def test_a_row_marks_a_secret_that_will_email_itself():
    """Whether a secret delivers on unlock is its most consequential fact, and it was invisible."""
    assert "✉" in _row(_secret(ready=False, email="a@b.co"))
    assert "✉" not in _row(_secret(ready=False, email=None))


# ── typed errors → what the TUI says ─────────────────────────────────────────
@pytest.mark.parametrize(
    "exc, severity",
    [
        (NotReadyError("wait"), "warning"),  # nothing is wrong
        (NetworkError("blip"), "warning"),  # the vault is fine; retry
        (NotFoundError("gone"), "warning"),  # refresh the list
        (VaultError("bad scope"), "error"),  # the user has to fix something
        (UsageError("no address"), "error"),
    ],
)
def test_severity_follows_the_error_code(exc, severity):
    assert severity_of(exc) == severity


def test_a_not_ready_error_says_how_long_the_wait_is():
    """'Ready in 4m 12s' is actionable; 'not unlocked yet' is not."""
    exc = NotReadyError("Locked.", id="x", seconds_remaining=252)
    assert message_of(exc) == "Locked. Ready in 4m 12s."


def test_an_error_without_a_countdown_is_left_alone():
    assert message_of(VaultError("Nope.")) == "Nope."


def test_a_row_carries_the_absolute_unlock_date_as_well_as_the_countdown():
    secret = _secret(ready=False)
    row = _row(secret)
    assert secret.unlock_at.astimezone().strftime("%Y-%m-%d") in row
    assert status_text(secret) in row
