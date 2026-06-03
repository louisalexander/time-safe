# Getting Started

## Prerequisites

Before running TimeSafe you need the following:

- **Java 21+** — [Temurin](https://adoptium.net/) recommended. The Gradle wrapper can auto-download a JDK via toolchains if you use `./gradlew`, but `java -jar` requires a local install.
- **Gradle wrapper** — included in the repo; no Gradle install needed.
- **A private GitHub repo for the vault** — e.g. `yourname-vault/vault`. This is where encrypted keys and unlock workflows are stored. It must be private.
- **A GitHub Personal Access Token (PAT)** with `repo` scope, scoped to the vault repo. A fine-grained PAT is recommended — limit it to only that repo.
- **A dedicated Gmail account** for key delivery — e.g. `yourname.vault.keys@gmail.com`. Do NOT use your personal Gmail.
- **A Gmail App Password** — standard Gmail passwords do not work with SMTP. You must generate an App Password (requires 2-Step Verification).

---

## Setting up the vault Gmail

The vault Gmail account is the linchpin of the security model. Set it up carefully.

### 1. Create a fresh Gmail account

Use a name that clearly identifies it as a vault account. Do not link it to your personal Google account. Use a separate browser profile or incognito window.

### 2. Enable 2-Step Verification

Go to **Google Account → Security → 2-Step Verification** and enable it. This is required before you can generate an App Password.

Use an authenticator app (e.g. Google Authenticator, Authy) — not SMS. SMS can be intercepted or ported.

### 3. Generate an App Password

Go to **Google Account → Security → App Passwords**. Create a new app password for "Mail" / "Other device". Copy the 16-character password — you will enter it during TimeSafe setup.

### 4. Remove all recovery options

!!! danger "Critical step"
    If the vault Gmail has a recovery email or phone number, those become bypass paths. You MUST remove them.

Go to **Google Account → Security**:

- Remove any recovery email address.
- Remove any recovery phone number.
- Do NOT add a backup Gmail account.

### 5. Save the backup codes physically

Go to **Google Account → Security → 2-Step Verification → Backup codes** and generate a set. Print them and store them in a physically secure location (safe, lockbox, sealed envelope). These are your only emergency access path to the vault Gmail if you lose your authenticator device.

Do not store backup codes digitally. Do not photograph them with a phone that syncs to cloud storage.

---

## Build the JAR

```bash
git clone https://github.com/louisalexander/time-safe.git
cd time-safe
./gradlew shadowJar
```

Output: `build/libs/time-safe-all.jar`

The shadow JAR bundles all dependencies (Apache Commons Crypto, Gson, etc.) into a single self-contained file.

---

## First-time configuration

Run the JAR and choose option `0` (Setup / Configure):

```bash
java -jar build/libs/time-safe-all.jar
```

You will be prompted for:

| Prompt | What to enter |
|--------|--------------|
| GitHub PAT | The fine-grained PAT with `repo` scope for the vault repo |
| Vault repo | `owner/repo` format, e.g. `yourname-vault/vault` |
| Vault Gmail address | The dedicated Gmail account, e.g. `yourname.vault.keys@gmail.com` |
| Gmail App Password | The 16-character App Password generated above |
| Delivery email | Where the unlock key emails should be sent — your personal email |

Configuration is saved to `~/.timesafe/config.json`. The file permissions should be restricted:

```bash
chmod 600 ~/.timesafe/config.json
```

!!! warning
    `config.json` contains your GitHub PAT and Gmail App Password in plaintext. Protect it.

---

## Add your first secret

Run the JAR again and choose option `1` (Add new secret):

```
> 1
Name: Empornium
Secret: hunter2
Days to lock: 90
```

TimeSafe will:

1. Generate a random AES key and IV.
2. Encrypt the secret locally — writing `<uuid>.enc` to the working directory.
3. Push the AES key to `vault/keys/<uuid>.key` in the vault repo.
4. Generate an unlock workflow YAML and push it to `.github/workflows/unlock-Empornium.yml` in the vault repo.
5. Confirm success and show the unlock date.

The secret is now locked. The key exists only in the private vault repo, accessible only via the vault Gmail.
