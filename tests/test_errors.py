import pytest

from timesafe.errors import (
    AmbiguousNameError,
    EmptyStdinError,
    NetworkError,
    NotFoundError,
    NotReadyError,
    TimesafeError,
    UsageError,
    VaultError,
)


def test_each_error_carries_its_documented_exit_code():
    assert UsageError("x").exit_code == 2
    assert NotReadyError("x").exit_code == 3
    assert VaultError("x").exit_code == 4
    assert NotFoundError("x").exit_code == 5


def test_each_error_carries_its_machine_readable_code():
    assert UsageError("x").code == "usage"
    assert NotReadyError("x").code == "not_ready"
    assert VaultError("x").code == "vault"
    assert NotFoundError("x").code == "not_found"


def test_to_json_is_error_plus_code():
    assert NotFoundError("no secret with that id").to_json() == {
        "error": "no secret with that id",
        "code": "not_found",
    }


def test_extra_fields_are_merged_into_the_json():
    exc = AmbiguousNameError("2 secrets named break-glass", ids=["a", "b"])
    assert exc.to_json() == {
        "error": "2 secrets named break-glass",
        "code": "ambiguous_name",
        "ids": ["a", "b"],
    }


def test_empty_stdin_and_ambiguous_name_are_usage_errors():
    # Both must exit 2 while staying distinguishable by `code`.
    for exc in (EmptyStdinError("empty"), AmbiguousNameError("ambiguous")):
        assert isinstance(exc, UsageError)
        assert exc.exit_code == 2
    assert EmptyStdinError("empty").code == "empty_stdin"
    assert AmbiguousNameError("ambiguous").code == "ambiguous_name"


def test_network_is_a_vault_error_with_its_own_code():
    exc = NetworkError("connection reset")
    assert isinstance(exc, VaultError)
    assert exc.exit_code == 4
    assert exc.code == "network"


def test_all_errors_share_one_catchable_base():
    for cls in (UsageError, NotReadyError, VaultError, NotFoundError):
        with pytest.raises(TimesafeError):
            raise cls("boom")


def test_str_is_the_bare_message_so_it_never_leaks_structure():
    assert str(VaultError("could not reach github")) == "could not reach github"
