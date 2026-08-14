# Getting Started

## Prerequisites

- **Python 3.12+** and [uv](https://docs.astral.sh/uv/).
- The drand **`tle`** binary on your `PATH` (or `$TIMESAFE_TLE`, or `./.tools/tle`). From the [tlock releases](https://github.com/drand/tlock/releases):
  ```bash
  mkdir -p .tools
  curl -sL https://github.com/drand/tlock/releases/download/v1.2.0/tlock_1.2.0_darwin_arm64.tar.gz | tar -xz -C .tools tle
  ```
  (Pick the asset for your OS/arch.)
- A **private** GitHub repo to use as a vault, plus a token with `contents` write access — add `secrets` + `workflows` if you want email delivery (a fine-grained PAT scoped to just that repo is ideal).

## Install & run

```bash
git clone https://github.com/louisalexander/time-safe.git
cd time-safe
uv sync
uv run timesafe
```

## Create a vault

On the **Vaults** screen press **`n`** (new) and enter:

| Field | What to enter |
|---|---|
| Vault name | any label, e.g. `personal` |
| GitHub repo | `owner/repo` for an **empty private** repo |
| GitHub token | your PAT |

time-safe pushes the vault structure + delivery script, writes a `.timesafe/initialized` marker, stores your token in the OS keychain, and records the vault in `~/.timesafe/vaults.json` (the only thing kept locally).

To use a vault that's already initialized (e.g. from another machine), press **`c`** (connect) instead and give the repo + a token.

## Add a secret

Press **`a`** and fill in:

- **Name** — a label.
- **Unlock in** — a duration: `30m`, `2h`, `7d`, `1d12h`, or a bare number (days). Short durations are great for trying it out.
- **Delivery email** *(optional)* — where the plaintext is emailed if you use "Email it".
- **Secret text** — encrypted to the computed drand round; only the ciphertext is pushed.

## Reveal

When a secret's countdown reaches **● ready**, open it and press **`d`** to reveal it locally (decrypted in memory from the public drand signature — nothing leaves your machine). You can also **`r`** renew it (re-lock for a new duration) or **`s`** email it.

## Link Gmail (optional — for email delivery)

See the [README](https://github.com/louisalexander/time-safe#gmail-delivery-setup-one-time-optional). In short: create a Google Cloud **Desktop app** OAuth client with the `gmail.send` scope, then press **`g`** in time-safe and authorize in the browser. The refresh token is stored only as a GitHub Actions secret in the vault repo.
