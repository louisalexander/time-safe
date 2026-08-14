from __future__ import annotations

import base64
import os

import httpx

API = "https://api.github.com"
API_ENV = "TIMESAFE_GITHUB_API"


class GitHubClient:
    """Thin httpx wrapper over the handful of GitHub REST endpoints time-safe needs."""

    def __init__(self, repo: str, token: str, client: httpx.Client | None = None) -> None:
        self.repo = repo
        # $TIMESAFE_GITHUB_API points at a different API root — GitHub Enterprise, or the stub
        # server the end-to-end tests run a real subprocess against.
        self._client = client or httpx.Client(
            base_url=os.environ.get(API_ENV) or API,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    # ── contents ──────────────────────────────────────────────────────────────
    def _contents(self, path: str) -> str:
        return f"/repos/{self.repo}/contents/{path}"

    def get_file(self, path: str) -> bytes | None:
        r = self._client.get(self._contents(path))
        if r.status_code == 404:
            return None
        r.raise_for_status()
        # The Contents API charset-detects binary files (e.g. tlock ciphertext) as UTF-16 and
        # returns them re-encoded, corrupting them. Fetch the exact bytes from the git blob instead
        # (the contents response's `sha` is the blob's object id).
        return self._blob(r.json()["sha"])

    def get_text_file(self, path: str) -> bytes | None:
        """Read a UTF-8 file in one request instead of two.

        `get_file` pays for a second round-trip because the Contents API corrupts *binary*
        payloads; text comes back intact, so anything textual — the `.meta` JSON — can be decoded
        straight from the contents response. That halves the cost of every listing.

        Never use this for ciphertext.
        """
        r = self._client.get(self._contents(path))
        if r.status_code == 404:
            return None
        r.raise_for_status()
        body = r.json()
        # Above ~1MB GitHub declines to inline the content and answers with encoding "none".
        # A .meta is never near that, but returning b"" for it would be silent corruption.
        if body.get("encoding") != "base64":
            return self._blob(body["sha"])
        return base64.b64decode(body["content"])

    def _blob(self, sha: str) -> bytes:
        r = self._client.get(f"/repos/{self.repo}/git/blobs/{sha}")
        r.raise_for_status()
        return base64.b64decode(r.json()["content"])

    def _get_sha(self, path: str) -> str | None:
        r = self._client.get(self._contents(path))
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()["sha"]

    def put_file(self, path: str, content: bytes, message: str) -> None:
        body = {"message": message, "content": base64.b64encode(content).decode()}
        sha = self._get_sha(path)
        if sha is not None:
            body["sha"] = sha
        self._client.put(self._contents(path), json=body).raise_for_status()

    def delete_file(self, path: str, message: str) -> None:
        sha = self._get_sha(path)
        if sha is None:
            return
        self._client.request(
            "DELETE", self._contents(path), json={"message": message, "sha": sha}
        ).raise_for_status()

    def list_dir(self, path: str) -> list[str]:
        r = self._client.get(self._contents(path))
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return [item["path"] for item in r.json()]

    # ── repo lifecycle ────────────────────────────────────────────────────────
    def get_authenticated_login(self) -> str:
        r = self._client.get("/user")
        r.raise_for_status()
        return r.json()["login"]

    def repo_exists(self) -> bool:
        r = self._client.get(f"/repos/{self.repo}")
        if r.status_code == 404:
            return False
        r.raise_for_status()
        return True

    def create_repo(self, *, auto_init: bool = True) -> None:
        """Create the vault repo. Always private — the security model depends on it, so there is
        deliberately no way to ask for a public one.

        Personal repos go to /user/repos; anything owned by someone other than the authenticated
        login is treated as an org and goes to /orgs/{owner}/repos.
        """
        owner, _, name = self.repo.partition("/")
        body = {"name": name, "private": True, "auto_init": auto_init}
        endpoint = (
            "/user/repos"
            if owner == self.get_authenticated_login()
            else f"/orgs/{owner}/repos"
        )
        self._client.post(endpoint, json=body).raise_for_status()

    # ── repo / workflows ──────────────────────────────────────────────────────
    def default_branch(self) -> str:
        r = self._client.get(f"/repos/{self.repo}")
        r.raise_for_status()
        return r.json()["default_branch"]

    def dispatch_workflow(self, workflow_filename: str, ref: str) -> None:
        self._client.post(
            f"/repos/{self.repo}/actions/workflows/{workflow_filename}/dispatches",
            json={"ref": ref},
        ).raise_for_status()

    # ── actions secrets ───────────────────────────────────────────────────────
    def actions_public_key(self) -> tuple[str, str]:
        r = self._client.get(f"/repos/{self.repo}/actions/secrets/public-key")
        r.raise_for_status()
        d = r.json()
        return d["key_id"], d["key"]

    def put_actions_secret(self, name: str, encrypted_value: str, key_id: str) -> None:
        self._client.put(
            f"/repos/{self.repo}/actions/secrets/{name}",
            json={"encrypted_value": encrypted_value, "key_id": key_id},
        ).raise_for_status()

    def delete_actions_secret(self, name: str) -> None:
        r = self._client.request("DELETE", f"/repos/{self.repo}/actions/secrets/{name}")
        if r.status_code not in (204, 404):
            r.raise_for_status()
