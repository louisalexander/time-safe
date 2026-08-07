from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import timezone
from typing import Any, BinaryIO

from timesafe import api
from timesafe.errors import EmptyStdinError, TimesafeError, UsageError, VaultError
from timesafe.vault.vault import Vault

"""The non-interactive command line.

All I/O is binary so `reveal` can emit a byte-exact plaintext, and every stream is injectable so the
whole surface is testable in-process. `main()` returns an exit code rather than calling sys.exit —
`timesafe.__main__` performs the exit.

Exit codes: 0 ok · 2 usage · 3 not-yet-unlockable · 4 vault/network · 5 not-found.
"""

PROG = "timesafe"


def _version() -> str:
    try:
        from importlib.metadata import version

        return version("timesafe")
    except Exception:  # noqa: BLE001 — running from a source tree without metadata
        return "0.0.0+unknown"


# ── argument parsing ─────────────────────────────────────────────────────────
class _Parser(argparse.ArgumentParser):
    """An ArgumentParser that raises instead of exiting, and never echoes argument values.

    argparse's default `error()` prints the offending value — which for a mistyped secret would put
    the plaintext straight into the logs. Help and version text is routed to the injected stream
    rather than the process stdout, so every byte this command emits is redirectable.
    """

    _out: BinaryIO | None = None

    def error(self, message: str) -> Any:  # type: ignore[override]
        raise UsageError(_sanitize(message))

    def _print_message(self, message: str, file: Any = None) -> None:
        if message and self._out is not None:
            self._out.write(message.encode("utf-8"))
            return
        super()._print_message(message, file)


def _sanitize(message: str) -> str:
    if message.startswith("unrecognized arguments"):
        return (
            "Unrecognized arguments. The secret is read from stdin via --secret-stdin and is never "
            "accepted as an argument."
        )
    if "invalid choice" in message:
        choices = message.split("(", 1)[-1].rstrip(")")
        return f"Unknown command. Valid choices are {choices}."
    return message[0].upper() + message[1:] if message else message


def build_parser(stdout: BinaryIO | None = None) -> _Parser:
    parser = _Parser(prog=PROG, description="Timelock secrets in a GitHub vault.", add_help=True)
    parser.add_argument("--version", action="version", version=f"{PROG} {_version()}")
    subparsers = parser.add_subparsers(dest="command", metavar="<command>", parser_class=_Parser)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--vault", metavar="<name|owner/repo>", help="which vault to use (else $TIMESAFE_VAULT)"
    )
    common.add_argument("--json", action="store_true", help="machine-readable output on stdout")

    p_add = subparsers.add_parser(
        "add", parents=[common], help="timelock a secret read from stdin"
    )
    p_add.add_argument("--name", required=True, metavar="<label>", help="human-readable label")
    p_add.add_argument("--duration", required=True, metavar="<10d|2h|30m>", help="how long to lock")
    p_add.add_argument("--email", metavar="<addr>", help="optional delivery address")
    p_add.add_argument(
        "--secret-stdin",
        action="store_true",
        required=True,
        help="read the plaintext from stdin (the only way to supply it)",
    )

    p_status = subparsers.add_parser(
        "status", parents=[common], help="readiness of one or every secret"
    )
    _add_selectors(p_status)

    p_reveal = subparsers.add_parser(
        "reveal", parents=[common], help="print an unlocked secret's plaintext"
    )
    _add_selectors(p_reveal)

    subparsers.add_parser("list", parents=[common], help="full metadata for every secret")

    p_init = subparsers.add_parser(
        "init", parents=[common], help="create and/or initialize a vault repo"
    )
    p_init.add_argument("--name", required=True, metavar="<label>", help="local name for the vault")
    p_init.add_argument("--create", action="store_true", help="create the repo if it is missing")
    p_init.add_argument("--token-stdin", action="store_true", help="read the PAT from stdin")

    subparsers.add_parser("tui", help="launch the interactive terminal UI")

    parser._out = stdout
    for sub in subparsers.choices.values():
        sub._out = stdout  # type: ignore[attr-defined]
    return parser


def _add_selectors(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--id", dest="secret_id", metavar="<id>", help="the id returned by `add`")
    parser.add_argument(
        "--name",
        metavar="<label>",
        help="convenience lookup; fails if the name is ambiguous (names are not unique)",
    )


# ── stdin ────────────────────────────────────────────────────────────────────
def _read_stdin_text(stdin: BinaryIO, what: str) -> str:
    """Read stdin as UTF-8, stripping exactly one trailing newline.

    Exactly one, so `echo secret |` behaves as expected while a secret that genuinely ends in
    whitespace survives intact. Use `printf '%s'` for byte-exact input.
    """
    if stdin.isatty():
        raise UsageError(
            f"stdin is a terminal, so there is nothing to read. Pipe the {what} in, e.g. "
            f"`printf '%s' \"$VALUE\" | {PROG} ...`."
        )

    data = stdin.read()
    if data.endswith(b"\r\n"):
        data = data[:-2]
    elif data.endswith(b"\n"):
        data = data[:-1]
    if not data:
        raise EmptyStdinError(f"No {what} on stdin.")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise UsageError(f"The {what} on stdin is not valid UTF-8.") from None


# ── output ───────────────────────────────────────────────────────────────────
def _write(stream: BinaryIO, text: str) -> None:
    stream.write(text.encode("utf-8"))


def _emit_json(stream: BinaryIO, payload: Any) -> None:
    _write(stream, json.dumps(payload) + "\n")


def _emit_error(stream: BinaryIO, exc: TimesafeError) -> None:
    _emit_json(stream, exc.to_json())


def _status_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No secrets in this vault.\n"
    header = f"{'ID':36}  {'NAME':20}  {'UNLOCK AT':25}  READY  REMAINING\n"
    lines = [header]
    for row in rows:
        ready = "yes" if row["ready"] else "no"
        lines.append(
            f"{row['id']:36}  {row['name'][:20]:20}  {row['unlock_at']:25}  "
            f"{ready:5}  {_humanize(row['seconds_remaining'])}\n"
        )
    return "".join(lines)


def _list_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No secrets in this vault.\n"
    lines = []
    for row in rows:
        lines.append(f"{row['id']}  {row['name']}\n")
        lines.append(f"    unlocks {row['unlock_at']}  (round {row['round']})\n")
        lines.append(f"    created {row['created_at']}\n")
        if row["delivery_email"]:
            lines.append(f"    emails  {row['delivery_email']}\n")
    return "".join(lines)


def _humanize(seconds: int) -> str:
    if seconds <= 0:
        return "-"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


# ── commands ─────────────────────────────────────────────────────────────────
def _cmd_add(args, stdin: BinaryIO, stdout: BinaryIO, vault: Vault | None) -> int:
    secret = _read_stdin_text(stdin, "secret")
    result = api.add(
        name=args.name,
        duration=args.duration,
        secret=secret,
        email=args.email,
        vault=vault,
        selector=args.vault,
    )
    _emit_json(stdout, result)
    return 0


def _cmd_status(args, stdout: BinaryIO, vault: Vault | None) -> int:
    result = api.status(
        secret_id=args.secret_id, name=args.name, vault=vault, selector=args.vault
    )
    if args.json:
        _emit_json(stdout, result)
    else:
        _write(stdout, _status_table(result if isinstance(result, list) else [result]))
    return 0


def _cmd_reveal(args, stdout: BinaryIO, vault: Vault | None) -> int:
    plaintext = api.reveal(
        secret_id=args.secret_id, name=args.name, vault=vault, selector=args.vault
    )
    # Byte-exact: no decoration, no trailing newline of our own, never print().
    stdout.write(plaintext.encode("utf-8"))
    return 0


def _cmd_list(args, stdout: BinaryIO, vault: Vault | None) -> int:
    rows = api.list_secrets(vault=vault, selector=args.vault)
    if args.json:
        _emit_json(stdout, rows)
    else:
        _write(stdout, _list_table(rows))
    return 0


def _cmd_init(args, stdin: BinaryIO, stdout: BinaryIO) -> int:
    if not args.vault:
        raise UsageError("init needs --vault owner/repo.")
    token = (
        _read_stdin_text(stdin, "token")
        if args.token_stdin
        else (os.environ.get("TIMESAFE_GITHUB_TOKEN") or "").strip()
    )
    if not token:
        raise UsageError("No token. Set TIMESAFE_GITHUB_TOKEN or pass --token-stdin.")
    result = api.init(repo=args.vault, name=args.name, token=token, create=args.create)
    _emit_json(stdout, result)
    return 0


def _cmd_tui() -> int:
    # Imported lazily so no CLI invocation ever pays for loading Textual.
    try:
        from timesafe.app import TimeSafeApp
    except ModuleNotFoundError as exc:
        raise UsageError(
            "The TUI is not available in this build. Install time-safe from PyPI to use it."
        ) from exc
    TimeSafeApp().run()
    return 0


# ── entry point ──────────────────────────────────────────────────────────────
def main(
    argv: list[str] | None = None,
    *,
    stdin: BinaryIO | None = None,
    stdout: BinaryIO | None = None,
    stderr: BinaryIO | None = None,
    vault: Vault | None = None,
) -> int:
    """Run one CLI invocation and return its exit code. Never raises, never prints a traceback."""
    argv = sys.argv[1:] if argv is None else argv
    stdin = stdin if stdin is not None else sys.stdin.buffer
    stdout = stdout if stdout is not None else sys.stdout.buffer
    stderr = stderr if stderr is not None else sys.stderr.buffer

    try:
        parser = build_parser(stdout)
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            # --help / --version print to the real stdout and exit 0; anything else is a usage error.
            return int(exc.code or 0)

        if args.command is None:
            raise UsageError("No command given. Try `timesafe --help`.")

        if args.command == "add":
            return _cmd_add(args, stdin, stdout, vault)
        if args.command == "status":
            return _cmd_status(args, stdout, vault)
        if args.command == "reveal":
            return _cmd_reveal(args, stdout, vault)
        if args.command == "list":
            return _cmd_list(args, stdout, vault)
        if args.command == "init":
            return _cmd_init(args, stdin, stdout)
        if args.command == "tui":
            return _cmd_tui()
        raise UsageError(f"Unknown command {args.command!r}.")

    except TimesafeError as exc:
        _emit_error(stderr, exc)
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001
        # Never let a traceback out: rich renders frame locals, which would include the plaintext.
        if os.environ.get("TIMESAFE_DEBUG") == "1":
            _write(stderr, "".join(traceback.format_exception_only(type(exc), exc)))
        _emit_error(stderr, VaultError("Internal error."))
        return 4
    finally:
        for stream in (stdout, stderr):
            try:
                stream.flush()
            except Exception:  # noqa: BLE001
                pass
