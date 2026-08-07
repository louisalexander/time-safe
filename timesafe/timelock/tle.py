from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# The single source of truth for which tlock release we ship and generate workflows against.
# vault/workflow.py builds its download URL from this, the wheel builder fetches it, and the
# PyInstaller spec bundles it — a test asserts they all agree.
TLE_VERSION = "1.2.0"

_PACKAGED_BIN = Path(__file__).resolve().parents[1] / "_bin"
_PROJECT_TOOLS = Path(__file__).resolve().parents[2] / ".tools"
_CACHE_DIR = Path.home() / ".cache" / "timesafe"


class NotYetUnlocked(Exception):
    """Raised when a timelock ciphertext cannot be decrypted yet (its round hasn't arrived)."""


class TleError(Exception):
    """Raised on any other `tle` failure (missing binary, bad input, network)."""


def _make_executable(path: Path) -> str:
    """Ensure a binary we shipped is runnable.

    Wheels don't preserve the executable bit consistently across pip versions, so chmod it. If the
    install tree is read-only (root-owned site-packages, non-root process), fall back to a copy in
    the user cache rather than failing at the first encrypt.
    """
    if os.access(path, os.X_OK):
        return str(path)
    try:
        os.chmod(path, 0o755)
        return str(path)
    except OSError:
        pass
    cached = _CACHE_DIR / path.name
    if not os.access(cached, os.X_OK):
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, cached)
        os.chmod(cached, 0o755)
    return str(cached)


def tle_path() -> str:
    """Locate the `tle` binary.

    Order: $TIMESAFE_TLE, the PyInstaller bundle, the binary packaged into the wheel, PATH, then the
    project's ./.tools/tle. The packaged copy deliberately outranks PATH so the version always
    matches TLE_VERSION rather than whatever stray `tle` a host happens to have.
    """
    env = os.environ.get("TIMESAFE_TLE")
    if env:
        return env

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        frozen = Path(meipass) / "tle"
        if frozen.exists():
            return _make_executable(frozen)

    packaged = _PACKAGED_BIN / "tle"
    if packaged.exists():
        return _make_executable(packaged)

    found = shutil.which("tle")
    if found:
        return found

    local = _PROJECT_TOOLS / "tle"
    if local.exists():
        return str(local)

    raise TleError(
        "tle binary not found. Wheels for common platforms bundle it; you are likely running from a "
        "source distribution or an unsupported platform. Install the `tle` binary from "
        "https://github.com/drand/tlock/releases, then put it on PATH or point TIMESAFE_TLE at it."
    )


def encrypt(plaintext: bytes, drand_round: int, *, tle: str | None = None) -> bytes:
    """Timelock-encrypt `plaintext` to `drand_round` (quicknet). Returns the tlock ciphertext."""
    binary = tle or tle_path()
    proc = subprocess.run(
        [binary, "-e", "-r", str(drand_round)], input=plaintext, capture_output=True
    )
    if proc.returncode != 0:
        raise TleError(proc.stderr.decode(errors="replace").strip())
    return proc.stdout


def decrypt(ciphertext: bytes, *, tle: str | None = None) -> bytes:
    """Decrypt a tlock ciphertext. Raises NotYetUnlocked if its round hasn't arrived yet."""
    binary = tle or tle_path()
    proc = subprocess.run([binary, "-d"], input=ciphertext, capture_output=True)
    if proc.returncode != 0:
        err = proc.stderr.decode(errors="replace").strip()
        if "too early" in err.lower():
            raise NotYetUnlocked(err)
        raise TleError(err)
    return proc.stdout
