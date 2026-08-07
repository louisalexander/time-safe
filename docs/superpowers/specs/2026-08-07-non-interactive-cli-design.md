# time-safe — Non-Interactive CLI Design

**Date:** 2026-08-07
**Status:** Approved design (ready for implementation planning)
**Relates to:** [2026-06-05 Python Rewrite Design](2026-06-05-timesafe-python-rewrite-design.md)

---

## 1. Overview

time-safe today is a Textual TUI. This document specifies an **additive, non-interactive CLI** so other
programs can drive a vault without a terminal, plus the packaging and pipelines needed to install that
CLI on the machines that will actually run it.

The first consumer is `break-start.sh` on **sisko** (Ubuntu 18.04.6): it will add a timelocked secret,
poll for readiness, and reveal the plaintext once unlocked.

### Goals

- `add`, `status`, `reveal`, `list`, `init` — all usable from cron or a systemd unit with no TTY.
- Machine-readable JSON on stdout; distinct, documented exit codes.
- Plaintext secrets never reach argv, log files, or exception output.
- The same logic importable as `timesafe.api` so callers can skip `subprocess` entirely.
- Installable on hosts with a modern Python **and** on hosts with no usable Python at all.

### Non-goals

- **The TUI does not change.** Not one behavioural difference. Every change below is additive or a
  pure refactor with the same observable behaviour.
- No `delete`, `renew`, or `send-email` subcommands. They exist on `Vault` and would be easy, but no
  consumer needs them. `timesafe/api.py` is where they'd go.
- No Gmail linking from the CLI. It is a browser OAuth loopback flow
  (`timesafe/oauth/loopback_flow.py`) and is fundamentally interactive.
- No Docker image. Considered and dropped in favour of the standalone binary (§8).
- No changes to the vault's on-disk/on-repo format. `.tle`, `.meta`, and the per-secret workflow are
  byte-identical to what the TUI writes today.

---

## 2. Decisions (locked)

| # | Decision |
|---|----------|
| 1 | **Identity** → `Secret.id` stays a UUID. `add` takes `--name <label>` and **returns the authoritative id**. Callers persist that id and use it for every later lookup; they must never construct or guess an id from a name. |
| 2 | **Names are not unique** and nothing enforces it. `--name` lookup is a convenience only, and **fails loudly on ambiguity** — never a silent pick. Stated plainly in the README. |
| 3 | **Vault resolution** → `--vault` > `$TIMESAFE_VAULT` > the sole registry entry if exactly one > usage error listing the candidates. Two or more registered vaults with no selector is a hard error, never a guess. |
| 4 | **Token resolution** → `$TIMESAFE_GITHUB_TOKEN` > OS keychain > vault error. Env-first is what makes cron work; the keychain is unavailable in a headless session and must never block. |
| 5 | **Secrets never in argv** → there is no `--secret` flag. stdin is the only path in. Same rule for PATs: no `--token` flag, only `$TIMESAFE_GITHUB_TOKEN` or `--token-stdin`. |
| 6 | **Exit codes** → `0` ok, `2` usage, `3` not-yet-unlockable, `4` vault/network, `5` not-found. |
| 7 | **`reveal` output** → plaintext to stdout and nothing else: no decoration, no added trailing newline, written via `sys.stdout.buffer`. |
| 8 | **`init` is idempotent** — a deliberate divergence from `InitVaultScreen`, which hard-errors on an already-initialized vault. Provisioning scripts must be safe to re-run. It also subsumes the TUI's *Connect*. |
| 9 | **No Textual below the CLI** → `timesafe/api.py` and everything it imports are Textual-free; `timesafe.app` is imported lazily, only on the TUI path. |
| 10 | **`tle` ships with the package** → vendored into platform wheels and into the standalone binary. It stops being a manual install step. |
| 11 | **Distribution** → PyPI wheels for hosts with Python ≥3.12, standalone single-file binaries for hosts without. No Docker. |
| 12 | **The standalone binary is CLI-only** (`--exclude-module textual`). `timesafe tui` inside it exits with a pointer to the pip install. |

---

## 3. Architecture

The CLI must not import Textual — for cron start-up cost, and so a UI bug can never break automation.
That fixes the dependency direction:

```
cli.py  ──>  api.py  ──>  vault/ · github/ · timelock/ · config/
screens/ ─────────────────────^
(textual)                      (no textual anywhere below this line)
```

### New modules

| Module | Responsibility |
|---|---|
| `timesafe/validation.py` | `parse_duration`, `is_valid_email` — moved out of `screens/add_secret.py`. Pure, no Textual. |
| `timesafe/errors.py` | Typed exceptions, each carrying its exit code and machine-readable `code` string. |
| `timesafe/resolve.py` | Headless vault + token resolution (decisions 3 and 4). Returns a ready `Vault`. |
| `timesafe/api.py` | The importable surface: `add`, `status`, `reveal`, `list_secrets`, `init`. Returns dataclasses/dicts, raises typed errors. **No printing, no `sys.exit`, no argparse.** Each accepts an optional `vault=` so callers can inject a `Vault` and skip resolution. |
| `timesafe/cli.py` | argparse, stdin reading, JSON encoding, exit codes. Thin — every decision lives in `api`. |

### Refactors to existing code

- `parse_duration` / `is_valid_email` move to `timesafe/validation.py`. Call sites updated:
  `screens/add_secret.py` (2), `screens/renew.py:12`. Their tests move from `tests/test_screens.py`
  to `tests/test_validation.py`.
- `TLE_VERSION = "1.2.0"` becomes a constant in `timesafe/timelock/tle.py`. `vault/workflow.py:5`
  builds `TLE_RELEASE` from it instead of hardcoding the URL a second time.
- `tle_path()` gains the frozen-binary and packaged locations to its lookup chain (§7).
- `GitHubClient` gains `create_repo()` and `get_authenticated_login()` (§6).
- `tests/test_vault.py`'s `FakeGitHub` moves to `tests/fakes.py` so the api/cli suites share it.

### Entry point

`[project.scripts] timesafe = "timesafe.__main__:main"` is unchanged. `main()` becomes a dispatcher:

- `timesafe` with no args → TUI, exactly as today
- `timesafe <subcommand>` / `--help` / `--version` → `cli.main()`
- `timesafe tui` → TUI explicitly

`cli.main(argv, stdin, stdout, stderr) -> int` **returns** its exit code rather than calling
`sys.exit`, so every code is testable in-process. `__main__.main()` performs the `sys.exit()`.

---

## 4. Command contracts

**Global flags:** `--vault <name|owner/repo>`, `--json`.

Every error object carries a stable discriminator so callers never parse prose:

```json
{"error": "no secret with that id", "code": "not_found"}
```

`code` ∈ `usage · empty_stdin · not_found · ambiguous_name · not_ready · vault · network`.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `2` | Usage error — bad flags, empty stdin, ambiguous `--name`, no vault selected |
| `3` | Not yet unlockable |
| `4` | Vault or network error |
| `5` | No such secret |

### `add`

```
timesafe add --name <label> --duration <10d|2h|30m> [--email <addr>] --secret-stdin [--json]
```

```json
{"id":"3f2a91c4-6b0e-4d21-9f77-1a2b3c4d5e6f","name":"break-glass",
 "unlock_at":"2026-08-17T12:00:00+00:00","round":19273645,
 "vault_path":"vault/secrets/3f2a91c4-6b0e-4d21-9f77-1a2b3c4d5e6f.tle","pushed":true}
```

- Accepts **no positional arguments**, so a mistyped secret can't land in argv.
- **Trailing-newline rule:** strips exactly one trailing `\n` or `\r\n`, nothing else — so `echo secret |`
  does the obvious thing while a secret genuinely ending in spaces survives intact. README documents
  `printf '%s'` for byte-exact input.
- Empty stdin (after that strip) → `2` / `empty_stdin`. Non-UTF-8 stdin → `2`.
- **stdin is a TTY → exit `2` immediately**, rather than blocking forever on a read that will never
  come. Direct consequence of the no-interactive-prompts constraint.
- `--email` records the address and writes the unlock workflow, exactly as the TUI does. It does not
  verify Gmail is linked; an unlinked vault's workflow fails at run time. Documented.
- `"pushed"` reflects that writes go through the GitHub Contents API — each `put_file` is a commit on
  the default branch. There is no local git checkout.

**Partial-write handling.** `Vault.put_secret` makes three sequential API commits (`.tle`, `.meta`,
workflow) with no transaction. If the `.meta` write fails, today you get an orphaned ciphertext that
`list_secrets` cannot see (it reads only `.meta`) and the caller never learns the id — unrecoverable
garbage. `api.add` wraps the call, attempts best-effort cleanup of whatever was written, and reports
the id in the error so nothing is silently orphaned. **`Vault.put_secret` itself is not modified**, so
TUI behaviour stays byte-identical.

### `status`

```
timesafe status [--id <id>] [--name <label>] [--json]
```

```json
{"id":"3f2a91c4-…","name":"break-glass","unlock_at":"2026-08-17T12:00:00+00:00",
 "ready":true,"seconds_remaining":0}
```

- No `--id`/`--name` → a JSON array covering every secret in the vault.
- An `--id` that matches no secret → `5` / `not_found`.
- `seconds_remaining` clamps at `0`; never negative.
- `ready` is the **scheduled** answer (wall-clock vs. `unlock_at` from `.meta`). `reveal` is the
  **cryptographic** one. They can disagree for a second or two at the boundary, because drand publishes
  every ~3s — which is why `reveal` keeps its own independent exit-3 path rather than trusting `status`.

### `reveal`

```
timesafe reveal --id <id> [--name <label>]
```

Plaintext to stdout, nothing else, no added trailing newline. Not ready → empty stdout, JSON error on
stderr, exit `3`. Two independent gates both map to `3`:

1. the `.meta` pre-check, which fails fast without fetching the ciphertext, and
2. `tle.NotYetUnlocked` from the decrypt itself, which catches clock skew.

`--json` is **accepted and ignored** here. The spec calls for `--json` on every command but also for
`reveal` to print only plaintext; accepting-and-ignoring keeps scripted invocation uniform while
changing nothing. Errors are JSON on stderr regardless.

### `list`

```
timesafe list [--json]
```

The full inventory — `id · name · unlock_at · created_at · round · chain · delivery_email · ready`.
`status` is the readiness view; `list` is the metadata view.

Without `--json`, `status` and `list` print a compact human-readable table. `add` and `reveal` behave
identically with or without it.

### Name lookup

`--name` is available on `status` and `reveal`. Zero matches → `5` / `not_found`. **Two or more
matches → exit `2` with `{"code":"ambiguous_name","ids":[…]}`** — never a silent pick.

---

## 5. `timesafe init`

```
timesafe init --vault <owner/repo> --name <label> [--create] [--token-stdin] [--json]
```

Note `--vault` carries a different meaning here than elsewhere: on every other command it *selects* an
already-registered vault and accepts either a registry name or `owner/repo`; on `init` the vault does
not exist yet, so it must be a literal `owner/repo`. A bare name is a usage error.

Token comes from `$TIMESAFE_GITHUB_TOKEN` or stdin via `--token-stdin`. There is no `--token` flag — a
PAT in argv lands in `ps` output and shell history. The keychain isn't consulted; a brand-new vault has
no entry yet.

`--create` creates the repo when missing: `POST /user/repos`, or `POST /orgs/{owner}/repos` when the
owner isn't the authenticated login (resolved via `GET /user`). Always `private: true` — not
configurable, because the entire security model rests on the vault repo being private. Also
`auto_init: true`, so a default branch exists for `dispatch_workflow` to target.

Idempotent, reporting exactly what it did:

```json
{"repo":"me/vault","created":true,"initialized":true,"registered":true,"token_saved":true}
```

A second run returns all `false` and exit `0`. Pointing it at an already-initialized vault registers it
locally — which is how a second machine gets provisioned headlessly, and why no separate `connect`
subcommand is needed.

`token_saved` is `false` without failing when the keychain is unavailable, as on a headless box. The
repo-side work is done either way, and env-var operation doesn't need the keychain.

**Limitation:** Gmail linking stays TUI-only. A CLI-created vault accepts `add --email` and the workflow
is written, but delivery fails at run time until someone presses `g` in the TUI once.

---

## 6. GitHub client additions

| Method | Endpoint |
|---|---|
| `get_authenticated_login()` | `GET /user` → `login` |
| `create_repo(private=True, auto_init=True)` | `POST /user/repos` or `POST /orgs/{owner}/repos` |
| `repo_exists()` | `GET /repos/{owner}/{repo}` → bool |

Repo creation needs a classic PAT with `repo` scope, or a fine-grained PAT with the right
administration permission. Fine-grained PATs frequently **cannot** create repos; the README says so and
recommends creating the repo manually plus plain `init` when `--create` returns 403.

---

## 7. Secret safety

Findings from auditing the leakage paths, and what changes:

- **Already safe:** `tle.encrypt` passes plaintext via subprocess stdin (`timelock/tle.py:38`), never
  argv. Nothing to fix.
- **`argparse` echoes offending values in its error messages.** If a secret were mistyped into a
  positional slot, the default `error()` would print it. `add` accepts no positionals, and
  `ArgumentParser.error()` is overridden to emit our JSON usage error naming the *flag* but never the
  *value*.
- **`rich` is installed (via Textual) and rich tracebacks render frame locals** — which for a
  `put_secret` frame means the plaintext. The CLI never installs rich traceback handling. Its top-level
  handler converts any unexpected exception into `{"error":"internal error","code":"vault"}`, exit `4`,
  no traceback. `TIMESAFE_DEBUG=1` opts back into a plain, locals-free traceback.
- **No logging** anywhere in the CLI path — no handlers, no files.
- `reveal` writes with `sys.stdout.buffer.write(...)`, never `print()` — no added newline, no repr, no
  encoding surprise.
- **Env-var token caveat** documented: it is readable via `/proc/self/environ` by the same user, so
  systemd users should prefer `LoadCredential=` or an `EnvironmentFile` at mode 0600.

---

## 8. Packaging

`tle` is a Go binary, not a Python package — so `pip install timesafe` alone leaves `add` and `reveal`
dead with `TleError: tle binary not found`. Both distribution channels therefore ship it.

### `tle_path()` lookup chain

```
$TIMESAFE_TLE  →  sys._MEIPASS/tle (frozen)  →  timesafe/_bin/tle (wheel)  →  PATH  →  ./.tools/tle
```

Packaged sits above `PATH` so the binary always matches the pinned `TLE_VERSION` rather than whatever
stray `tle` a host happens to have. `$TIMESAFE_TLE` still overrides everything; `.tools/tle` keeps the
dev checkout working unchanged. The `sys._MEIPASS` branch is required — PyInstaller unpacks to a temp
dir at runtime, and without it the bundled binary is invisible to the frozen executable.

**Two gotchas handled explicitly:**

- **The executable bit** survives a wheel inconsistently across pip versions. `tle_path()` checks
  `os.access(p, os.X_OK)` and chmods to `0o755` if needed; if that fails — a system-wide install running
  as non-root — it copies to `~/.cache/timesafe/tle` and uses that.
- **The sdist carries no binary.** `pip install` on an unlisted platform falls back to sdist and gets no
  `tle`. The `TleError` message at `timelock/tle.py:28` is rewritten to say exactly that and point at
  the install docs.

### PyPI wheels

`scripts/build_wheels.py` per target: download and checksum-verify `tle` into `timesafe/_bin/`,
`uv build --wheel`, retag via `python -m wheel tags --platform-tag=…`.

| Wheel | tle asset |
|---|---|
| `manylinux2014_x86_64` | `tlock_<v>_linux_amd64` |
| `manylinux2014_aarch64` | `tlock_<v>_linux_arm64` |
| `macosx_11_0_arm64` | `tlock_<v>_darwin_arm64` |
| `macosx_10_9_x86_64` | `tlock_<v>_darwin_amd64` |
| sdist | none (documented) |

Go binaries are static, so the manylinux wheels also work on musl/Alpine.

### Standalone binaries

For hosts with no usable modern Python. **sisko is the motivating case:** Ubuntu 18.04.6, system
`python3` is 3.6.9, the only interpreter with working `venv`+`ensurepip` is 3.9.10, and there is no
`uv`, no `pipx`, and no `virtualenv` — so the wheels above cannot run there at all.

- PyInstaller `--onefile`, built inside `quay.io/pypa/manylinux2014_*` (glibc 2.17, comfortably older
  than 18.04's 2.27), bundling CPython 3.12 + timesafe + `tle`.
- `--exclude-module textual` — the binary is for automation. This roughly halves the artifact and
  removes PyInstaller's most fragile hidden-import surface. `timesafe tui` exits with a message
  pointing at the pip install.
- Targets: `linux-amd64`, `linux-arm64`, `macos-arm64`.
- Attached to each GitHub Release alongside a `SHA256SUMS` file so a `curl` install can be verified.

Install on sisko:

```bash
curl -sL https://github.com/louisalexander/time-safe/releases/download/v0.2.0/timesafe-linux-amd64 \
  -o ~/.local/bin/timesafe
chmod +x ~/.local/bin/timesafe
```

### Version-pin drift guard

`TLE_VERSION` lives in `timesafe/timelock/tle.py`. `vault/workflow.py` builds its release URL from it,
`build_wheels.py` and the PyInstaller spec read it, and a unit test asserts they all agree. Cheap, and
it fails loudly at the right moment.

### Licence

**Open item, to resolve during implementation, not assumed here:** confirm tlock's licence terms for
redistributing its binary, and vendor its `LICENSE` into the wheel and the binary with attribution. If
redistribution turns out to be prohibited, the fallback is a `timesafe install-tle` subcommand that
downloads the pinned, checksum-verified binary into `~/.cache/timesafe/` — no new design needed.

---

## 9. Pipelines

`ci.yml` keeps its current `uv sync` + `pytest -q` job. `release.yml` is added and gated on it
(`needs: test`), so a red build can never ship.

| Trigger | Action |
|---|---|
| PR / push to `master` | Build all wheels, sdist, and binaries. Smoke-test them. **Publish nothing.** |
| `v*` git tag | Publish wheels to PyPI via trusted publishing (OIDC, `id-token: write`, no stored API token). Attach binaries + `SHA256SUMS` to the GitHub Release. |

PyPI has no sensible `:edge` channel without version-bumping every commit, so the edge/tag split
collapses to *build always, publish on tags*. The never-ship-a-red-build property is unchanged.

**Smoke tests** run against the built artifacts, not the source tree:

- Install each wheel into a clean venv; assert `tle_path()` resolves to the packaged binary and that it
  actually executes.
- Run each binary: `--help`, `status --json` with no vault configured asserting exit `2`, and confirm
  the embedded `tle` runs.

---

## 10. Testing

- **`validation.py`** — the existing duration/email tests, relocated.
- **`resolve.py`** — full `--vault` > env > sole-vault precedence, and every error path.
- **`api.py`** — against the shared `FakeGitHub` in `tests/fakes.py`, including the partial-write
  cleanup path.
- **`cli.py` in-process** — `cli.main(argv, stdin, stdout, stderr)` returns an int, so every exit code
  (`0/2/3/4/5`) is asserted without spawning anything.
- **Subprocess end-to-end** — a handful of real `subprocess.run` tests: piped stdin, captured stdout, no
  TTY, asserting exit codes and that `reveal` output is byte-exact with **no trailing newline**.
  In-process tests cannot prove the cron requirement; these can.
- **Leakage** — assert no plaintext appears in stdout or stderr on any failure path.
- **Drift guard** — assert `TLE_VERSION` agrees across `workflow.py`, the wheel builder, and the
  PyInstaller spec.

Tests need **no real `tle` and no network**: the end-to-end tests point `$TIMESAFE_TLE` at a stub binary
written into `tmp_path`, and GitHub is `FakeGitHub`. CI stays fast and offline. The existing suite must
stay green.

---

## 11. Documentation

The README gains a CLI section with copy-pasteable examples for every command, including:

- A shell example piping a generated secret via stdin without it ever appearing on screen or in argv.
- The exit-code table.
- A worked cron / systemd unit using `$TIMESAFE_VAULT` + `$TIMESAFE_GITHUB_TOKEN`.
- A plain statement that **names are not unique**, that scripts must persist the returned `id`, and that
  they must never construct an id from a name.
- Install instructions for both channels, including the sisko-style `curl` + `chmod` binary install.
- The `--create` fine-grained-PAT caveat and the Gmail-is-TUI-only limitation.
