import keyring.errors
import pytest

from timesafe import resolve
from timesafe.config.credentials import InMemoryCredentialStore
from timesafe.config.registry import VaultRef, VaultRegistry
from timesafe.errors import UsageError, VaultError


def _registry(tmp_path, *refs):
    return VaultRegistry(list(refs), tmp_path / "vaults.json")


# ── repo selection ───────────────────────────────────────────────────────────
def test_explicit_owner_repo_selector_wins(tmp_path):
    reg = _registry(tmp_path, VaultRef("work", "me/work"))
    assert resolve.resolve_repo("other/vault", reg, {"TIMESAFE_VAULT": "me/work"}) == "other/vault"


def test_selector_may_be_a_registry_name(tmp_path):
    reg = _registry(tmp_path, VaultRef("seedbox", "me/seedbox-vault"))
    assert resolve.resolve_repo("seedbox", reg, {}) == "me/seedbox-vault"


def test_unregistered_bare_name_is_a_usage_error(tmp_path):
    reg = _registry(tmp_path, VaultRef("work", "me/work"))
    with pytest.raises(UsageError) as exc:
        resolve.resolve_repo("nope", reg, {})
    assert "nope" in str(exc.value)


def test_env_is_used_when_no_selector_is_given(tmp_path):
    reg = _registry(tmp_path, VaultRef("work", "me/work"), VaultRef("home", "me/home"))
    # Two registered vaults would otherwise be ambiguous; the env var settles it.
    assert resolve.resolve_repo(None, reg, {"TIMESAFE_VAULT": "me/home"}) == "me/home"


def test_a_lone_registered_vault_is_used_implicitly(tmp_path):
    reg = _registry(tmp_path, VaultRef("only", "me/only"))
    assert resolve.resolve_repo(None, reg, {}) == "me/only"


def test_two_registered_vaults_with_no_selector_is_a_hard_error(tmp_path):
    reg = _registry(tmp_path, VaultRef("work", "me/work"), VaultRef("home", "me/home"))
    with pytest.raises(UsageError) as exc:
        resolve.resolve_repo(None, reg, {})
    # It must list the candidates rather than silently picking one.
    assert exc.value.extra["vaults"] == ["work", "home"]
    assert exc.value.exit_code == 2


def test_no_registered_vaults_and_no_selector_is_a_usage_error(tmp_path):
    with pytest.raises(UsageError) as exc:
        resolve.resolve_repo(None, _registry(tmp_path), {})
    assert "TIMESAFE_VAULT" in str(exc.value)


def test_malformed_selector_is_rejected(tmp_path):
    with pytest.raises(UsageError):
        resolve.resolve_repo("a/b/c", _registry(tmp_path), {})


# ── token selection ──────────────────────────────────────────────────────────
def test_env_token_beats_the_keychain():
    store = InMemoryCredentialStore()
    store.put("me/vault", "from-keychain")
    token = resolve.resolve_token("me/vault", store, {"TIMESAFE_GITHUB_TOKEN": "from-env"})
    assert token == "from-env"


def test_keychain_is_used_when_the_env_var_is_absent():
    store = InMemoryCredentialStore()
    store.put("me/vault", "from-keychain")
    assert resolve.resolve_token("me/vault", store, {}) == "from-keychain"


def test_blank_env_token_is_ignored_rather_than_used():
    store = InMemoryCredentialStore()
    store.put("me/vault", "from-keychain")
    assert resolve.resolve_token("me/vault", store, {"TIMESAFE_GITHUB_TOKEN": ""}) == "from-keychain"


def test_no_token_anywhere_is_a_vault_error():
    with pytest.raises(VaultError) as exc:
        resolve.resolve_token("me/vault", InMemoryCredentialStore(), {})
    assert exc.value.exit_code == 4
    assert "TIMESAFE_GITHUB_TOKEN" in str(exc.value)


def test_an_unavailable_keychain_does_not_blow_up():
    """On a headless box keyring raises rather than returning None. That must read as 'no token'."""

    class HeadlessStore(InMemoryCredentialStore):
        def get(self, repo):
            raise keyring.errors.NoKeyringError("no backend")

    with pytest.raises(VaultError):
        resolve.resolve_token("me/vault", HeadlessStore(), {})


def test_the_error_never_contains_the_token():
    store = InMemoryCredentialStore()
    with pytest.raises(VaultError) as exc:
        resolve.resolve_token("me/vault", store, {"TIMESAFE_GITHUB_TOKEN": ""})
    assert "" == store.get("me/vault") or store.get("me/vault") is None
    assert "ghp_" not in str(exc.value)


# ── end to end ───────────────────────────────────────────────────────────────
def test_resolve_vault_builds_a_vault_for_the_chosen_repo_and_token(tmp_path):
    reg = _registry(tmp_path, VaultRef("only", "me/only"))
    store = InMemoryCredentialStore()
    store.put("me/only", "tok")

    vault = resolve.resolve_vault(None, registry=reg, credentials=store, env={})

    assert vault.github.repo == "me/only"


def test_resolve_vault_retries_idempotent_reads_by_default(tmp_path):
    from timesafe.github import retry

    vault = _resolved(tmp_path)
    assert vault.github.retries == retry.ATTEMPTS
    assert vault.github.get_file.__wrapped__  # the read is wrapped, the writes are not


def test_resolve_vault_can_build_a_client_that_does_not_retry(tmp_path):
    vault = _resolved(tmp_path, retries=1)
    assert vault.github.retries == 1
    assert not hasattr(vault.github.get_file, "__wrapped__")


def _resolved(tmp_path, **kwargs):
    store = InMemoryCredentialStore()
    store.put("me/only", "tok")
    return resolve.resolve_vault(
        None,
        registry=_registry(tmp_path, VaultRef("only", "me/only")),
        credentials=store,
        env={},
        **kwargs,
    )
