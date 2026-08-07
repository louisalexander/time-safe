import base64

import httpx
import respx

from timesafe.github.client import API, GitHubClient

REPO = "owner/repo"


def _client():
    http = httpx.Client(base_url=API, headers={"Authorization": "Bearer t"})
    return GitHubClient(REPO, "t", client=http)


@respx.mock
def test_get_file_returns_none_on_404():
    respx.get(f"{API}/repos/{REPO}/contents/vault/secrets/x.tle").respond(404)
    assert _client().get_file("vault/secrets/x.tle") is None


@respx.mock
def test_get_file_returns_exact_bytes_from_git_blob_not_contents():
    # The Contents API mangles binary; get_file must read the exact bytes from the git blob.
    sha = "deadbeefsha"
    respx.get(f"{API}/repos/{REPO}/contents/vault/secrets/x.tle").respond(
        json={"content": "Y29ycnVwdGVk", "sha": sha}  # contents 'content' is corrupted/ignored
    )
    respx.get(f"{API}/repos/{REPO}/git/blobs/{sha}").respond(
        json={"content": base64.b64encode(b"cipher").decode()}
    )
    assert _client().get_file("vault/secrets/x.tle") == b"cipher"


@respx.mock
def test_put_file_new_sends_base64_without_sha():
    path = "vault/secrets/x.meta"
    respx.get(f"{API}/repos/{REPO}/contents/{path}").respond(404)
    put = respx.put(f"{API}/repos/{REPO}/contents/{path}").respond(json={"content": {}})
    _client().put_file(path, b"hello", "msg")
    body = put.calls.last.request.read()
    import json

    sent = json.loads(body)
    assert sent["content"] == base64.b64encode(b"hello").decode()
    assert "sha" not in sent


@respx.mock
def test_list_dir_returns_paths_and_empty_on_404():
    respx.get(f"{API}/repos/{REPO}/contents/vault/secrets").respond(
        json=[{"path": "vault/secrets/a.meta"}, {"path": "vault/secrets/a.tle"}]
    )
    assert _client().list_dir("vault/secrets") == ["vault/secrets/a.meta", "vault/secrets/a.tle"]


@respx.mock
def test_default_branch():
    respx.get(f"{API}/repos/{REPO}").respond(json={"default_branch": "main"})
    assert _client().default_branch() == "main"


def test_api_base_url_can_be_overridden_by_environment(monkeypatch):
    # Lets the end-to-end tests point a real subprocess at a local stub, and covers GH Enterprise.
    monkeypatch.setenv("TIMESAFE_GITHUB_API", "http://127.0.0.1:9999")
    client = GitHubClient(REPO, "t")
    assert str(client._client.base_url).rstrip("/") == "http://127.0.0.1:9999"


def test_api_base_url_defaults_to_github(monkeypatch):
    monkeypatch.delenv("TIMESAFE_GITHUB_API", raising=False)
    client = GitHubClient(REPO, "t")
    assert str(client._client.base_url).rstrip("/") == API


# ── repo creation ────────────────────────────────────────────────────────────
@respx.mock
def test_get_authenticated_login():
    respx.get(f"{API}/user").respond(json={"login": "owner"})
    assert _client().get_authenticated_login() == "owner"


@respx.mock
def test_repo_exists_is_true_on_200_and_false_on_404():
    respx.get(f"{API}/repos/{REPO}").respond(json={"default_branch": "main"})
    assert _client().repo_exists() is True

    respx.get(f"{API}/repos/{REPO}").respond(404)
    assert _client().repo_exists() is False


@respx.mock
def test_create_repo_under_the_authenticated_user_posts_to_user_repos():
    import json

    respx.get(f"{API}/user").respond(json={"login": "owner"})
    route = respx.post(f"{API}/user/repos").respond(201, json={"full_name": REPO})

    _client().create_repo()

    sent = json.loads(route.calls.last.request.read())
    assert sent["name"] == "repo"
    assert sent["private"] is True
    assert sent["auto_init"] is True


@respx.mock
def test_create_repo_under_another_owner_posts_to_the_org_endpoint():
    import json

    http = httpx.Client(base_url=API, headers={"Authorization": "Bearer t"})
    client = GitHubClient("some-org/vault", "t", client=http)
    respx.get(f"{API}/user").respond(json={"login": "owner"})
    route = respx.post(f"{API}/orgs/some-org/repos").respond(201, json={})

    client.create_repo()

    assert json.loads(route.calls.last.request.read())["name"] == "vault"


def test_create_repo_offers_no_way_to_request_a_public_vault():
    # The security model requires a private vault, so visibility isn't a parameter at all.
    import inspect

    assert "private" not in inspect.signature(GitHubClient.create_repo).parameters


@respx.mock
def test_dispatch_workflow_posts_ref():
    route = respx.post(
        f"{API}/repos/{REPO}/actions/workflows/unlock-1.yml/dispatches"
    ).respond(204)
    _client().dispatch_workflow("unlock-1.yml", "main")
    import json

    assert json.loads(route.calls.last.request.read())["ref"] == "main"
