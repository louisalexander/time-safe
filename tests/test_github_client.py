import base64

import httpx
import pytest
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
def test_get_text_file_reads_the_contents_response_without_a_second_request():
    """Text survives the Contents API intact, so paying for the blob round-trip on every .meta
    doubles the cost of every listing for nothing."""
    path = "vault/secrets/x.meta"
    contents = respx.get(f"{API}/repos/{REPO}/contents/{path}").respond(
        json={"content": base64.b64encode(b'{"id": "x"}').decode(), "encoding": "base64", "sha": "s"}
    )
    blobs = respx.get(f"{API}/repos/{REPO}/git/blobs/s").respond(json={"content": ""})

    assert _client().get_text_file(path) == b'{"id": "x"}'
    assert contents.call_count == 1
    assert blobs.call_count == 0


@respx.mock
def test_get_text_file_returns_none_on_404():
    respx.get(f"{API}/repos/{REPO}/contents/vault/secrets/x.meta").respond(404)
    assert _client().get_text_file("vault/secrets/x.meta") is None


@respx.mock
def test_get_text_file_tolerates_github_declining_to_inline_the_content():
    """Over ~1MB the Contents API answers with encoding 'none' and an empty body. A .meta is never
    that big, but silently returning b'' would be a corrupt secret rather than an error."""
    path = "vault/secrets/x.meta"
    respx.get(f"{API}/repos/{REPO}/contents/{path}").respond(
        json={"content": "", "encoding": "none", "sha": "big"}
    )
    respx.get(f"{API}/repos/{REPO}/git/blobs/big").respond(
        json={"content": base64.b64encode(b"the real bytes").decode()}
    )
    assert _client().get_text_file(path) == b"the real bytes"


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


# ── retry on idempotent reads ────────────────────────────────────────────────
def _retrying_client(slept):
    http = httpx.Client(base_url=API, headers={"Authorization": "Bearer t"})
    return GitHubClient(REPO, "t", client=http, sleep=slept.append)


@respx.mock
def test_a_read_survives_a_transient_5xx():
    slept = []
    respx.get(f"{API}/repos/{REPO}/contents/vault/secrets").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json=[{"path": "vault/secrets/a.meta"}]),
        ]
    )
    assert _retrying_client(slept).list_dir("vault/secrets") == ["vault/secrets/a.meta"]
    assert len(slept) == 1


@respx.mock
def test_the_whole_read_is_retried_not_a_single_request():
    """get_file may take more than one request; a retry re-runs the read, whatever it is made of."""
    slept = []
    sha = "sha1"
    respx.get(f"{API}/repos/{REPO}/contents/vault/secrets/x.tle").mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json={"sha": sha, "content": "x"})]
    )
    respx.get(f"{API}/repos/{REPO}/git/blobs/{sha}").respond(
        json={"content": base64.b64encode(b"cipher").decode()}
    )
    assert _retrying_client(slept).get_file("vault/secrets/x.tle") == b"cipher"


@respx.mock
def test_get_text_file_survives_a_transient_5xx():
    """`.meta` reads go through get_text_file, so this is the path a cron poll actually takes."""
    slept = []
    respx.get(f"{API}/repos/{REPO}/contents/vault/secrets/x.meta").mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(
                200, json={"encoding": "base64", "content": base64.b64encode(b"{}").decode()}
            ),
        ]
    )
    assert _retrying_client(slept).get_text_file("vault/secrets/x.meta") == b"{}"
    assert len(slept) == 1


@respx.mock
def test_every_read_the_polling_path_uses_is_wrapped():
    """A read left out of IDEMPOTENT_READS is silently un-retried, which is the easy mistake."""
    client = GitHubClient(REPO, "t", client=httpx.Client(base_url=API))
    for name in ("get_file", "get_text_file", "list_dir", "repo_exists"):
        assert hasattr(getattr(client, name), "__wrapped__"), f"{name} is not retried"


@respx.mock
def test_repo_exists_survives_a_transient_5xx():
    slept = []
    respx.get(f"{API}/repos/{REPO}").mock(
        side_effect=[httpx.Response(502), httpx.Response(200, json={"default_branch": "main"})]
    )
    assert _retrying_client(slept).repo_exists() is True


@respx.mock
def test_a_404_is_answered_immediately_rather_than_retried():
    slept = []
    route = respx.get(f"{API}/repos/{REPO}/contents/vault/secrets/x.tle").respond(404)
    assert _retrying_client(slept).get_file("vault/secrets/x.tle") is None
    assert route.call_count == 1
    assert slept == []


@respx.mock
def test_a_write_is_never_retried():
    """`add` is not idempotent: a retried write after an ambiguous failure risks a duplicate."""
    slept = []
    path = "vault/secrets/x.meta"
    respx.get(f"{API}/repos/{REPO}/contents/{path}").respond(404)
    put = respx.put(f"{API}/repos/{REPO}/contents/{path}").respond(500)

    with pytest.raises(httpx.HTTPStatusError):
        _retrying_client(slept).put_file(path, b"hello", "msg")

    assert put.call_count == 1
    assert slept == []


@respx.mock
def test_retries_can_be_turned_off():
    slept = []
    http = httpx.Client(base_url=API, headers={"Authorization": "Bearer t"})
    route = respx.get(f"{API}/repos/{REPO}/contents/vault/secrets").respond(503)

    with pytest.raises(httpx.HTTPStatusError):
        GitHubClient(REPO, "t", client=http, retries=1, sleep=slept.append).list_dir("vault/secrets")

    assert route.call_count == 1
    assert slept == []


@respx.mock
def test_dispatch_workflow_posts_ref():
    route = respx.post(
        f"{API}/repos/{REPO}/actions/workflows/unlock-1.yml/dispatches"
    ).respond(204)
    _client().dispatch_workflow("unlock-1.yml", "main")
    import json

    assert json.loads(route.calls.last.request.read())["ref"] == "main"
