<h1 align="center">time-safe</h1>

<p align="center">
  <b>Lock a secret until a future moment — so that <i>nobody</i>, not even you, can read it early.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/TUI-Textual-5A2CA0" alt="Textual">
  <img src="https://img.shields.io/badge/timelock-drand%2Ftlock-F46036" alt="drand/tlock">
  <a href="https://louisalexander.github.io/time-safe/"><img src="https://img.shields.io/badge/docs-GitHub%20Pages-222" alt="Docs"></a>
</p>

<p align="center"><img src="docs/screenshots/02-secrets-list.svg" width="760" alt="time-safe secrets list"></p>

time-safe timelock-encrypts your secrets, stores the ciphertext in a GitHub repo, and lets you reveal them only **after a date you choose**. The time-lock is enforced by cryptography — the [drand](https://drand.love) distributed randomness beacon via [tlock](https://github.com/drand/tlock) — not by an honour system. **No decryption key is ever stored anywhere.** Until the unlock time arrives, the key literally does not exist, so neither you, nor GitHub, nor anyone who copies the repo can decrypt early.

It's a terminal app built with [Textual](https://textual.textualize.io/). (Python rewrite of the original Java version.)

## How it works

- Each secret is **timelock-encrypted to a future drand round**. The round's threshold-BLS signature — the only thing that can decrypt it — isn't produced by the beacon network until that wall-clock time.
- The ciphertext (`vault/secrets/<id>.tle`) lives in a GitHub repo — your "vault." **There are no key files.**
- **Reveal** is local: once the time passes, the app fetches the ciphertext and the now-public drand signature and decrypts in memory. The plaintext never touches disk.
- **Email delivery** (optional): a per-secret GitHub Actions workflow runs `tle -d` at/after the unlock time and emails you the plaintext via the Gmail API. Before then, decryption simply fails and nothing is sent.

The only thing stored on your machine is the list of vaults (`~/.timesafe/vaults.json`). GitHub tokens live in your OS keychain; Gmail credentials live as GitHub Actions secrets.

## Screens

| Vaults | Secret (ready) | Add secret |
|:---:|:---:|:---:|
| <img src="docs/screenshots/01-vault-picker.svg" width="260"> | <img src="docs/screenshots/03-secret-detail-ready.svg" width="260"> | <img src="docs/screenshots/04-add-secret.svg" width="260"> |

## Requirements

- **Python 3.12+** and [uv](https://docs.astral.sh/uv/)
- The drand **`tle`** binary on your `PATH` (or `$TIMESAFE_TLE`, or `./.tools/tle`). From the [tlock releases](https://github.com/drand/tlock/releases):
  ```bash
  mkdir -p .tools
  curl -sL https://github.com/drand/tlock/releases/download/v1.2.0/tlock_1.2.0_darwin_arm64.tar.gz | tar -xz -C .tools tle
  ```
- A **private** GitHub repo for the vault, and a token with `contents` + `secrets` + `workflows` write access.

## Install & run

```bash
uv sync
uv run timesafe
```

In the app:

- **`n`** — initialize a new vault (name, `owner/repo`, token), then optionally **link Gmail**.
- **`c`** — connect to an already-initialized vault.
- **`a`** — add a secret: name, an unlock duration (`30m`, `2h`, `7d`, `1d12h`), an optional delivery email, and the text.
- Open a ready secret → **`d`** reveal it locally, **`s`** email it, or **`r`** renew (re-lock it for a new duration). **`x`** deletes.

## Gmail delivery setup (one-time, optional)

Email uses **your own** Google Cloud OAuth client:

1. [Google Cloud Console](https://console.cloud.google.com): create a project and **enable the Gmail API**.
2. OAuth **consent screen**: External, scope `https://www.googleapis.com/auth/gmail.send`. Add your vault Gmail under **Test users** or **Publish** the app (publishing avoids the 7-day refresh-token expiry).
3. **Credentials → OAuth client ID → "Desktop app."** (Not "TVs and Limited Input devices" — Google's device flow rejects `gmail.send`; time-safe uses the loopback/installed-app flow.) Note the client id + secret.
4. In time-safe press **`g`** (or link during init): enter the Gmail address + client id/secret → **Link** → approve in the browser that opens.

The refresh token + client secret are stored **only** as GitHub Actions secrets in the vault repo — never locally.

## Security model

- Confidentiality **before** the unlock time is cryptographic (drand threshold) — the repo can be seen without leaking anything early.
- **After** unlock, anyone with repo read access can decrypt — so keep the vault repo **private**.
- Trust assumptions: the drand threshold isn't compromised before the unlock time, and drand mainnet stays live (a robust multi-org network; the chain hash is pinned per secret).
- A real time-lock means the unlock time is **immutable** — there's no "extend." To re-time a secret, reveal it after unlock and add it again.

More in the [docs](https://louisalexander.github.io/time-safe/): [getting started](docs/getting-started.md) · [architecture](docs/architecture.md) · [usage](docs/usage.md) · [security](docs/security.md).

## Development

```bash
uv run pytest                                                  # unit + Textual Pilot tests
TIMESAFE_LIVE=1 uv run pytest tests/test_tle.py -k roundtrip   # live drand roundtrip
uv run python scripts/make_screenshots.py                      # regenerate docs/screenshots
```
