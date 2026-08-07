import os
import subprocess
import sys
from pathlib import Path

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


# ── binary resolution ────────────────────────────────────────────────────────
@pytest.fixture
def isolated_chain(monkeypatch, tmp_path):
    """Neutralise every real lookup source so each test can enable exactly one."""
    monkeypatch.delenv("TIMESAFE_TLE", raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(tle, "_PACKAGED_BIN", tmp_path / "nonexistent-pkg")
    monkeypatch.setattr(tle, "_PROJECT_TOOLS", tmp_path / "nonexistent-tools")
    monkeypatch.setattr(tle.shutil, "which", lambda _: None)
    return tmp_path


def _executable(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    return path


def test_env_override_wins_over_everything(isolated_chain, monkeypatch):
    packaged = _executable(isolated_chain / "pkg" / "tle")
    monkeypatch.setattr(tle, "_PACKAGED_BIN", packaged.parent)
    override = _executable(isolated_chain / "override" / "tle")
    monkeypatch.setenv("TIMESAFE_TLE", str(override))

    assert tle.tle_path() == str(override)


def test_frozen_bundle_beats_the_packaged_wheel_copy(isolated_chain, monkeypatch):
    packaged = _executable(isolated_chain / "pkg" / "tle")
    monkeypatch.setattr(tle, "_PACKAGED_BIN", packaged.parent)
    frozen = _executable(isolated_chain / "meipass" / "tle")
    monkeypatch.setattr(sys, "_MEIPASS", str(frozen.parent), raising=False)

    assert tle.tle_path() == str(frozen)


def test_packaged_binary_beats_whatever_is_on_path(isolated_chain, monkeypatch):
    packaged = _executable(isolated_chain / "pkg" / "tle")
    monkeypatch.setattr(tle, "_PACKAGED_BIN", packaged.parent)
    monkeypatch.setattr(tle.shutil, "which", lambda _: "/usr/local/bin/tle")

    # A stray host `tle` of unknown version must never shadow the pinned one we shipped.
    assert tle.tle_path() == str(packaged)


def test_falls_back_to_path_then_project_tools(isolated_chain, monkeypatch):
    monkeypatch.setattr(tle.shutil, "which", lambda _: "/usr/local/bin/tle")
    assert tle.tle_path() == "/usr/local/bin/tle"

    monkeypatch.setattr(tle.shutil, "which", lambda _: None)
    local = _executable(isolated_chain / "tools" / "tle")
    monkeypatch.setattr(tle, "_PROJECT_TOOLS", local.parent)
    assert tle.tle_path() == str(local)


def test_packaged_binary_without_the_executable_bit_is_chmodded(isolated_chain, monkeypatch):
    # Wheels do not preserve the executable bit consistently across pip versions.
    packaged = isolated_chain / "pkg" / "tle"
    packaged.parent.mkdir(parents=True)
    packaged.write_text("#!/bin/sh\nexit 0\n")
    packaged.chmod(0o644)
    monkeypatch.setattr(tle, "_PACKAGED_BIN", packaged.parent)

    assert tle.tle_path() == str(packaged)
    assert os.access(packaged, os.X_OK)


def test_unchmoddable_binary_is_copied_to_the_user_cache(isolated_chain, monkeypatch):
    # A root-owned site-packages install running as a normal user cannot chmod in place.
    packaged = isolated_chain / "pkg" / "tle"
    packaged.parent.mkdir(parents=True)
    packaged.write_bytes(b"#!/bin/sh\nexit 0\n")
    packaged.chmod(0o644)
    monkeypatch.setattr(tle, "_PACKAGED_BIN", packaged.parent)
    cache = isolated_chain / "cache"
    monkeypatch.setattr(tle, "_CACHE_DIR", cache)

    # Only the install tree is read-only; the user's cache is still writable.
    real_chmod = os.chmod

    def chmod(path, mode, *args, **kwargs):
        if Path(path) == packaged:
            raise PermissionError(13, "Permission denied")
        return real_chmod(path, mode, *args, **kwargs)

    monkeypatch.setattr(tle.os, "chmod", chmod)

    resolved = tle.tle_path()

    assert resolved == str(cache / "tle")
    assert (cache / "tle").read_bytes() == packaged.read_bytes()
    assert os.access(cache / "tle", os.X_OK)


def test_missing_binary_explains_the_sdist_case(isolated_chain):
    with pytest.raises(tle.TleError) as exc:
        tle.tle_path()
    message = str(exc.value)
    assert "TIMESAFE_TLE" in message
    assert "source distribution" in message


# ── version pinning ──────────────────────────────────────────────────────────
def test_workflow_release_url_is_built_from_the_pinned_version():
    from timesafe.vault import workflow

    assert tle.TLE_VERSION in workflow.TLE_RELEASE
    assert workflow.TLE_RELEASE.endswith(f"tlock_{tle.TLE_VERSION}_linux_amd64.tar.gz")


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
