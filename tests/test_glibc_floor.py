"""The standalone Linux binary exists for old hosts, so its glibc floor is a hard requirement.

Encoding it as a check means a change of build image can never silently ship a binary that won't
start on the machines it was built for.
"""

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

READELF_SAMPLE = """
0x0000000000000000 (NEEDED)   Shared library: [libdl.so.2]
000000000000 R_X86_64_JUMP_SLO 0000000000000000 memcpy@GLIBC_2.14 + 0
000000000000 R_X86_64_JUMP_SLO 0000000000000000 dlopen@GLIBC_2.2.5 + 0
000000000000 R_X86_64_JUMP_SLO 0000000000000000 fcntl@GLIBC_2.17 + 0
"""

TOO_NEW_SAMPLE = READELF_SAMPLE + """
000000000000 R_X86_64_JUMP_SLO 0000000000000000 renameat2@GLIBC_2.28 + 0
"""


@pytest.fixture(scope="module")
def checker():
    spec = importlib.util.spec_from_file_location(
        "check_glibc_floor", REPO_ROOT / "scripts" / "check_glibc_floor.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_finds_the_highest_required_glibc_version(checker):
    assert checker.highest_glibc(READELF_SAMPLE) == (2, 17)


def test_versions_compare_numerically_not_lexically(checker):
    # "2.9" must not outrank "2.28"; a string sort would get this backwards.
    sample = "foo@GLIBC_2.9\nbar@GLIBC_2.28\n"
    assert checker.highest_glibc(sample) == (2, 28)


def test_no_glibc_references_means_no_floor(checker):
    assert checker.highest_glibc("no symbols here") is None


def test_a_binary_within_the_floor_passes(checker):
    assert checker.verify(READELF_SAMPLE, "2.27") == 0


def test_a_binary_above_the_floor_fails(checker):
    assert checker.verify(TOO_NEW_SAMPLE, "2.27") == 1


def test_the_boundary_version_itself_is_allowed(checker):
    # Ubuntu 18.04 is exactly 2.27, so 2.27 must pass.
    assert checker.verify("x@GLIBC_2.27", "2.27") == 0


def test_parse_version_handles_two_and_three_components(checker):
    assert checker.parse_version("2.27") == (2, 27)
    assert checker.parse_version("2.2.5") == (2, 2)
