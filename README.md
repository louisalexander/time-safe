# time-safe

Timelock-encrypt secrets, store the ciphertext in a GitHub repo, and reveal them only **after a chosen date** — enforced cryptographically by [drand](https://drand.love)/[tlock](https://github.com/drand/tlock), not by an honour system. No decryption key is ever stored: until the target time, *nobody* (not you, not GitHub, not an attacker with the repo) can decrypt.

A terminal app (Textual). Python rewrite of the original Java version.

## How it works

- Each secret is **timelock-encrypted to a future drand round** (the "quicknet" beacon). The round's threshold-BLS signature — the only thing that can decrypt — doesn't exist until that wall-clock time.
- The ciphertext (`vault/secrets/<id>.tle`) lives in a GitHub repo (your "vault"). There are **no key files**.
- **Reveal** happens locally: once unlocked, the app fetches the ciphertext + the public drand signature and decrypts in memory. The plaintext never touches disk.
- **Email delivery** (optional): a per-secret GitHub Actions workflow runs `tle -d` at/after the unlock time and emails the plaintext via the Gmail API. Before the unlock time, decryption simply fails and nothing is sent.

The only thing stored on your machine is a list of vaults (`~/.timesafe/vaults.json`); GitHub tokens live in your OS keychain.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- The drand **`tle`** binary on your `PATH` (or `$TIMESAFE_TLE`, or `./.tools/tle`). Download from the [tlock releases](https://github.com/drand/tlock/releases):
  ```bash
  mkdir -p .tools
  curl -sL https://github.com/drand/tlock/releases/download/v1.2.0/tlock_1.2.0_darwin_arm64.tar.gz | tar -xz -C .tools tle
  ```
- A **private** GitHub repo to use as a vault, and a fine-grained PAT with `contents` + `secrets` + `workflows` write access.

## Install & run

```bash
uv sync
uv run timesafe
```

In the app: **Initialize new vault** (`n`) with a name, `owner/repo`, and your PAT. You'll then be taken to **Link Gmail** (optional — only needed for email delivery). Add secrets with `a`; open a ready secret and **Reveal** (`d`) it locally or **Email it** (`s`).

## Gmail delivery setup (one-time, optional)

Email delivery uses **your own** Google Cloud OAuth client (so refresh tokens don't expire and no Google verification is needed for personal use):

1. In the [Google Cloud Console](https://console.cloud.google.com), create (or reuse) a project and **enable the Gmail API**.
2. Configure the OAuth consent screen: **External**, scope `https://www.googleapis.com/auth/gmail.send`. Either add your vault Gmail address under **Test users**, or **Publish** the app (publishing avoids the 7-day refresh-token expiry; an unverified app just shows a warning you click through).
3. Create an **OAuth client ID** of type **"Desktop app"**. (Not "TVs and Limited Input devices" — Google's device flow rejects the `gmail.send` scope; time-safe uses the loopback/installed-app flow instead.) Note the client id and client secret.
4. In time-safe, run **Re-link Gmail** (`g`) or the link step during init: enter your Gmail address + the client id/secret, then press **Link**. Your browser opens to Google's consent screen; approve "Send email on your behalf," and the app captures the result on a temporary localhost port.

The refresh token and client secret are stored **only** as GitHub Actions secrets in the vault repo (`GMAIL_REFRESH_TOKEN`, `OAUTH_CLIENT_SECRET`, `OAUTH_CLIENT_ID`, `GMAIL_ADDRESS`) — never written locally.

## Security model

- Confidentiality **before** the unlock time is cryptographic (drand threshold). The repo can even be seen without leaking secrets early.
- **After** unlock, anyone with repo read access can decrypt — so keep the vault repo **private**.
- Trust assumptions: the drand threshold isn't compromised before the unlock time, and drand mainnet stays live (it's a robust multi-org network; the chain hash is pinned per secret).
- A real time-lock means the unlock time is **immutable** — there is no "extend"; to re-time a secret you reveal it after unlock and add it again.

## Development

```bash
uv run pytest                  # unit + Textual snapshot/Pilot tests
TIMESAFE_LIVE=1 uv run pytest tests/test_tle.py -k roundtrip   # live drand roundtrip
```
