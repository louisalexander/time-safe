# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the standalone `timesafe` executable.

For hosts with no usable modern Python — the motivating case is an Ubuntu 18.04 box whose newest
working interpreter is 3.9, with no uv, pipx or virtualenv, so the PyPI wheels cannot run there at
all. Built inside a manylinux2014 container (glibc 2.17), the result runs on anything newer.

CLI-only: Textual is excluded, which roughly halves the artifact and removes PyInstaller's most
fragile hidden-import surface. `timesafe tui` inside this binary exits with a message pointing at
the pip install; cli._cmd_tui handles that.

    TIMESAFE_TLE_BIN=/path/to/tle pyinstaller timesafe.spec
"""

import os
import sys

sys.path.insert(0, os.getcwd())
from timesafe.timelock.tle import TLE_VERSION  # noqa: E402

tle_binary = os.environ.get("TIMESAFE_TLE_BIN")
if not tle_binary or not os.path.exists(tle_binary):
    raise SystemExit(
        f"Set TIMESAFE_TLE_BIN to the tlock {TLE_VERSION} binary to bundle "
        "(scripts/build_wheels.py fetches it)."
    )

a = Analysis(
    ["timesafe/__main__.py"],
    pathex=[os.getcwd()],
    # Landing at the bundle root makes it sys._MEIPASS/tle, which tle_path() looks for.
    binaries=[(tle_binary, ".")],
    datas=[],
    hiddenimports=[
        # pynacl (via vault/github/secrets_api.py) is a cffi extension, and PyInstaller does not
        # discover its native backend on its own — without this the binary dies on first import.
        "cffi",
        "_cffi_backend",
        # keyring picks its backend dynamically; the CLI must degrade to "no keychain" on a
        # headless box rather than fail to import.
        "keyring.backends.fail",
        "keyring.backends.null",
    ],
    excludes=[
        "textual",
        "rich",
        "tkinter",
        "pytest",
        "IPython",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="timesafe",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
