# time-safe — Python Rewrite Design (Timelock Edition)

**Date:** 2026-06-05
**Status:** Approved design (ready for implementation planning)
**Supersedes:** the Java implementation. Clean-room Python reimplementation of the multi-vault redesign, now using **timelock encryption (drand/tlock)** instead of storing keys in the repo.

---

## 1. Overview

time-safe is a terminal application that **timelock-encrypts** secrets so they cannot be decrypted by anyone — including the owner — until a chosen future moment, stores the ciphertext in a GitHub repository, and can optionally email the plaintext to a per-secret address once it unlocks. This document specifies a clean Python rewrite (Textual TUI, drand/tlock, `keyring`, Gmail OAuth).

### Goals
- **Cryptographically enforced** time-lock via drand/tlock: no decryption material exists for anyone until the unlock time.
- Multi-vault management; the only local on-disk state is a list of vaults.
- A vault is a GitHub repo; ciphertext lives there, decrypted only in memory.
- One-time vault init vs. connect-to-existing, enforced by a repo sentinel.
- Per-secret unlock time + (optional) delivery email, set at creation.
- Reveal secrets **locally** in the app once unlocked; optionally email the plaintext via a GitHub Actions + Gmail OAuth workflow.
- A nicer, testable TUI via Textual.

### Non-goals
- No backward compatibility with Java-created (AES/CBC) ciphertext. **Start clean.**
- **No "extend lock"** — timelock binds the unlock time cryptographically (see §2). Postponing a locked secret is impossible by design.
- No cross-platform credential storage beyond `keyring`'s built-ins.
- No web/mobile UI.

---

## 2. Decisions (locked)

| # | Decision |
|---|----------|
| 1 | **PAT storage** → OS keychain via `keyring`; the local vault list holds only name + `owner/repo`. |
| 2 | **Migration** → none; start clean. Old `~/.timesafe/config.json` + local `vault/` files, if present, are deleted on first run with a notice. |
| 3 | **Per-secret delivery email** → set at creation only (v1); used only by the optional email-delivery feature. |
| 4 | **Reveal/Email gating** → both hidden until a secret's unlock time passes. |
| 5 | **Email auth** → Gmail OAuth (owner's own **Published** Google Cloud client). **Optional** — only needed for the "email it" feature; local reveal needs no Gmail. |
| 6 | **TUI** → Textual. |
| 7 | **Crypto** → **timelock encryption via drand/tlock** (encrypt-to-round). The drand "quicknet" beacon (threshold BLS, League of Entropy) is the trust anchor; the decryption key is the beacon signature at the target round, which does not exist until that wall-clock time. **No per-secret key is stored anywhere.** |
| 8 | **tlock implementation** → shell out to the drand **`tle`** CLI (alt: `age` + `age-plugin-tlock`). No mature pure-Python tlock exists; a small pinned binary is invoked from both the app and the delivery workflow. |
| 9 | **`g` Re-link Gmail** → standalone vault action to (re)authorize/rotate the vault's Gmail credential at any time (only relevant if using email delivery). |
| 10 | **No "extend lock"** → a tlock ciphertext is cryptographically bound to its round; you cannot re-time a secret you cannot read. Re-locking = reveal after unlock, then add again. |
| 11 | **Reveal is local-first** → the app decrypts in memory using the public drand signature; plaintext never touches disk or (for local reveal) email. |

---

## 3. Tech stack

| Concern | Choice |
|---|---|
| Language | Python 3.12+ |
| TUI | **Textual** (`Pilot` + snapshot testing) |
| GitHub API | thin **httpx** client |
| Repo-secret sealing | **PyNaCl** (sealed box; for writing OAuth Actions secrets) |
| Keychain | **keyring** (macOS Keychain backend) |
| Timelock crypto | **drand `tle` CLI** (quicknet beacon) via subprocess; drand `/info` over httpx to map dates→rounds |
| OAuth (app side) | manual device flow over httpx |
| Delivery script (Actions) | stdlib Python + the `tle` binary: decrypt via tlock, send via Gmail API |
| Registry/config | stdlib `json` + `pathlib` |
| Dev/packaging | **uv** + `timesafe` console entry point; bundles/locates the `tle` binary |
| Tests | **pytest** + `respx` (HTTP) + `pytest-textual-snapshot` (screens); `tle` calls wrapped behind a seam and faked in unit tests |

(`cryptography`/AES is no longer needed for secret encryption — tlock replaces it.)

---

## 4. Data & storage model

| Datum | Lives in | Notes |
|---|---|---|
| Vault list (name + `owner/repo`) | `~/.timesafe/vaults.json` (local) | **Only** local persistence |
| GitHub PAT (per vault) | OS keychain via `keyring`, keyed by repo | Never in a plaintext file |
| Vault Gmail address | repo Actions secret `GMAIL_ADDRESS` | optional (email feature only) |
| OAuth refresh token | repo Actions secret `GMAIL_REFRESH_TOKEN` | optional; never local |
| OAuth client id / secret | repo Actions secrets `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` | optional |
| Secret metadata | repo file `vault/secrets/<id>.meta` (JSON) | `{id, name, unlock_at, drand_round, drand_chain, created_at, delivery_email?}` |
| Secret ciphertext | repo file `vault/secrets/<id>.tle` | **tlock ciphertext** (age-armored). Safe even if seen before unlock. Decrypted only in memory. |
| ~~Per-secret key~~ | — | **Eliminated.** No key is stored anywhere. |
| Init sentinel | repo file `.timesafe/initialized` | guards double-init / invalid connect |
| Delivery script | repo file `vault/scripts/send_secret.py` | stdlib + `tle`: decrypt-at-T then Gmail-send (optional feature) |
| Per-secret unlock workflow | repo file `.github/workflows/unlock-<id>.yml` | `workflow_dispatch`-only; installs `tle`; runs `send_secret.py` |
| Secret list / ciphertext / plaintext (runtime) | process memory only | never written to disk |

**Trust model (now cryptographic):** confidentiality before the unlock time does **not** depend on the repo being private — tlock guarantees no party (owner, PAT holder, GitHub, drand minority) can decrypt before round R. After unlock, anyone with repo read access can decrypt, so a **private repo is still recommended** to bound *post-unlock* access. The remaining trust assumptions: (a) the drand threshold (≈t-of-n League of Entropy nodes) is not compromised before T, and (b) drand mainnet remains live so the round signature is eventually published. The app pins the quicknet chain hash and records `drand_round`+`drand_chain` per secret so decryption is reproducible.

---

## 5. Screens & flows

Textual screens; breadcrumb header `time-safe › vault › screen`; footer key bindings; everything terminal-default except **green = ready** and **red = delete**.

- **Vault picker** (home): list of vaults. `↵` open · `n` new · `c` connect · `r` remove · `q` quit. Single vault opens directly.
- **Init new vault** (one-time): name + `owner/repo` + PAT → validate, reject if already initialized, push structure + `send_secret.py`, write sentinel, store PAT in keychain, add to registry → (optionally) flow into **Link Gmail**.
- **Connect existing vault**: `owner/repo` + PAT → requires sentinel; rejects uninitialized/duplicate; stores PAT + registers.
- **Link Gmail** (device flow; init or `g`): shows Google URL + user code, polls, writes the OAuth Actions secrets. Optional; skippable if you only use local reveal.
- **Secrets list**: per-secret state — live countdown, or `● ready` (green). `↵` open · `a` add · `g` re-link gmail · `esc` back · `q` quit.
- **Secret detail**:
  - *ready*: `d` **Reveal** (local decrypt + show) · `s` **Email it** (workflow decrypts + emails plaintext) · `x` Delete (red).
  - *locked*: `d` Reveal *(disabled — "locked until <T>")* · `x` Delete. Reveal/Email hidden-or-disabled until ready. **No Extend.**
  - shows unlock time, round, and (if set) delivery email, read-only.
- **Add secret** (4-step wizard): name → unlock date/duration → **delivery email** (validated; optional/skippable) → secret text → tlock-encrypt to the computed round + push `.tle`/`.meta`.
- **Reveal result**: shows the locally-decrypted plaintext (read-only); plaintext discarded on close. (Replaces the old paste-the-key screen — there is no key.)

`d` Reveal (local, secure) and `s` Email it (out-of-band plaintext delivery) are distinct, intentionally.

---

## 6. Module layout

```
timesafe/
  __main__.py            entry point
  app.py                 TimeSafeApp(Textual App): screen stack, bindings, active-vault state
  app.tcss               theme: default fg; .ready=green, .delete=red
  config/
    registry.py          VaultRegistry → ~/.timesafe/vaults.json (VaultRef = name + repo)        [pure-ish]
    credentials.py       CredentialStore over keyring (PAT per repo)
  timelock/
    drand.py             round_for(unlock_at): fetch+cache quicknet /info, map date→round         [IO; respx]
    tle.py               encrypt(plaintext, round)->bytes / decrypt(ciphertext)->bytes|NotYet via `tle` subprocess  [seam-faked]
  github/
    client.py            GitHubClient: httpx wrapper (contents, list dir, default branch, dispatch) [IO; respx]
    secrets_api.py       PyNaCl seal() (pure) + set/delete repo Actions secret
  vault/
    secret.py            Secret model + meta JSON (de)serialize (id,name,unlock_at,round,chain,...) [pure]
    workflow.py          build_unlock_workflow_yaml() + SEND_SECRET_SCRIPT (stdlib+tle string)      [pure]
    vault.py             Vault(repo, token): list_secrets/put_secret/reveal/delete/
                         dispatch_email/is_initialized/write_sentinel/init/relink_gmail             [orchestration]
  oauth/
    device_flow.py       GmailDeviceAuth: pure body-builders/parsers/classifier + run() driver
  screens/               vault_picker, init_vault, connect_vault, gmail_link,
                         secrets_list, secret_detail, add_secret, reveal
tests/                   pure-logic units; respx-mocked github_client + drand; faked tle; snapshots/ per screen
pyproject.toml           uv-managed; deps + console script; locates/bundles `tle`
README.md                incl. one-time Google Cloud OAuth-client setup + tle prerequisite
```

**Architecture shifts from the Java version:** Textual `push_screen`/`pop_screen` replace `NavigationController`; Textual workers (`@work`) replace `runAsync`; **drand/tlock replaces all per-secret key management** (no `crypto.py`, no key files, no key delivery). `keyring`/PyNaCl handle keychain/secret-sealing.

---

## 7. Delivery / reveal flow

**Add:** compute `round = round_for(unlock_at)` from cached drand `/info`; `tle.encrypt(plaintext, round)`; push `vault/secrets/<id>.tle` + `.meta` (records `unlock_at`, `drand_round`, `drand_chain`). No key, no key file.

**Reveal (local, primary):** once `now >= unlock_at`, the app fetches the `.tle` from the repo and runs `tle.decrypt(...)`, which pulls the public drand round signature and decrypts in memory. Before T it returns *NotYet* and the UI keeps the countdown. Plaintext is shown read-only and discarded on close — it never leaves the machine.

**Email it (optional, out-of-band):** on a ready secret, `s` dispatches `unlock-<id>.yml`. The job installs `tle`, runs the stdlib `send_secret.py`: `tle -d` the checked-out ciphertext (succeeds only after T — itself the server-side gate), then sends the **plaintext** FROM the vault Gmail TO the per-secret delivery address via the Gmail API. On Gmail-token revoke/expiry it exits non-zero and opens a *"Gmail re-authorization required"* issue. Dispatching before T → `tle -d` fails → job exits cleanly without sending.

---

## 8. Testing strategy

- **Pure logic** (`secret`, `workflow`, `device_flow` parsers, `registry`, `secrets_api.seal`, `drand.round_for` math) → pytest units.
- **`tle` subprocess** → wrapped behind the `timelock/tle.py` seam; faked in unit tests; one **live smoke test** (encrypt to a round a few seconds out, sleep, decrypt) marked slow/manual.
- **GitHub client / drand info** → `respx`-mocked HTTP.
- **Screens** → Textual `Pilot` + `pytest-textual-snapshot` (incl. ready vs. locked detail, reveal result, gated Reveal/Email).
- **Live-only** (real device-flow, real dispatch+email, revoke→issue) → manual runbook.

---

## 9. Implementation plan mapping (five Python plans)

1. **Registry + keychain + picker** — `config/`, `app.py` shell, vault picker. (No legacy migration.)
2. **Timelock secrets, in-memory** — `timelock/` (`drand.py`, `tle.py`), `vault/secret.py`, `github/client.py`, `vault/vault.py` (`put_secret`/`list_secrets`/`reveal`/`delete`); secrets-list + reveal screens. Decryption is local tlock.
3. **Init / connect + sentinel** — `init_vault`/`connect_vault` screens, `is_initialized`/`write_sentinel`.
4. **Per-secret email field + reveal/email gating + theme** — add-secret wizard, secret-detail gating (no Extend), `app.tcss` colors, snapshots.
5. **Gmail OAuth + email delivery** — `oauth/device_flow.py`, `vault/workflow.py` (`SEND_SECRET_SCRIPT` with `tle -d`), `gmail_link` screen, `relink_gmail`, OAuth Actions secrets. (Optional feature; local reveal already works after Plan 2.)

---

## 10. Open items / risks

- **drand liveness/longevity** — if quicknet ever disappeared, those secrets become permanently undecryptable. Mitigations: drand is a robust multi-org threshold network built for exactly this; we pin the chain hash and record the round; revisit double-wrapping (tlock ∘ keychain key) if the user later wants outage insurance (currently out of scope per the single-tlock decision).
- **`tle` binary dependency** — the app and the workflow both need it. App: bundle or document install; workflow: install step. Behind a seam for testing.
- **Email carries plaintext** — the optional "Email it" path sends the decrypted secret over Gmail. Local reveal (default) avoids this; document the trade-off. (Could later add a "notify only, open the app" mode.)
- **No reschedule** — extend-lock is gone by design (decision #10); make this explicit in the UI ("locked until <T>, not adjustable").
- **`gmail.send` sensitive scope** — Published-but-unverified owner client is acceptable; documented in README. OAuth is optional overall.
- **Clock/round mapping** — compute rounds from drand `/info` (genesis+period), not local guesses; store the round so reveal is deterministic regardless of clock skew.
