#!/usr/bin/env python3
"""Fail if a Linux binary requires a newer glibc than its target hosts have.

    python scripts/check_glibc_floor.py dist/timesafe 2.27

The standalone build exists precisely for machines too old for the wheels — the motivating one runs
Ubuntu 18.04, which is glibc 2.27. A binary needing anything newer won't start there, and the
failure looks like a mysterious "version `GLIBC_2.28' not found" to whoever downloaded it. Checking
it here means swapping the build image can never silently break that promise.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys

GLIBC_REF = re.compile(r"GLIBC_(\d+(?:\.\d+)+)")


def parse_version(text: str) -> tuple[int, int]:
    """'2.27' -> (2, 27). Only major/minor matter for glibc symbol versioning."""
    parts = text.split(".")
    return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0


def highest_glibc(symbols: str) -> tuple[int, int] | None:
    """The highest GLIBC_x.y referenced anywhere in the symbol dump, or None if there are none."""
    found = [parse_version(m.group(1)) for m in GLIBC_REF.finditer(symbols)]
    return max(found) if found else None


def verify(symbols: str, max_version: str) -> int:
    ceiling = parse_version(max_version)
    required = highest_glibc(symbols)

    if required is None:
        print("no glibc version references found — nothing to check")
        return 0

    pretty = f"{required[0]}.{required[1]}"
    if required > ceiling:
        print(
            f"FAIL: needs glibc {pretty}, but the target floor is {max_version}. "
            f"This binary will not start on the hosts it exists for.",
            file=sys.stderr,
        )
        return 1
    print(f"ok: highest glibc requirement is {pretty} (floor {max_version})")
    return 0


def dump_symbols(path: str) -> str:
    for tool, args in (("readelf", ["--dyn-syms", "--wide"]), ("objdump", ["-T"])):
        if shutil.which(tool):
            proc = subprocess.run([tool, *args, path], capture_output=True, text=True)
            if proc.returncode == 0:
                return proc.stdout
    print("neither readelf nor objdump is available; skipping the check", file=sys.stderr)
    return ""


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    return verify(dump_symbols(argv[0]), argv[1])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
