# Usage

## Running

```bash
java -jar build/libs/time-safe-all.jar
```

The JAR must be run from the directory containing your `.enc` and `.meta` files (or wherever you keep your encrypted secrets). On first run, if no secrets exist, you will see an empty list.

---

## Main menu

```
TimeSafe
0. Setup / Configure
1. Add new secret
2. Manage secrets
q. Quit
```

### Option 0 — Setup / Configure

Runs the first-time configuration wizard. Prompts for GitHub PAT, vault repo, vault Gmail address, Gmail App Password, and delivery email. Saves to `~/.timesafe/config.json`.

Use this again if you need to rotate credentials (e.g. generate a new GitHub PAT, update the Gmail App Password).

### Option 1 — Add new secret

Prompts for:

- **Name** — a human-readable label (e.g. `Empornium`, `Reddit`). Also used as the workflow filename in the vault repo.
- **Secret** — the plaintext value to lock (typically a password). Input is hidden.
- **Days to lock** — integer number of days from now until the unlock date.

On completion, TimeSafe prints the unlock date for confirmation.

### Option 2 — Manage secrets

Lists all secrets found in the current directory (files matching `*.meta`). Each entry shows the name, ID, unlock date, and whether it is currently locked or unlocked.

Select a secret by number to open the submenu.

---

## Secret submenu

After selecting a secret from the list:

```
1. View metadata
2. Decrypt
3. Extend lock
4. Delete
```

### 1 — View metadata

Prints the secret's stored properties:

- Name
- UUID (used as the filename stem for `.enc` and `.meta`)
- Unlock date (ISO-8601)
- Current locked status (`LOCKED` / `UNLOCKED`)

### 2 — Decrypt

Only available when the secret is unlocked (current date is on or after the unlock date). If the secret is still locked, this option will display a message showing when it unlocks and return to the menu.

When available:

1. TimeSafe prompts for the base64 AES key from the unlock email.
2. Paste the key from your email.
3. TimeSafe fetches the IV from the `.meta` file, decrypts the `.enc` blob, and prints the plaintext secret.

The key is used in memory only and discarded when the process exits. It is never written to disk.

### 3 — Extend lock

Prompts for the number of additional days to lock the secret. The new unlock date is calculated from **now** (the current date and time), not from the original unlock date.

!!! note "Re-locking an unlocked secret"
    If a secret is already unlocked (past its original date), using Extend lock will re-lock it. The new unlock date will be `now + N days`. This is useful if you decide mid-unlock that you want to stay locked for longer.

The extension:

1. Generates a new AES key and IV.
2. If the original key is available (decrypted state), re-encrypts the plaintext with the new key. If no key is available (still locked), the existing `.enc` file is kept and only the metadata and workflow are updated.
3. Pushes the updated key and a new workflow YAML to the vault repo.
4. Deletes the old workflow YAML from the vault repo.

### 4 — Delete

Permanently removes the secret:

1. Deletes the local `.enc` and `.meta` files.
2. Deletes `vault/keys/<uuid>.key` from the vault repo.
3. Deletes `.github/workflows/unlock-<name>.yml` from the vault repo.

!!! danger
    Deletion is irreversible. If the secret is locked, the plaintext is permanently lost — the key in the vault repo is deleted before it is ever delivered.

---

## Decryption walkthrough

Step-by-step guide for when the unlock email arrives:

1. Check your delivery email inbox on or after the unlock date.
2. Find the email from the vault Gmail account. Subject will be something like `TimeSafe unlock: Empornium`.
3. Copy the base64 key from the email body. It will look like: `AbCdEfGh1234...==`
4. Run TimeSafe: `java -jar build/libs/time-safe-all.jar`
5. Choose `2` (Manage secrets).
6. Select the secret by number.
7. Choose `2` (Decrypt).
8. Paste the base64 key when prompted.
9. The plaintext secret is printed to the console.

Copy the secret immediately. TimeSafe does not store the decrypted value.

---

## Extending a lock

If you want to add more time to a secret before or after the unlock date:

1. Choose `2` (Manage secrets).
2. Select the secret.
3. Choose `3` (Extend lock).
4. Enter the number of additional days from **now**.

The vault repo is updated automatically. The old scheduled workflow is replaced with a new one for the new date.

---

## Development commands

All development tasks use the Gradle wrapper — no separate Gradle install required.

```bash
# Full quality gate: compile + test + spotless check + spotbugs
./gradlew check

# Auto-format all Java sources to Google Java Format
./gradlew spotlessApply

# Run unit tests only
./gradlew test

# Build the fat JAR
./gradlew shadowJar

# View SpotBugs HTML report after a check run
open build/reports/spotbugs/main.html
```
