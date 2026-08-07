#!/usr/bin/env bash
# Build the standalone `timesafe` executable for one target.
#
#   scripts/build_binary.sh linux_amd64
#
# On Linux this is meant to run *inside* a manylinux2014 container (glibc 2.17), so the result runs
# on anything from Ubuntu 18.04 onward. The container is invoked with `docker run` rather than a job
# `container:` because GitHub's JS actions need node24, which needs glibc >= 2.28 — newer than the
# image we deliberately target. Checkout happens on the host; only the build happens in here.
#
# On macOS it runs natively against whatever Python is on PATH.

set -euo pipefail

TLE_TARGET="${1:?usage: build_binary.sh <goos_goarch>, e.g. linux_amd64}"

# manylinux images ship their interpreters outside the default PATH.
if [ -d /opt/python/cp312-cp312/bin ]; then
    export PATH="/opt/python/cp312-cp312/bin:$PATH"
fi

echo "==> python: $(command -v python) ($(python --version 2>&1))"

python -m pip install --quiet --upgrade pip
python -m pip install --quiet pyinstaller httpx keyring pynacl

echo "==> fetching tle for ${TLE_TARGET}"
python scripts/build_wheels.py --fetch-only "${TLE_TARGET}"

echo "==> building"
TIMESAFE_TLE_BIN=build/tle-bin/tle python -m PyInstaller --clean --noconfirm timesafe.spec

# The container runs as root; leave the artifact readable and runnable from the host job.
chmod 0755 dist/timesafe
echo "==> built dist/timesafe"
