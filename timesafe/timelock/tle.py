from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class NotYetUnlocked(Exception):
    """Raised when a timelock ciphertext cannot be decrypted yet (its round hasn't arrived)."""


class TleError(Exception):
    """Raised on any other `tle` failure (missing binary, bad input, network)."""


def tle_path() -> str:
    """Locate the `tle` binary: $TIMESAFE_TLE, then PATH, then the project's ./.tools/tle."""
    env = os.environ.get("TIMESAFE_TLE")
    if env:
        return env
    found = shutil.which("tle")
    if found:
        return found
    local = Path(__file__).resolve().parents[2] / ".tools" / "tle"
    if local.exists():
        return str(local)
    raise TleError(
        "tle binary not found — set TIMESAFE_TLE, install `tle`, or place it at .tools/tle "
        "(https://github.com/drand/tlock/releases)."
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
