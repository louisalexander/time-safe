"""A release tag that disagrees with the packaged version is unrecoverable.

PyPI version numbers can never be reused or truly deleted, so tagging `v0.2.0` while the package
still says `0.1.0` spends 0.1.0 a second time: the upload fails, and the GitHub release meanwhile
carries binaries reporting the wrong version. Checking it before anything irreversible happens is
the difference between a ten-second failure and a burnt version number.
"""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def checker():
    spec = importlib.util.spec_from_file_location(
        "check_release_tag", REPO_ROOT / "scripts" / "check_release_tag.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_tag_matching_the_packaged_version_passes(checker):
    assert checker.verify("v0.1.0", "0.1.0") == 0


def test_a_tag_ahead_of_the_packaged_version_fails(checker):
    # The motivating mistake: tag bumped, timesafe/__init__.py forgotten.
    assert checker.verify("v0.2.0", "0.1.0") == 1


def test_a_tag_behind_the_packaged_version_fails(checker):
    assert checker.verify("v0.1.0", "0.2.0") == 1


def test_the_v_prefix_is_optional(checker):
    assert checker.verify("0.1.0", "0.1.0") == 0


def test_the_failure_message_carries_the_tag_and_the_package(checker, capsys):
    checker.verify("v0.2.0", "0.1.0")
    err = capsys.readouterr().err
    assert "0.2.0" in err and "0.1.0" in err


def test_a_version_suffix_is_not_silently_equal(checker):
    # 'v0.1.0' and '0.1.0rc1' are different releases on PyPI; comparing loosely would let one pass.
    assert checker.verify("v0.1.0", "0.1.0rc1") == 1


def test_it_checks_against_the_real_installed_package(checker):
    """The workflow passes no expected version — it reads the package, so that path must work."""
    import timesafe

    assert checker.packaged_version() == timesafe.__version__


# ── workflow wiring ──────────────────────────────────────────────────────────
def _release_yaml() -> str:
    return (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text()


def test_the_release_workflow_runs_the_guard():
    assert "scripts/check_release_tag.py" in _release_yaml()


def test_publishing_cannot_start_until_the_guard_has_passed():
    """A guard that runs beside publish-pypi rather than before it guards nothing."""
    yaml = _release_yaml()
    publish = yaml.split("publish-pypi:", 1)[1].split("\n  github-release:", 1)[0]
    assert "version-guard" in publish.split("needs:", 1)[1].split("\n", 1)[0]


def test_the_github_release_also_waits_for_the_guard():
    # Otherwise a mismatched tag still ships binaries reporting the wrong version.
    yaml = _release_yaml()
    release_job = yaml.split("github-release:", 1)[1]
    assert "version-guard" in release_job.split("needs:", 1)[1].split("\n", 1)[0]


def test_a_re_run_of_a_partial_release_is_not_blocked_by_its_own_uploads():
    """Without skip-existing, re-running a release that half-uploaded fails on its own files."""
    assert "skip-existing: true" in _release_yaml()
