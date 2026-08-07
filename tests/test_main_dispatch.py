import subprocess
import sys

import pytest

from timesafe import __main__, cli


@pytest.fixture
def recorded(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "main", lambda argv, **kw: (calls.append(argv), 0)[1])
    return calls


def test_bare_invocation_launches_the_tui(monkeypatch, recorded):
    monkeypatch.setattr(sys, "argv", ["timesafe"])
    with pytest.raises(SystemExit) as exc:
        __main__.main()
    assert recorded == [["tui"]]
    assert exc.value.code == 0


def test_a_subcommand_is_delegated_to_the_cli(monkeypatch, recorded):
    monkeypatch.setattr(sys, "argv", ["timesafe", "status", "--json"])
    with pytest.raises(SystemExit):
        __main__.main()
    assert recorded == [["status", "--json"]]


def test_the_cli_exit_code_becomes_the_process_exit_code(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["timesafe", "reveal", "--id", "x"])
    monkeypatch.setattr(cli, "main", lambda argv, **kw: 3)
    with pytest.raises(SystemExit) as exc:
        __main__.main()
    assert exc.value.code == 3


def test_help_is_delegated_rather_than_opening_the_tui(monkeypatch, recorded):
    monkeypatch.setattr(sys, "argv", ["timesafe", "--help"])
    with pytest.raises(SystemExit):
        __main__.main()
    assert recorded == [["--help"]]


def test_a_cli_run_never_imports_textual():
    """Textual costs real start-up time and must not be loaded on the automation path."""
    code = (
        "import sys; from timesafe import cli; "
        "cli.main(['--help']); "
        "sys.exit(1 if 'textual' in sys.modules else 0)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert result.returncode == 0, "importing timesafe.cli pulled in textual"
