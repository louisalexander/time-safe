from __future__ import annotations

from timesafe.timelock.tle import TLE_VERSION
from timesafe.vault.secret import Secret

# Built from the single pinned version in timelock/tle.py so the runner and the local binary can
# never drift apart.
TLE_RELEASE = (
    f"https://github.com/drand/tlock/releases/download/v{TLE_VERSION}"
    f"/tlock_{TLE_VERSION}_linux_amd64.tar.gz"
)

_WORKFLOW_TEMPLATE = """\
name: Unlock __NAME__
on:
  workflow_dispatch:
jobs:
  send-secret:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      issues: write
    steps:
      - uses: actions/checkout@v4
      - name: Install tle
        run: curl -sL __TLE_RELEASE__ | sudo tar -xz -C /usr/local/bin tle
      - name: Decrypt and email
        env:
          UUID: __UUID__
          SECRET_NAME: __NAME__
          DELIVERY_EMAIL: __EMAIL__
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_REFRESH_TOKEN: ${{ secrets.GMAIL_REFRESH_TOKEN }}
          OAUTH_CLIENT_ID: ${{ secrets.OAUTH_CLIENT_ID }}
          OAUTH_CLIENT_SECRET: ${{ secrets.OAUTH_CLIENT_SECRET }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
        run: python3 vault/scripts/send_secret.py
"""


def build_unlock_workflow_yaml(secret: Secret) -> str:
    """The per-secret, dispatch-only workflow that tlock-decrypts at T and emails the plaintext."""
    return (
        _WORKFLOW_TEMPLATE.replace("__TLE_RELEASE__", TLE_RELEASE)
        .replace("__UUID__", secret.id)
        .replace("__NAME__", secret.name)
        .replace("__EMAIL__", secret.delivery_email or "")
    )


# Stdlib-only delivery script. tlock decryption IS the server-side time gate: if the round hasn't
# arrived, `tle -d` errors "too early" and we exit 0 without sending.
SEND_SECRET_SCRIPT = r'''import os, sys, json, base64, subprocess
import urllib.request, urllib.error, urllib.parse
from email.message import EmailMessage

uuid     = os.environ["UUID"]
name     = os.environ["SECRET_NAME"]
delivery = os.environ["DELIVERY_EMAIL"]
gmail    = os.environ["GMAIL_ADDRESS"]
refresh  = os.environ["GMAIL_REFRESH_TOKEN"]
cid      = os.environ["OAUTH_CLIENT_ID"]
csec     = os.environ["OAUTH_CLIENT_SECRET"]


def open_reauth_issue(detail):
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("Cannot open issue: GITHUB_TOKEN/REPOSITORY missing")
        return
    body = json.dumps({
        "title": "time-safe: Gmail re-authorization required",
        "body": "The Gmail refresh token was rejected. Run 'Re-link Gmail' "
                "in the time-safe app to restore delivery.\n\nDetail: " + detail,
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/repos/" + repo + "/issues", data=body, method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    try:
        urllib.request.urlopen(req)
        print("Opened re-authorization issue.")
    except Exception as e:
        print("Failed to open issue:", e)


# tlock decrypt — the time gate.
p = subprocess.run(["tle", "-d", "vault/secrets/" + uuid + ".tle"], capture_output=True)
if p.returncode != 0:
    err = p.stderr.decode("utf-8", "replace")
    if "too early" in err.lower():
        print("Not yet unlocked:", err.strip())
        sys.exit(0)
    print("Decrypt failed:", err.strip())
    sys.exit(1)
plaintext = p.stdout.decode("utf-8", "replace")

# Exchange the refresh token for an access token.
token_body = urllib.parse.urlencode({
    "client_id": cid, "client_secret": csec,
    "refresh_token": refresh, "grant_type": "refresh_token",
}).encode()
treq = urllib.request.Request("https://oauth2.googleapis.com/token", data=token_body)
treq.add_header("Content-Type", "application/x-www-form-urlencoded")
try:
    with urllib.request.urlopen(treq) as r:
        access_token = json.loads(r.read())["access_token"]
except urllib.error.HTTPError as e:
    detail = e.read().decode("utf-8", "replace")
    print("Token exchange failed (%s): %s" % (e.code, detail))
    if e.code in (400, 401):
        open_reauth_issue(detail)
    sys.exit(1)

# Send the plaintext via the Gmail API.
msg = EmailMessage()
msg["Subject"] = "Vault Unlock: " + name
msg["From"] = gmail
msg["To"] = delivery
msg.set_content(
    'Your time-safe secret "%s" has unlocked.\n\n%s\n' % (name, plaintext))
raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
sreq = urllib.request.Request(
    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
    data=json.dumps({"raw": raw}).encode(), method="POST")
sreq.add_header("Authorization", "Bearer " + access_token)
sreq.add_header("Content-Type", "application/json")
try:
    urllib.request.urlopen(sreq)
    print("Secret delivered.")
except urllib.error.HTTPError as e:
    detail = e.read().decode("utf-8", "replace")
    print("Gmail send failed (%s): %s" % (e.code, detail))
    if e.code in (400, 401):
        open_reauth_issue(detail)
    sys.exit(1)
'''
