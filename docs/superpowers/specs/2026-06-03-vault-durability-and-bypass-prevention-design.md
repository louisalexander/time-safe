# Time-Safe: Vault Durability & Bypass Prevention

## Goal

Improve the time-safe app so that:
1. Vault secrets survive machine loss (durability)
2. A locked site's "forgot password" flow cannot be used to bypass the lock (bypass prevention)
3. Impulsive self-bypass requires deliberate multi-step effort, not a single click

## Threat Model

The adversary is the user themselves in a moment of impulse. The lock needs to survive:
- Checking the site's "forgot password" button
- Logging into the vault Gmail to retrieve a reset link
- Looking for the decryption key on disk

It does NOT need to survive:
- A determined, sober user who spends hours working around it (acceptable bypass)
- Physical hardware attacks

## Data Model

No change to what the user enters. Each secret has:
- **Name** — human label (e.g. `Empornium`, `Vault Gmail`)
- **Secret** — the password value to encrypt
- **Lock duration** — number of days until the key is emailed back

## Architecture

Three interlocking layers:

### Layer 1 — Per-Secret Encryption with Remote Key Custody

- On lock: app generates a cryptographically random 256-bit AES key and random IV via `SecureRandom`
- Secret is encrypted locally (AES/CBC/PKCS5Padding)
- Key is uploaded to a GitHub Actions secret (`KEY_<uuid>`) on the vault GitHub repo and then cleared from memory — never written to disk
- GitHub Actions secrets are write-only from a human perspective; only a running workflow can read them
- Encrypted blob + plaintext metadata (name, lock date) are committed to the vault GitHub repo

### Layer 2 — Scheduled Key Delivery via GitHub Actions

- A workflow file (`unlock-<uuid>.yml`) is created for each secret and committed to `.github/workflows/` in the vault repo
- The workflow fires at the unlock date (cron schedule) and emails the AES key to the user's real inbox
- Email is sent via the vault Gmail's SMTP using a Gmail App Password stored as a repo-level Actions secret (`SMTP_USER`, `SMTP_PASS`) — set once during setup
- The workflow also exposes `workflow_dispatch` (manual trigger) — this is the intentional bypass path, requiring the user to log into the vault GitHub account, navigate to the workflow, and click Run. Non-impulsive by design.

### Layer 3 — Recovery Email Isolation (Vault Gmail)

- A dedicated Gmail account (e.g. `yourname.vault@gmail.com`) is used exclusively for locked site recovery
- For each locked site: change recovery email (and login email where possible) to vault Gmail
- The vault Gmail's own password is stored as a locked secret in the vault (same or longer lock duration)
- Vault Gmail recovery options:
  - Recovery email: **removed**
  - Recovery phone: **removed**
  - Backup codes: **printed, stored physically** (two copies — one at home, one at a second location)
- This closes the loop: "forgot password" → vault Gmail → vault Gmail is locked → dead end

## GitHub Infrastructure

A separate GitHub account is used for the vault (not the user's main dev account). This means accessing vault workflows requires logging out of the main account.

- **Vault GitHub account email:** vault Gmail address
- **Vault GitHub account password:** stored as a locked secret in the vault
- **Vault repo structure:**

```
vault/
  secrets/
    <uuid>.enc        ← AES-encrypted blob
    <uuid>.meta       ← JSON: { name, lockDate, uuid }
  .github/
    workflows/
      unlock-<uuid>.yml   ← one per secret
```

## App Changes

### New: Setup Command (run once)

Prompts for:
- Vault GitHub personal access token (with `repo` and `secrets` scopes)
- Vault Gmail address
- Gmail App Password (for SMTP)
- User's real email address (where keys get delivered)

Stores to `~/.timesafe/config` as JSON (local trusted state — the only local secret):
```json
{
  "githubToken": "ghp_...",
  "githubRepo": "yourname-vault/vault",
  "smtpUser": "yourname.vault@gmail.com",
  "smtpPass": "app-password-here",
  "deliveryEmail": "your-real@email.com"
}
```
Creates initial repo structure on GitHub.

### Updated: Add Secret

1. Prompts: name, secret value, days
2. Generates random AES-256 key + IV
3. Encrypts secret locally
4. Writes `<uuid>.enc` and `<uuid>.meta` to local `vault/` directory
5. Pushes both files to vault GitHub repo
6. Creates GitHub Actions secret `KEY_<uuid>` via GitHub API
7. Generates and commits `unlock-<uuid>.yml` workflow scheduled for unlock date
8. Prints checklist reminder:
   ```
   Done. Now complete these steps on the site manually:
     [ ] Change recovery email to: yourname.vault@gmail.com
     [ ] Change login email to: yourname.vault@gmail.com (if supported)
     [ ] Log out of all sessions
   ```

### Updated: List Secrets

- Reads `.meta` files from local `vault/` (falls back to fetching from GitHub if local is missing)
- Shows name + days remaining (or "UNLOCKED — check email for key")

### Updated: Decrypt

- If time has not passed: shows time remaining, no decrypt option
- If time has passed: prompts "Enter key from email:" → user pastes key → app decrypts local `.enc` file → shows password

### Removed

- `VaultManager.decrypt(Secret)` no longer auto-decrypts using a locally held key — decryption now requires the user to supply the key received by email

## Key Dependencies to Add (pom.xml)

- **GitHub API client** — use `org.kohsuke:github-api` for repo operations and secret management
- Remove dependency on hardcoded key/IV in `EncryptDecrypt`

## Emergency Recovery

If the user genuinely loses access (machine dead, local files gone, GitHub account inaccessible):
1. Retrieve printed vault Gmail backup codes from physical location
2. Log into vault Gmail using backup code
3. Log into vault GitHub account (via vault Gmail for password reset if needed)
4. Manually trigger unlock workflows or read secrets via the workflow logs
5. Decrypt locally using the retrieved key

## What Is Not In Scope

- Mobile app
- Multi-device sync beyond GitHub as shared store
- Sharing secrets with others
- Automated site login-email changes (must be done manually on each site)
