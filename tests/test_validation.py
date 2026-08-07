from datetime import timedelta

import pytest

from timesafe.validation import is_valid_email, is_valid_repo, parse_duration


# ── duration parsing ─────────────────────────────────────────────────────────
def test_parse_duration_units():
    assert parse_duration("30m") == timedelta(minutes=30)
    assert parse_duration("2h") == timedelta(hours=2)
    assert parse_duration("7d") == timedelta(days=7)
    assert parse_duration("90s") == timedelta(seconds=90)
    assert parse_duration("1d12h") == timedelta(days=1, hours=12)
    assert parse_duration(" 2h ") == timedelta(hours=2)
    assert parse_duration("5") == timedelta(days=5)  # bare number = days


def test_parse_duration_rejects_bad_input():
    for bad in [None, "", "abc", "5x", "-3d", "0", "1.5h", "d"]:
        with pytest.raises(ValueError):
            parse_duration(bad)


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


# ── the screens still expose these, so the TUI keeps working ─────────────────
def test_screens_reexport_the_same_objects():
    from timesafe.screens import add_secret, init_vault

    assert add_secret.parse_duration is parse_duration
    assert add_secret.is_valid_email is is_valid_email
    assert init_vault.is_valid_repo is is_valid_repo
