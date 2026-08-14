#!/usr/bin/env python3
"""Fail if a release tag does not match the version the package will report.

    python scripts/check_release_tag.py v0.1.0

`release.yml` publishes on any `v*` tag but builds whatever `timesafe/__init__.py` says, so tagging
`v0.2.0` with the package still at `0.1.0` would publish 0.1.0 under a v0.2.0 tag. PyPI version
numbers can never be reused or truly deleted, so that mistake is permanent: 0.1.0 is spent, the
upload fails, and the GitHub release meanwhile carries binaries reporting the wrong version.

The version is read out of the source rather than imported, so this runs in seconds on a bare
checkout — before anything irreversible has happened.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_LINE = re.compile(r'^__version__\s*=\s*["\'](.+?)["\']', re.MULTILINE)


def packaged_version() -> str:
    """The version `timesafe.__version__` will report, read without importing the package."""
    source = (REPO_ROOT / "timesafe" / "__init__.py").read_text(encoding="utf-8")
    match = VERSION_LINE.search(source)
    if match is None:
        raise SystemExit("could not find __version__ in timesafe/__init__.py")
    return match.group(1)


def verify(tag: str, packaged: str) -> int:
    """Compare a `v`-prefixed git tag against the packaged version, exactly.

    Deliberately a string comparison, not a version-object one: `v0.1.0` and `0.1.0rc1` are
    different releases on PyPI, and a loose comparison would wave that through.
    """
    wanted = tag[1:] if tag.startswith("v") else tag
    if wanted != packaged:
        print(
            f"FAIL: tag {tag} would publish version {packaged}. "
            f"Bump timesafe/__init__.py to {wanted}, or retag as v{packaged}.",
            file=sys.stderr,
        )
        return 1
    print(f"ok: tag {tag} matches the packaged version {packaged}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    return verify(argv[0], packaged_version())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
