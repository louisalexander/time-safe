from timesafe.config.credentials import InMemoryCredentialStore, service_name


def test_service_is_repo_scoped():
    assert service_name("owner/repo") == "timesafe:owner/repo"


def test_in_memory_put_get_delete():
    s = InMemoryCredentialStore()
    assert s.get("owner/repo") is None
    s.put("owner/repo", "ghp_x")
    assert s.get("owner/repo") == "ghp_x"
    s.put("owner/repo", "ghp_y")  # upsert
    assert s.get("owner/repo") == "ghp_y"
    s.delete("owner/repo")
    assert s.get("owner/repo") is None
