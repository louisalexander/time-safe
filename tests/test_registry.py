from timesafe.config.registry import VaultRef, VaultRegistry


def test_load_missing_is_empty(tmp_path):
    r = VaultRegistry.load(tmp_path / "vaults.json")
    assert r.vaults == []


def test_add_save_reload(tmp_path):
    p = tmp_path / "vaults.json"
    r = VaultRegistry.load(p)
    r.add(VaultRef("fort-knox", "timesafevault/fort-knox"))
    r.save(p)
    reloaded = VaultRegistry.load(p)
    assert [v.repo for v in reloaded.vaults] == ["timesafevault/fort-knox"]
    assert reloaded.vaults[0].name == "fort-knox"


def test_add_is_idempotent_by_repo():
    r = VaultRegistry([])
    r.add(VaultRef("a", "owner/repo"))
    r.add(VaultRef("b", "owner/repo"))
    assert len(r.vaults) == 1
    assert r.contains("owner/repo")


def test_remove_by_repo():
    r = VaultRegistry([])
    r.add(VaultRef("a", "owner/repo"))
    r.remove("owner/repo")
    assert not r.contains("owner/repo")


def test_save_with_no_arg_round_trips_to_loaded_path(tmp_path):
    p = tmp_path / "vaults.json"
    r = VaultRegistry.load(p)
    r.add(VaultRef("x", "o/x"))
    r.save()  # no path arg → must write back to the path it was loaded from
    assert [v.repo for v in VaultRegistry.load(p).vaults] == ["o/x"]
