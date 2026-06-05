import httpx
import respx

from timesafe.oauth import device_flow as df


def test_device_code_body_has_client_id_and_scope():
    body = df.device_code_body("client-123")
    assert "client_id=client-123" in body
    assert "scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.send" in body


def test_token_poll_body_uses_device_grant():
    body = df.token_poll_body("cid", "csec", "DEV")
    assert "device_code=DEV" in body
    assert "grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Adevice_code" in body


def test_parse_device_code_prefers_url_then_uri():
    dc = df.parse_device_code(
        {"device_code": "D", "user_code": "WDJB-MJHT", "verification_url": "https://g/device", "interval": 7}
    )
    assert dc.user_code == "WDJB-MJHT"
    assert dc.verification_url == "https://g/device"
    assert dc.interval == 7
    dc2 = df.parse_device_code(
        {"device_code": "D", "user_code": "U", "verification_uri": "https://g/device"}
    )
    assert dc2.verification_url == "https://g/device"
    assert dc2.interval == 5


def test_classify_poll():
    assert df.classify_poll(400, {"error": "authorization_pending"}) is df.PollStatus.PENDING
    assert df.classify_poll(400, {"error": "slow_down"}) is df.PollStatus.SLOW_DOWN
    assert df.classify_poll(200, {"refresh_token": "rt"}) is df.PollStatus.DONE
    assert df.classify_poll(400, {"error": "access_denied"}) is df.PollStatus.ERROR


@respx.mock
def test_run_polls_until_refresh_token(monkeypatch):
    respx.post(df.DEVICE_CODE_ENDPOINT).respond(
        json={"device_code": "DEV", "user_code": "WDJB-MJHT", "verification_url": "https://g/device", "interval": 1}
    )
    respx.post(df.TOKEN_ENDPOINT).mock(
        side_effect=[
            httpx.Response(428, json={"error": "authorization_pending"}),
            httpx.Response(200, json={"refresh_token": "rt-value", "access_token": "at"}),
        ]
    )
    prompts = []
    with httpx.Client() as client:
        token = df.run(
            "cid", "csec", prompts.append, client=client, sleep=lambda s: None
        )
    assert token == "rt-value"
    assert prompts and prompts[0].user_code == "WDJB-MJHT"
