from __future__ import annotations

import sys

from timesafe import cli


def main() -> None:
    """Console-script entry point.

    A bare `timesafe` still opens the TUI, exactly as it always has; anything else is a CLI
    invocation. Both paths go through `cli.main`, so `--help` lists every command and Textual is
    imported lazily — only when the TUI is actually being launched.
    """
    argv = sys.argv[1:]
    sys.exit(cli.main(argv or ["tui"]))


if __name__ == "__main__":
    main()
