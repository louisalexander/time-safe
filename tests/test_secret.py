from datetime import datetime, timedelta, timezone

from timesafe.vault.secret import Secret


def _future(**kw):
    return datetime.now(timezone.utc) + timedelta(**kw)


def test_create_assigns_id_and_created_at():
    s = Secret.create("My Secret", _future(days=7), 999999, "chainhash", "a@b.co")
    assert s.id
    assert s.name == "My Secret"
    assert s.delivery_email == "a@b.co"
    assert s.created_at.tzinfo is not None


def test_meta_json_round_trip():
    s = Secret.create("Round", _future(days=30), 123456, "chainhash", "x@y.z")
    loaded = Secret.from_meta_json(s.to_meta_json())
    assert loaded.id == s.id
    assert loaded.name == s.name
    assert loaded.drand_round == 123456
    assert loaded.drand_chain == "chainhash"
    assert loaded.delivery_email == "x@y.z"
    assert loaded.unlock_at == s.unlock_at


def test_from_meta_tolerates_absent_delivery_email():
    s = Secret.create("NoEmail", _future(days=1), 1, "c")
    loaded = Secret.from_meta_json(s.to_meta_json())
    assert loaded.delivery_email is None


def test_is_ready():
    past = Secret.create("Past", datetime.now(timezone.utc) - timedelta(seconds=1), 1, "c")
    future = Secret.create("Future", _future(days=1), 1, "c")
    assert past.is_ready()
    assert not future.is_ready()
