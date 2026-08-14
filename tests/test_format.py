from datetime import datetime, timedelta, timezone

from timesafe.cli import _humanize
from timesafe.format import humanize_seconds
from timesafe.screens.secrets_list import status_text
from timesafe.vault.secret import Secret


def test_units_are_largest_first():
    assert humanize_seconds(3 * 86400 + 4 * 3600 + 7 * 60 + 9) == "3d 4h 07m"
    assert humanize_seconds(4 * 3600 + 7 * 60 + 9) == "4h 07m 09s"
    assert humanize_seconds(7 * 60 + 9) == "7m 09s"
    assert humanize_seconds(9) == "9s"


def test_ready_wording_is_the_callers_choice():
    assert humanize_seconds(0) == "-"
    assert humanize_seconds(-5) == "-"
    assert humanize_seconds(0, ready="● ready") == "● ready"


def test_tui_and_cli_render_the_same_countdown():
    """The point of the shared formatter: one secret, one moment, one string."""
    now = datetime.now(timezone.utc)
    secret = Secret.create("S", now + timedelta(days=3, hours=4, minutes=7, seconds=9), 1, "c", None)
    remaining = int((secret.unlock_at - now).total_seconds())
    assert status_text(secret, now) == _humanize(remaining)
