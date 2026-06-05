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
def test_get_file_decodes_base64_content():
    payload = base64.b64encode(b"cipher").decode()
    respx.get(f"{API}/repos/{REPO}/contents/vault/secrets/x.tle").respond(
        json={"content": payload, "sha": "abc"}
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


@respx.mock
def test_dispatch_workflow_posts_ref():
    route = respx.post(
        f"{API}/repos/{REPO}/actions/workflows/unlock-1.yml/dispatches"
    ).respond(204)
    _client().dispatch_workflow("unlock-1.yml", "main")
    import json

    assert json.loads(route.calls.last.request.read())["ref"] == "main"
