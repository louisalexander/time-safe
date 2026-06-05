from __future__ import annotations

import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import httpx

DEVICE_CODE_ENDPOINT = "https://oauth2.googleapis.com/device/code"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/gmail.send"
DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
_FORM = {"Content-Type": "application/x-www-form-urlencoded"}


@dataclass(frozen=True)
class DeviceCode:
    device_code: str
    user_code: str
    verification_url: str
    interval: int


class PollStatus(Enum):
    PENDING = "pending"
    SLOW_DOWN = "slow_down"
    DONE = "done"
    ERROR = "error"


class DeviceAuthError(Exception):
    pass


# ── pure helpers ──────────────────────────────────────────────────────────────
def device_code_body(client_id: str) -> str:
    return urllib.parse.urlencode({"client_id": client_id, "scope": SCOPE})


def token_poll_body(client_id: str, client_secret: str, device_code: str) -> str:
    return urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "device_code": device_code,
            "grant_type": DEVICE_GRANT,
        }
    )


def parse_device_code(data: dict) -> DeviceCode:
    url = data.get("verification_url") or data["verification_uri"]
    return DeviceCode(
        device_code=data["device_code"],
        user_code=data["user_code"],
        verification_url=url,
        interval=int(data.get("interval", 5)),
    )


def classify_poll(status_code: int, data: dict) -> PollStatus:
    if status_code == 200 and "refresh_token" in data:
        return PollStatus.DONE
    error = data.get("error")
    if error == "authorization_pending":
        return PollStatus.PENDING
    if error == "slow_down":
        return PollStatus.SLOW_DOWN
    return PollStatus.ERROR


# ── live driver ───────────────────────────────────────────────────────────────
def run(
    client_id: str,
    client_secret: str,
    on_prompt: Callable[[DeviceCode], None],
    *,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
    deadline_seconds: int = 600,
) -> str:
    """Run the RFC 8628 device flow. Calls on_prompt(device_code), polls, returns the refresh token."""
    http = client or httpx.Client(timeout=30)
    resp = http.post(DEVICE_CODE_ENDPOINT, content=device_code_body(client_id), headers=_FORM)
    resp.raise_for_status()
    device = parse_device_code(resp.json())
    on_prompt(device)

    interval = max(device.interval, 5)
    waited = 0
    while waited < deadline_seconds:
        sleep(interval)
        waited += interval
        poll = http.post(
            TOKEN_ENDPOINT,
            content=token_poll_body(client_id, client_secret, device.device_code),
            headers=_FORM,
        )
        data = poll.json()
        status = classify_poll(poll.status_code, data)
        if status is PollStatus.DONE:
            return data["refresh_token"]
        if status is PollStatus.SLOW_DOWN:
            interval += 5
        elif status is PollStatus.PENDING:
            continue
        else:
            raise DeviceAuthError(str(data))
    raise DeviceAuthError("device authorization timed out")
