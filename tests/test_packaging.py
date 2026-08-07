"""Packaging invariants — the ones that break silently and are noticed only at install time."""

import importlib.util
import re
from pathlib import Path

import pytest

from timesafe.timelock.tle import TLE_VERSION

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_wheels", REPO_ROOT / "scripts" / "build_wheels.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder():
    return _load_builder()


# ── version pinning ──────────────────────────────────────────────────────────
def _tracked_text_files():
    skip_dirs = {".git", ".venv", "node_modules", "dist", "build", "__pycache__", ".pytest_cache"}
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or path.suffix in {".png", ".svg", ".lock", ".ico"}:
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue


def test_no_file_hardcodes_a_tlock_version_other_than_the_pin():
    """One pin, in timelock/tle.py. Anything else that names a tlock version has drifted."""
    patterns = [
        re.compile(r"tlock[_-]v?(\d+\.\d+\.\d+)"),
        re.compile(r"drand/tlock/releases/download/v(\d+\.\d+\.\d+)"),
        re.compile(r"drand/tlock/v(\d+\.\d+\.\d+)"),
    ]
    offenders = []
    for path, text in _tracked_text_files():
        for pattern in patterns:
            for match in pattern.finditer(text):
                if match.group(1) != TLE_VERSION:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {match.group(0)}")
    assert not offenders, f"tlock version drift (pin is {TLE_VERSION}): {offenders}"


def test_the_generated_unlock_workflow_uses_the_pinned_release():
    from timesafe.vault.workflow import TLE_RELEASE

    assert f"/v{TLE_VERSION}/" in TLE_RELEASE


def test_the_builder_derives_its_urls_from_the_pin(builder):
    assert builder.TLE_VERSION == TLE_VERSION
    assert builder.asset_name("linux_amd64") == f"tlock_{TLE_VERSION}_linux_amd64.tar.gz"
    assert builder.asset_url("linux_amd64").endswith(
        f"/v{TLE_VERSION}/tlock_{TLE_VERSION}_linux_amd64.tar.gz"
    )


# ── target table ─────────────────────────────────────────────────────────────
def test_every_wheel_target_maps_to_a_real_release_asset(builder):
    # These four suffixes exist in the tlock v1.2.0 release; a typo here fails only at build time.
    assert set(builder.TARGETS.values()) == {
        "linux_amd64",
        "linux_arm64",
        "darwin_arm64",
        "darwin_amd64",
    }


def test_wheel_tags_are_platform_specific_never_any(builder):
    # A wheel containing a native binary must not be published as py3-none-any.
    assert all(tag != "any" for tag in builder.TARGETS)
    assert all(
        tag.startswith(("manylinux", "macosx")) for tag in builder.TARGETS
    ), builder.TARGETS


def test_checksum_parsing_handles_the_goreleaser_format(builder):
    text = (
        "abc123  tlock_1.2.0_linux_amd64.tar.gz\n"
        "def456 *tlock_1.2.0_darwin_arm64.tar.gz\n"
        "\n"
    )
    assert builder.parse_checksums(text) == {
        "tlock_1.2.0_linux_amd64.tar.gz": "abc123",
        "tlock_1.2.0_darwin_arm64.tar.gz": "def456",
    }


# ── wheel contents ───────────────────────────────────────────────────────────
def test_the_wheel_is_configured_to_include_the_vendored_binary():
    config = (REPO_ROOT / "pyproject.toml").read_text()
    assert 'artifacts = ["timesafe/_bin/*"]' in config, (
        "timesafe/_bin is gitignored, so hatchling drops it unless it's listed as an artifact"
    )


def test_the_binary_directory_is_not_committed():
    gitignore = (REPO_ROOT / ".gitignore").read_text()
    assert "timesafe/_bin" in gitignore


def test_the_console_script_points_at_the_dispatcher():
    config = (REPO_ROOT / "pyproject.toml").read_text()
    assert 'timesafe = "timesafe.__main__:main"' in config


# ── licensing ────────────────────────────────────────────────────────────────
def test_license_is_verbatim_mit_so_it_is_detected():
    """GitHub matches LICENSE against known templates; extra prose makes it report NOASSERTION.

    Third-party attribution belongs in NOTICE, not appended here.
    """
    text = (REPO_ROOT / "LICENSE").read_text()
    assert text.startswith("MIT License")
    assert text.rstrip().endswith("SOFTWARE.")
    assert "tlock" not in text


def test_notice_records_the_bundled_third_party_binary():
    notice = (REPO_ROOT / "NOTICE").read_text()
    assert "tlock" in notice
    assert "Apache" in notice and "MIT" in notice


def test_both_licence_files_ship_in_the_distribution():
    config = (REPO_ROOT / "pyproject.toml").read_text()
    assert 'license-files = ["LICENSE", "NOTICE"]' in config


# ── version reporting ────────────────────────────────────────────────────────
def test_the_package_carries_its_own_version():
    """importlib.metadata is empty in a frozen binary, so the version must live in the package."""
    import timesafe

    assert re.fullmatch(r"\d+\.\d+\.\d+", timesafe.__version__)


def test_pyproject_derives_its_version_from_the_package():
    # One source of truth, so a release can't ship a binary reporting a different version.
    config = (REPO_ROOT / "pyproject.toml").read_text()
    assert 'dynamic = ["version"]' in config
    assert 'path = "timesafe/__init__.py"' in config


def test_the_cli_reports_the_real_version_without_installed_metadata():
    import timesafe
    from timesafe import cli

    assert cli._version() == timesafe.__version__
    assert "unknown" not in cli._version()


# ── PyInstaller spec ─────────────────────────────────────────────────────────
def test_the_binary_spec_excludes_textual():
    """The standalone build is CLI-only; bundling Textual doubles it for no benefit."""
    spec = (REPO_ROOT / "timesafe.spec").read_text()
    assert '"textual"' in spec.split("excludes=")[1].split("]")[0]


def test_the_binary_spec_declares_the_cffi_backend():
    """pynacl is a cffi extension; without this hidden import the frozen binary dies on import."""
    spec = (REPO_ROOT / "timesafe.spec").read_text()
    hidden = spec.split("hiddenimports=")[1].split("]")[0]
    assert '"_cffi_backend"' in hidden


def test_the_binary_spec_bundles_tle_at_the_bundle_root():
    # tle_path() looks for sys._MEIPASS/tle, so the destination must be ".".
    spec = (REPO_ROOT / "timesafe.spec").read_text()
    assert 'binaries=[(tle_binary, ".")]' in spec


def test_the_tui_command_fails_gracefully_when_textual_is_absent(monkeypatch):
    """In the standalone binary the import genuinely fails; it must not surface as a crash."""
    import builtins

    from timesafe import cli
    from timesafe.errors import UsageError

    real_import = builtins.__import__

    def no_textual(name, *args, **kwargs):
        if name.startswith("timesafe.app") or name == "textual":
            raise ModuleNotFoundError("No module named 'textual'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_textual)

    with pytest.raises(UsageError) as exc:
        cli._cmd_tui()
    assert "TUI is not available" in str(exc.value)
