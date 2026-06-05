import base64
import hashlib
import threading
import time
import urllib.parse
import urllib.request

import httpx
import respx

from timesafe.oauth import loopback_flow as lf


def test_pkce_challenge_is_s256_of_verifier():
    verifier, challenge = lf.pkce_pair()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected


def test_build_auth_url_has_required_params():
    url = lf.build_auth_url("cid", "http://127.0.0.1:1234", "chal", "st")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert q["client_id"] == ["cid"]
    assert q["redirect_uri"] == ["http://127.0.0.1:1234"]
    assert q["response_type"] == ["code"]
    assert q["scope"] == [lf.SCOPE]
    assert q["code_challenge_method"] == ["S256"]
    assert q["access_type"] == ["offline"]


def test_exchange_code_body_uses_auth_code_grant():
    body = lf.exchange_code_body("cid", "csec", "CODE", "http://127.0.0.1:1", "ver")
    assert body["grant_type"] == "authorization_code"
    assert body["code"] == "CODE"
    assert body["code_verifier"] == "ver"
    assert body["client_secret"] == "csec"


@respx.mock
def test_run_completes_the_loopback_and_returns_refresh_token():
    respx.post(lf.TOKEN_ENDPOINT).respond(json={"refresh_token": "rt", "access_token": "at"})

    def on_prompt(url: str) -> None:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        redirect, state = q["redirect_uri"][0], q["state"][0]

        def hit():
            time.sleep(0.2)  # let run() reach handle_request()
            urllib.request.urlopen(f"{redirect}/?code=AUTHCODE&state={state}")

        threading.Thread(target=hit, daemon=True).start()

    with httpx.Client() as client:
        token = lf.run("cid", "csec", on_prompt, open_browser=False, client=client, timeout=5)
    assert token == "rt"
