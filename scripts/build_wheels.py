#!/usr/bin/env python3
"""Build platform wheels with the pinned `tle` binary vendored in.

`tle` is a Go binary, not a Python package, so a plain `pip install timesafe` would leave `add` and
`reveal` dead. Each wheel therefore carries the matching binary at `timesafe/_bin/tle` and is
retagged from `py3-none-any` to a real platform tag.

    python scripts/build_wheels.py                 # every target
    python scripts/build_wheels.py --target manylinux2014_x86_64
    python scripts/build_wheels.py --list

The sdist deliberately carries no binary; `tle_path()` raises a message explaining that.

tlock is dual-licensed Apache-2.0 / MIT, so redistributing the binary is permitted. Both licence
texts are fetched from the pinned tag and shipped alongside it.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from timesafe.timelock.tle import TLE_VERSION  # noqa: E402

RELEASE_BASE = f"https://github.com/drand/tlock/releases/download/v{TLE_VERSION}"
LICENCE_BASE = f"https://raw.githubusercontent.com/drand/tlock/v{TLE_VERSION}"
LICENCE_FILES = ("LICENSE-APACHE", "LICENSE-MIT")
BIN_DIR = REPO_ROOT / "timesafe" / "_bin"

# Wheel platform tag -> the tlock release's GOOS_GOARCH suffix.
TARGETS = {
    "manylinux2014_x86_64": "linux_amd64",
    "manylinux2014_aarch64": "linux_arm64",
    "macosx_11_0_arm64": "darwin_arm64",
    "macosx_10_9_x86_64": "darwin_amd64",
}


def asset_name(goos_goarch: str) -> str:
    return f"tlock_{TLE_VERSION}_{goos_goarch}.tar.gz"


def asset_url(goos_goarch: str) -> str:
    return f"{RELEASE_BASE}/{asset_name(goos_goarch)}"


def parse_checksums(text: str) -> dict[str, str]:
    """Parse a goreleaser checksums.txt into {filename: sha256}."""
    sums: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2:
            digest, name = parts
            sums[name.lstrip("*")] = digest
    return sums


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url) as response:  # noqa: S310 — pinned github.com release URLs
        return response.read()


def fetch_tle(goos_goarch: str, dest_dir: Path) -> Path:
    """Download, checksum-verify and extract `tle` for one target into `dest_dir`."""
    name = asset_name(goos_goarch)
    expected = parse_checksums(_fetch(f"{RELEASE_BASE}/checksums.txt").decode()).get(name)
    if not expected:
        raise SystemExit(f"{name} is not listed in the release checksums.")

    payload = _fetch(asset_url(goos_goarch))
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise SystemExit(f"Checksum mismatch for {name}: expected {expected}, got {actual}.")

    dest_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / name
        archive.write_bytes(payload)
        with tarfile.open(archive) as tar:
            member = tar.getmember("tle")
            tar.extract(member, tmp, filter="data")
        shutil.copyfile(Path(tmp) / "tle", dest_dir / "tle")

    (dest_dir / "tle").chmod(0o755)
    for licence in LICENCE_FILES:
        (dest_dir / licence).write_bytes(_fetch(f"{LICENCE_BASE}/{licence}"))
    return dest_dir / "tle"


def build_wheel(platform_tag: str, outdir: Path) -> Path:
    """Build a wheel from the current tree and retag it for `platform_tag`."""
    subprocess.run(
        [sys.executable, "-m", "uv", "build", "--wheel", "--out-dir", str(outdir)],
        cwd=REPO_ROOT,
        check=True,
    )
    built = max(outdir.glob("*-any.whl"), key=lambda p: p.stat().st_mtime)
    subprocess.run(
        [sys.executable, "-m", "wheel", "tags", "--remove", f"--platform-tag={platform_tag}", str(built)],
        check=True,
    )
    return next(outdir.glob(f"*{platform_tag}.whl"))


def build(platform_tag: str, outdir: Path) -> Path:
    goos_goarch = TARGETS[platform_tag]
    print(f"→ {platform_tag}  (tlock {TLE_VERSION} {goos_goarch})", flush=True)
    shutil.rmtree(BIN_DIR, ignore_errors=True)
    fetch_tle(goos_goarch, BIN_DIR)
    try:
        wheel = build_wheel(platform_tag, outdir)
    finally:
        shutil.rmtree(BIN_DIR, ignore_errors=True)
    print(f"  built {wheel.name}", flush=True)
    return wheel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", action="append", choices=sorted(TARGETS), help="repeatable")
    parser.add_argument("--outdir", default=str(REPO_ROOT / "dist"))
    parser.add_argument("--list", action="store_true", help="print the target table and exit")
    args = parser.parse_args(argv)

    if args.list:
        for tag, goos in sorted(TARGETS.items()):
            print(f"{tag}\t{asset_name(goos)}")
        return 0

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for tag in args.target or sorted(TARGETS):
        build(tag, outdir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
