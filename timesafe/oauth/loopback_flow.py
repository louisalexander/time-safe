from __future__ import annotations

import base64
import hashlib
import http.server
import secrets
import urllib.parse
import webbrowser
from collections.abc import Callable

import httpx

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/gmail.send"


class OAuthError(Exception):
    pass


# ── pure helpers ──────────────────────────────────────────────────────────────
def pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE S256."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def build_auth_url(client_id: str, redirect_uri: str, code_challenge: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return AUTH_ENDPOINT + "?" + urllib.parse.urlencode(params)


def exchange_code_body(
    client_id: str, client_secret: str, code: str, redirect_uri: str, code_verifier: str
) -> dict:
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
    }


# ── live driver ───────────────────────────────────────────────────────────────
class _RedirectHandler(http.server.BaseHTTPRequestHandler):
    captured: dict = {}

    def do_GET(self):  # noqa: N802 - http.server API
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _RedirectHandler.captured = {k: v[0] for k, v in params.items()}
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body>time-safe: Gmail linked. You can close this tab.</body></html>")

    def log_message(self, *args):  # silence default logging
        pass


def run(
    client_id: str,
    client_secret: str,
    on_prompt: Callable[[str], None] | None = None,
    *,
    open_browser: bool = True,
    client: httpx.Client | None = None,
    timeout: int = 300,
) -> str:
    """Loopback OAuth flow: open the browser, capture the redirect on a local port, return a refresh token."""
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)

    server = http.server.HTTPServer(("127.0.0.1", 0), _RedirectHandler)
    server.timeout = timeout
    redirect_uri = f"http://127.0.0.1:{server.server_address[1]}"
    auth_url = build_auth_url(client_id, redirect_uri, challenge, state)

    if on_prompt:
        on_prompt(auth_url)
    if open_browser:
        webbrowser.open(auth_url)

    _RedirectHandler.captured = {}
    server.handle_request()  # blocks until the redirect arrives (or timeout)
    server.server_close()

    captured = _RedirectHandler.captured
    if captured.get("state") != state:
        raise OAuthError("authorization state mismatch (or timed out before redirect)")
    code = captured.get("code")
    if not code:
        error = captured.get("error", "no authorization code received")
        raise OAuthError(error)

    http_client = client or httpx.Client(timeout=30)
    resp = http_client.post(
        TOKEN_ENDPOINT,
        data=exchange_code_body(client_id, client_secret, code, redirect_uri, verifier),
    )
    resp.raise_for_status()
    data = resp.json()
    if "refresh_token" not in data:
        raise OAuthError("no refresh_token returned — revoke prior access and re-consent.")
    return data["refresh_token"]
