# CLI reference

time-safe ships a non-interactive CLI alongside the TUI, so other programs can drive a vault. It
needs no terminal, prompts for nothing, and works when stdin and stdout are pipes — from cron, from a
systemd unit, or from another script.

The TUI is unchanged: bare `timesafe` still opens it.

!!! danger "Two rules for anything calling this"

    1. **Persist the `id` that `add` returns.** It is the vault's authoritative key. Never build one
       from a name, and never assume the scheme — it may change.
    2. **Names are not unique.** Nothing in the vault enforces uniqueness, and the TUI will happily
       create two secrets with the same label. `--name` is a convenience lookup that *fails* on
       ambiguity rather than picking one.

## Install

=== "Modern host (Python 3.12+)"

    ```bash
    uv tool install timesafe      # or: pipx install timesafe
    ```

    The wheels bundle the `tle` binary, so there is nothing else to fetch.

=== "Old host (no usable Python)"

    A single self-contained executable — no Python, no pip, no venv, no container.

    ```bash
    curl -sL https://github.com/louisalexander/time-safe/releases/latest/download/timesafe-linux-amd64 \
      -o ~/.local/bin/timesafe
    chmod +x ~/.local/bin/timesafe
    ```

    Built against glibc 2.17, so it runs on anything from Ubuntu 18.04 onward. Verify it against the
    `SHA256SUMS` file on the release. This build is **CLI-only** — `timesafe tui` will tell you to
    install from PyPI instead.

Available binaries: `timesafe-linux-amd64`, `timesafe-linux-arm64`, `timesafe-macos-arm64`.

## Configuration

Everything comes from the environment, so nothing has to be typed.

| Variable | Purpose |
|---|---|
| `TIMESAFE_VAULT` | which vault — `owner/repo`, or a name from your local vault list |
| `TIMESAFE_GITHUB_TOKEN` | GitHub PAT — needs **`contents`** write, plus **`workflow`** for `--email` (see below) |
| `TIMESAFE_TLE` | path to a specific `tle` binary (overrides the bundled one) |
| `TIMESAFE_GITHUB_API` | alternate API root, for GitHub Enterprise |
| `TIMESAFE_DEBUG` | set to `1` to print an exception line on unexpected failures |

**How the vault is chosen:** `--vault` first, then `$TIMESAFE_VAULT`, then — only if exactly one vault
is registered locally — that one. Two or more registered with no selector is a hard error listing the
candidates, never a guess.

**How the token is found:** `$TIMESAFE_GITHUB_TOKEN` first, then the OS keychain. Environment-first is
what makes cron work: a headless session has no unlocked keychain, and time-safe will never block
waiting for one.

!!! info "`--email` needs the `workflow` scope; nothing else does"

    An `add --email` writes a delivery workflow for that secret
    (`.github/workflows/unlock-<id>.yml`). Writing anything under `.github/workflows/` requires the
    `workflow` scope, so a token with `contents` write alone fails on that add — and only on the
    last of three writes:

    ```json
    {"error": "Failed to write the secret. GitHub returned 403 writing
     .github/workflows/unlock-45d30ee9-….yml. …", "code": "vault",
     "cleaned": ["vault/secrets/45d30ee9-….meta", "vault/secrets/45d30ee9-….tle"]}
    ```

    The `cleaned` list is the tell: `.tle` and `.meta` were written and then rolled back, so the
    failure was on the workflow.

    **If you only ever `reveal` locally — the usual automation case — `contents` write is enough.**
    An add without `--email` writes no workflow at all. To use delivery, widen the token:

    - **Classic PAT** → tick `repo` *and* `workflow`.
    - **Fine-grained PAT** → Contents: Read and write, **Workflows: Read and write**.

    Add `secrets: write` too if you want Gmail delivery, which stores its credentials as Actions
    secrets.

!!! warning "Token hygiene"

    An environment variable is readable via `/proc/self/environ` by the same user. Under systemd,
    prefer `LoadCredential=`, or an `EnvironmentFile=` at mode `0600`.

## Exit codes

Distinct on purpose, so a caller can tell "not ready yet" from "something broke".

| Code | Meaning |
|---|---|
| `0` | Success |
| `2` | Usage error — bad flags, empty stdin, ambiguous `--name`, no vault selected |
| `3` | **Not yet unlockable** — the secret exists, its time hasn't come |
| `4` | Vault or network error |
| `5` | No such secret |

Errors are always JSON **on stderr**, never stdout, and always carry a stable `code`:

```json
{"error": "No secret with id 3f2a91c4-….", "code": "not_found"}
```

`code` is one of `usage`, `empty_stdin`, `not_found`, `ambiguous_name`, `not_ready`, `vault`,
`network`. Branch on `code`, not on the message text.

## Commands

### `add`

```bash
timesafe add --name <label> --duration <10d|2h|30m> [--email <addr>] --secret-stdin
```

Timelock-encrypts the secret and pushes it to the vault. **The plaintext is read only from stdin** —
there is deliberately no flag that could carry it, so it can never appear in `ps` output or shell
history.

```bash
# generate a secret and lock it without it ever hitting the screen or the argument list
openssl rand -base64 32 | timesafe add --name break-glass --duration 10d --secret-stdin
```

```json
{"id":"3f2a91c4-6b0e-4d21-9f77-1a2b3c4d5e6f","name":"break-glass",
 "unlock_at":"2026-08-17T12:00:00+00:00","round":19273645,
 "vault_path":"vault/secrets/3f2a91c4-6b0e-4d21-9f77-1a2b3c4d5e6f.tle","pushed":true}
```

Save `id`. It's the only thing that identifies the secret later.

**Durations:** `30m`, `2h`, `7d`, `1d12h`, `90s`. A bare number means days.

**Trailing newlines:** exactly one trailing `\n` (or `\r\n`) is stripped, so `echo secret |` does what
you expect. Nothing else is touched, so a secret that genuinely ends in whitespace survives. For
byte-exact input use `printf '%s'`:

```bash
printf '%s' "$SECRET" | timesafe add --name k --duration 1d --secret-stdin
```

Failure modes: empty stdin → `2`; stdin is a terminal → `2` immediately, rather than hanging on a read
that will never come; a failed write is cleaned up so no half-written secret is left behind.

`--email` records a delivery address and writes the unlock workflow. It does not check that Gmail is
linked — see [the limitation below](#what-the-cli-cannot-do).

### `status`

```bash
timesafe status [--id <id>] [--name <label>] [--json]
```

```json
{"id":"3f2a91c4-…","name":"break-glass","unlock_at":"2026-08-17T12:00:00+00:00",
 "ready":false,"seconds_remaining":863995}
```

With no selector, prints an array covering every secret. `seconds_remaining` clamps at `0` and is
never negative. Without `--json` you get a human-readable table.

!!! note "`ready` vs. actually revealable"

    `ready` is the *scheduled* answer — wall clock against the stored unlock time. `reveal` is the
    *cryptographic* one. Within a second or two of the boundary they can disagree, because drand
    publishes a round roughly every 3s. Poll `status`, but treat `reveal`'s exit `3` as the real
    answer.

### `reveal`

```bash
timesafe reveal --id <id>
```

Writes **only the plaintext** to stdout — no decoration, no trailing newline of its own. Safe to
redirect straight into a file or a variable:

```bash
timesafe reveal --id "$ID" > /run/secrets/unlocked
SECRET=$(timesafe reveal --id "$ID")
```

If it isn't unlockable yet: nothing on stdout, a JSON error on stderr, exit **3**.

`--json` is accepted and ignored here, so a script can pass it uniformly.

### `list`

```bash
timesafe list [--json]
```

Full metadata for every secret: `id`, `name`, `unlock_at`, `created_at`, `round`, `chain`,
`delivery_email`, `ready`. `status` is the readiness view; `list` is the inventory view.

### `init`

```bash
timesafe init --vault <owner/repo> --name <label> [--create] [--token-stdin]
```

Creates and/or initializes a vault repo and registers it locally.

```bash
export TIMESAFE_GITHUB_TOKEN=ghp_...
timesafe init --vault me/my-vault --name seedbox --create
```

```json
{"repo":"me/my-vault","created":true,"initialized":true,"registered":true,"token_saved":true}
```

**Idempotent** — safe to re-run from a provisioning script. It does only what's missing and reports
exactly what it did; a second run returns all `false` and exit `0`. Pointing it at an
already-initialized vault just registers it locally, which is how you provision a second machine.

`--create` always makes the repo **private**; there is no way to request otherwise, because the whole
security model depends on it.

Like the secret, the token never goes in argv — use `$TIMESAFE_GITHUB_TOKEN` or `--token-stdin`.

!!! warning "`--create` and fine-grained PATs"

    Fine-grained tokens frequently cannot create repositories. If `--create` returns a 403, create
    the repo yourself and run plain `init`.

## Scripting patterns

### Lock now, unlock later

```bash
#!/usr/bin/env bash
set -euo pipefail

STATE=/etc/seedbox-break.json

# Lock a fresh secret and remember the id the vault gave us.
ID=$(openssl rand -base64 32 \
     | timesafe add --name break-glass --duration 10d --secret-stdin \
     | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')
printf '{"id":"%s"}\n' "$ID" > "$STATE"
```

```bash
#!/usr/bin/env bash
# Later — poll, and act only when it's genuinely open.
ID=$(python3 -c 'import json; print(json.load(open("/etc/seedbox-break.json"))["id"])')

if SECRET=$(timesafe reveal --id "$ID" 2>/dev/null); then
    printf '%s' "$SECRET" | do_the_thing
else
    case $? in
        3) echo "not unlocked yet" ;;
        5) echo "secret is gone — was it deleted?" >&2; exit 1 ;;
        *) echo "vault error" >&2; exit 1 ;;
    esac
fi
```

### systemd

```ini
[Unit]
Description=Check the break-glass secret

[Service]
Type=oneshot
Environment=TIMESAFE_VAULT=me/my-vault
EnvironmentFile=/etc/timesafe.env     # mode 0600, holds TIMESAFE_GITHUB_TOKEN
ExecStart=/usr/local/bin/break-start.sh
```

### Skip the subprocess entirely

Everything above is available as a Python API with the same semantics and the same typed errors:

```python
from timesafe import api
from timesafe.errors import NotReadyError, NotFoundError

added = api.add(name="break-glass", duration="10d", secret=plaintext)
store(added["id"])

try:
    secret = api.reveal(secret_id=added["id"])
except NotReadyError as exc:
    print(f"{exc.extra['seconds_remaining']}s to go")
except NotFoundError:
    print("gone")
```

`api.add`, `api.status`, `api.reveal`, `api.list_secrets` and `api.init` return plain JSON-ready data
and raise `timesafe.errors` exceptions, each carrying `.exit_code` and `.code`. Pass `vault=` to
supply your own `Vault` and skip environment resolution.

## What the CLI cannot do

- **Link Gmail.** It's a browser OAuth flow, so it's inherently interactive. `add --email` records the
  address and writes the workflow, but delivery fails at run time until someone presses `g` in the TUI
  once for that vault.
- **Delete or renew.** Not exposed; use the TUI.
- **Extend a lock.** Nothing can — the unlock time is cryptographically bound. See
  [Security](security.md).

## Secret handling

- The plaintext only ever arrives on stdin, and `tle` receives it on stdin too — never as an argument.
- No logging, anywhere on the CLI path.
- Unexpected failures never print a traceback: `rich` renders frame locals, which would include the
  plaintext. You get `{"error":"Internal error.","code":"vault"}` and exit `4`. `TIMESAFE_DEBUG=1`
  adds a plain, locals-free exception line.
- A mistyped positional argument is never echoed back, so a secret passed in the wrong place cannot
  end up in your logs.
