#!/usr/bin/env bash
# Build the standalone `timesafe` executable for one target.
#
#   scripts/build_binary.sh linux_amd64
#
# Uses a uv-managed CPython (python-build-standalone), which ships libpython as a shared library.
# PyInstaller requires that, and manylinux's own interpreters are static-only — so the obvious
# "build in manylinux2014 for an old glibc" approach cannot work without compiling CPython first.
#
# The glibc floor is therefore not guaranteed by the build image; it is *verified* afterwards by
# scripts/check_glibc_floor.py, which fails the build if the result needs anything newer than the
# oldest host we support.

set -euo pipefail

TLE_TARGET="${1:?usage: build_binary.sh <goos_goarch>, e.g. linux_amd64}"
VENV="${PWD}/build/venv"

command -v uv >/dev/null || { echo "uv is required (https://docs.astral.sh/uv/)" >&2; exit 1; }

echo "==> creating an isolated build environment"
rm -rf "${VENV}"
uv venv --python 3.12 "${VENV}"
export VIRTUAL_ENV="${VENV}"
PYTHON="${VENV}/bin/python"

uv pip install --quiet --python "${PYTHON}" pyinstaller httpx keyring pynacl
echo "==> python: $("${PYTHON}" --version)"

echo "==> fetching tle for ${TLE_TARGET}"
"${PYTHON}" scripts/build_wheels.py --fetch-only "${TLE_TARGET}"

echo "==> freezing"
TIMESAFE_TLE_BIN=build/tle-bin/tle "${PYTHON}" -m PyInstaller \
    --clean --noconfirm --distpath dist --workpath build/pyi timesafe.spec

chmod 0755 dist/timesafe
echo "==> built dist/timesafe ($(du -h dist/timesafe | cut -f1))"
