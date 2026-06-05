from __future__ import annotations

import base64

import httpx

API = "https://api.github.com"


class GitHubClient:
    """Thin httpx wrapper over the handful of GitHub REST endpoints time-safe needs."""

    def __init__(self, repo: str, token: str, client: httpx.Client | None = None) -> None:
        self.repo = repo
        self._client = client or httpx.Client(
            base_url=API,
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
