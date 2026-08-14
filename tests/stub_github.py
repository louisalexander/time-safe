"""A minimal in-process stand-in for the GitHub REST endpoints time-safe uses.

Only exists so the end-to-end tests can run the real `timesafe` executable, over real pipes, in a
real subprocess — the only way to prove the no-TTY/cron contract. Backed by a plain dict.
"""

from __future__ import annotations

import base64
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

REPO = "owner/vault"


class _State:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def sha(self, path: str) -> str:
        return hashlib.sha1(path.encode()).hexdigest()


def _handler(state: _State):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # keep the test output clean
            pass

        def _send(self, status: int, payload=None):
            body = b"" if payload is None else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)

        def _path_after(self, prefix: str) -> str:
            return self.path.split(prefix, 1)[1] if prefix in self.path else ""

        def do_GET(self):  # noqa: N802
            if self.path == f"/repos/{REPO}":
                return self._send(200, {"default_branch": "main", "full_name": REPO})
            if self.path == "/user":
                return self._send(200, {"login": "owner"})
            if "/git/blobs/" in self.path:
                wanted = self.path.rsplit("/", 1)[1]
                for path, content in state.files.items():
                    if state.sha(path) == wanted:
                        return self._send(
                            200, {"content": base64.b64encode(content).decode()}
                        )
                return self._send(404, {"message": "Not Found"})

            path = self._path_after(f"/repos/{REPO}/contents/")
            if path in state.files:
                # Model the Contents API's charset detection: UTF-8 comes back intact, binary comes
                # back re-encoded and corrupted. That is the whole reason get_file pays for the git
                # blob and get_text_file does not, so the stub has to reproduce it or the
                # end-to-end tests would pass against a client that got the distinction wrong.
                content = state.files[path]
                try:
                    content.decode("utf-8")
                except UnicodeDecodeError:
                    inlined = base64.b64encode(content.decode("latin-1").encode("utf-16")).decode()
                else:
                    inlined = base64.b64encode(content).decode()
                return self._send(
                    200,
                    {
                        "sha": state.sha(path),
                        "content": inlined,
                        "encoding": "base64",
                        "path": path,
                    },
                )
            children = [p for p in state.files if p.startswith(path.rstrip("/") + "/")]
            if children:
                return self._send(200, [{"path": p, "sha": state.sha(p)} for p in sorted(children)])
            return self._send(404, {"message": "Not Found"})

        def do_PUT(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            path = self._path_after(f"/repos/{REPO}/contents/")
            state.files[path] = base64.b64decode(body["content"])
            return self._send(200, {"content": {"path": path}})

        def do_DELETE(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            path = self._path_after(f"/repos/{REPO}/contents/")
            state.files.pop(path, None)
            return self._send(200, {})

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            return self._send(201, {})

    return Handler


class StubGitHub:
    """Context manager yielding a running stub. `url` is what $TIMESAFE_GITHUB_API should be set to."""

    def __init__(self) -> None:
        self.state = _State()
        self._server = HTTPServer(("127.0.0.1", 0), _handler(self.state))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    @property
    def files(self) -> dict[str, bytes]:
        return self.state.files

    def __enter__(self) -> "StubGitHub":
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)
