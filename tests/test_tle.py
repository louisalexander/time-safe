import os
import subprocess

import pytest

from timesafe.timelock import tle


class _Proc:
    def __init__(self, returncode, stdout=b"", stderr=b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_decrypt_too_early_raises_not_yet(monkeypatch):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: _Proc(1, stderr=b"too early to decrypt: expected round 5 > 3 current round"),
    )
    with pytest.raises(tle.NotYetUnlocked):
        tle.decrypt(b"ciphertext", tle="/fake/tle")


def test_decrypt_other_error_raises_tle_error(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(1, stderr=b"boom: bad input"))
    with pytest.raises(tle.TleError):
        tle.decrypt(b"ciphertext", tle="/fake/tle")


def test_decrypt_success_returns_plaintext(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(0, stdout=b"the secret"))
    assert tle.decrypt(b"ciphertext", tle="/fake/tle") == b"the secret"


def test_encrypt_success_returns_ciphertext(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(0, stdout=b"CIPHER"))
    assert tle.encrypt(b"pt", 999999, tle="/fake/tle") == b"CIPHER"


def test_encrypt_failure_raises_tle_error(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Proc(1, stderr=b"nope"))
    with pytest.raises(tle.TleError):
        tle.encrypt(b"pt", 1, tle="/fake/tle")


# ── Live roundtrip (opt-in: needs the real binary + network) ─────────────────
LIVE = os.environ.get("TIMESAFE_LIVE") == "1"


@pytest.mark.skipif(not LIVE, reason="set TIMESAFE_LIVE=1 to run the live drand roundtrip")
def test_live_roundtrip_future_locked_past_unlocks():
    import re

    binary = tle.tle_path()
    meta = subprocess.run([binary, "-m"], capture_output=True, text=True).stdout
    current = int(re.search(r"current:\s*(\d+)", meta).group(1))
    pt = b"live roundtrip"
    # past round decrypts; future round is locked
    past = subprocess.run(
        [binary, "-e", "-f", "-r", str(current - 3)], input=pt, capture_output=True
    ).stdout
    assert tle.decrypt(past, tle=binary) == pt
    future = tle.encrypt(pt, current + 20, tle=binary)
    with pytest.raises(tle.NotYetUnlocked):
        tle.decrypt(future, tle=binary)
