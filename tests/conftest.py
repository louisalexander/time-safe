import pytest

from tests.fakes import fake_timelock


@pytest.fixture
def faked(monkeypatch):
    """Fake drand (no network) and tlock (reversible 'CT:' prefix) so vault logic is hermetic."""
    fake_timelock(monkeypatch)
    # secrets_api.seal is called by relink; replace with identity so no real crypto in these tests
    monkeypatch.setattr("timesafe.vault.vault.seal", lambda pk, v: f"sealed:{v}")
