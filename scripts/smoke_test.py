#!/usr/bin/env python3
"""Verify a built artifact actually works, before anything is published.

Two modes:

    python scripts/smoke_test.py wheel              # run with the *installed* package's interpreter
    python scripts/smoke_test.py binary ./dist/timesafe

Run the wheel mode from outside the repository root, so `import timesafe` resolves to the installed
wheel rather than the source tree — otherwise this proves nothing about what was packaged.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

EXIT_USAGE = 2


def _fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command that must terminate. A hang here would stall the whole release."""
    try:
        return subprocess.run(cmd, capture_output=True, timeout=60, **kwargs)
    except subprocess.TimeoutExpired:
        _fail(f"{' '.join(cmd)} did not terminate within 60s")


def check_wheel() -> None:
    import timesafe
    from timesafe.timelock.tle import TLE_VERSION, tle_path

    source = Path(timesafe.__file__).resolve()
    if (Path.cwd() / "timesafe" / "__init__.py").resolve() == source:
        _fail("imported the source tree, not the installed wheel — run this from another directory")
    print(f"ok: timesafe imported from {source.parent}")

    resolved = Path(tle_path())
    if resolved.parent.name != "_bin":
        _fail(f"the packaged tle did not win resolution (got {resolved})")
    if not resolved.exists():
        _fail(f"{resolved} does not exist")
    proc = _run([str(resolved), "-h"])
    if proc.returncode not in (0, 1, 2):
        _fail(f"the bundled tle is not executable (exit {proc.returncode})")
    print(f"ok: bundled tlock {TLE_VERSION} at {resolved} is executable")

    licences = list(resolved.parent.glob("LICENSE-*"))
    if not licences:
        _fail("tlock's licence files were not shipped alongside the binary")
    print(f"ok: licences shipped ({', '.join(p.name for p in licences)})")

    # The console script is what users actually invoke; importing the package doesn't prove it exists.
    script = Path(sys.executable).parent / "timesafe"
    if not script.exists():
        _fail(f"the `timesafe` console script was not installed (looked in {script.parent})")
    _check_cli(str(script))


def _check_cli(executable: str) -> None:
    """Shared CLI assertions for both the console script and the standalone binary.

    HOME is redirected so a developer's real ~/.timesafe/vaults.json can't be picked up and turn the
    no-vault check into a live GitHub call.
    """
    helped = _run([executable, "--help"])
    if helped.returncode != 0 or b"reveal" not in helped.stdout:
        _fail("--help did not list the commands")
    print("ok: --help works")

    versioned = _run([executable, "--version"])
    if versioned.returncode != 0 or not versioned.stdout.strip():
        _fail("--version produced nothing")
    print(f"ok: --version -> {versioned.stdout.decode().strip()}")

    with tempfile.TemporaryDirectory() as empty_home:
        env = {"PATH": "/usr/bin:/bin", "HOME": empty_home}
        status = _run([executable, "status", "--json"], env=env)

    if status.returncode != EXIT_USAGE:
        _fail(
            f"expected exit {EXIT_USAGE} with no vault configured, got {status.returncode}: "
            f"{status.stderr!r}"
        )
    if b"Traceback" in status.stderr:
        _fail("a traceback escaped to stderr")
    try:
        body = json.loads(status.stderr)
    except json.JSONDecodeError:
        _fail(f"stderr was not JSON: {status.stderr!r}")
    if "code" not in body:
        _fail(f"error body has no machine-readable code: {body}")
    print(f"ok: no-vault exits {EXIT_USAGE} with code={body['code']}")


def check_binary(executable: str) -> None:
    exe = Path(executable).resolve()
    if not exe.exists():
        _fail(f"{exe} does not exist")

    _check_cli(str(exe))

    # The TUI is deliberately excluded from the standalone build; it must say so, not crash.
    with tempfile.TemporaryDirectory() as empty_home:
        tui = _run([str(exe), "tui"], env={"PATH": "/usr/bin:/bin", "HOME": empty_home})
    if tui.returncode != EXIT_USAGE or b"Traceback" in tui.stderr:
        _fail(f"`tui` should exit {EXIT_USAGE} with an explanation, got {tui.returncode}")
    print("ok: `tui` reports that this build is CLI-only")


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in {"wheel", "binary"}:
        print(__doc__)
        return 2
    if argv[0] == "wheel":
        check_wheel()
    else:
        if len(argv) < 2:
            _fail("binary mode needs the path to the executable")
        check_binary(argv[1])
    print("smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
