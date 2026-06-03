# TimeSafe for Secrets
[![CI](https://github.com/louisalexander/time-safe/actions/workflows/ci.yml/badge.svg)](https://github.com/louisalexander/time-safe/actions/workflows/ci.yml)
![Java](https://img.shields.io/badge/Java-21-orange?logo=openjdk)
![Gradle](https://img.shields.io/badge/Gradle-8.8-02303A?logo=gradle)
![License](https://img.shields.io/badge/License-MIT-blue)

Encrypt a secret and time-lock it — not even you can access it until the unlock date.

Designed for locking yourself out of sites you want to avoid. The key is held inside a GitHub account whose password is itself locked in the vault, creating a circular chain only time can break.

📖 **Full documentation:** [louisalexander.github.io/time-safe](https://louisalexander.github.io/time-safe)

---

## What it looks like

```
  ███████╗██╗███╗   ███╗███████╗███████╗ █████╗ ███████╗███████╗
     ██╔══╝██║████╗ ████║██╔════╝██╔════╝██╔══██╗██╔════╝██╔════╝
     ██║   ██║██╔████╔██║█████╗  ███████╗███████║█████╗  █████╗
     ██║   ██║██║╚██╔╝██║██╔══╝  ╚════██║██╔══██║██╔══╝  ██╔══╝
     ██║   ██║██║ ╚═╝ ██║███████╗███████║██║  ██║██║     ███████╗
     ╚═╝   ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝     ╚══════╝
                  your secrets, locked in time.

  ✗  Work Email                          47d 3h  (Jul 20 2026)
  ✗  Social Media                         2d 23h  (Jun  6 2026)
  ✗  Streaming Site                           23h  (Jun  4 2026)
  ✓  Old Account                      READY TO DECRYPT

[ Add Secret ]   [ Setup ]   [ Quit ]
```

Selecting a secret opens its detail view:

```
  ┌─────────────── Social Media ────────────────┐
  │  Status:   ✗  Locked                        │
  │  Unlocks:  Jun 6, 2026  (2 days remaining)  │
  │  ID:       a3f8c2d1...                      │
  │                                             │
  │  [ Extend Lock ]  [ Delete ]  [ Close ]     │
  └─────────────────────────────────────────────┘
```

---

## How it works

1. **Lock** — enter a name, secret value, and number of days. A random AES-256 key encrypts the secret. The ciphertext, metadata, and key are pushed to your private vault repo on GitHub.
2. **Schedule** — a GitHub Actions cron workflow is created in the vault repo for the unlock date. On that day it emails the base64-encoded key to your delivery address.
3. **Wait** — the key exists only inside the vault repo, which you cannot access: the vault GitHub account password is itself locked in the vault. The delivery Gmail password is also locked. There are no recovery options.
4. **Decrypt** — paste the key from the unlock email into the TUI and your secret is revealed.

---

## Security model

| What is locked away | Why you can't bypass it |
|---------------------|------------------------|
| Vault GitHub account password | Stored as a TimeSafe secret — you can't log in to view files |
| Vault Gmail password | Also stored as a TimeSafe secret — you can't receive a GitHub password-reset email |
| Vault Gmail recovery options | None configured — the only way back is physical backup codes stored offline |
| SMTP credentials | Stored as GitHub Actions Secrets — never in plaintext, not readable via API |

The circular dependency means even a determined, urgent version of yourself cannot short-circuit the lock without the physical backup codes.

> **Important:** use a dedicated GitHub account for the vault, separate from your personal account. The vault account's password should itself be locked in TimeSafe.

---

## Prerequisites

- **Java 21+** — or let Gradle download Temurin 21 automatically on first build
- A **private GitHub repo** owned by a dedicated vault account (separate from your personal GitHub)
- A **dedicated Gmail account** for key delivery — set up with no recovery options, with physical backup codes stored offline

---

## Quick Start

1. **Clone and build**
   ```bash
   git clone https://github.com/louisalexander/time-safe.git
   cd time-safe
   ./gradlew shadowJar
   ```

2. **Run**
   ```bash
   java -jar build/libs/time-safe-1.0-SNAPSHOT-all.jar
   ```

3. **First-time setup** — press `Setup` and enter:
   - GitHub personal access token for the vault account (`repo` + `workflow` scopes)
   - Vault repo name (e.g. `vaultaccount/my-vault`)
   - Vault Gmail address and App Password
   - Delivery email address (where unlock keys will be sent)

4. **Add a secret** — press `Add Secret`, enter a name, the secret value, and how many days to lock it for.

5. **Lock your vault credentials** — once setup works, add the vault Gmail password and vault GitHub password as secrets too. This completes the circular lock chain.

---

## TUI Reference

| Screen | How to reach | What you can do |
|--------|-------------|-----------------|
| Main list | Launch | See all secrets with time remaining |
| Secret detail | Select a secret from the list | View metadata, decrypt, extend lock, delete |
| Add secret | Main → `Add Secret` | Enter name, value, and lock duration |
| Decrypt | Detail → `Decrypt` (only when unlocked) | Paste the base64 key from the unlock email |
| Extend lock | Detail → `Extend Lock` | Add more days to a locked secret |
| Setup | Main → `Setup` | Configure GitHub PAT, vault repo, and Gmail credentials |

---

## Development

```bash
./gradlew check          # compile + test + Spotless + SpotBugs
./gradlew spotlessApply  # auto-format
./gradlew shadowJar      # build fat JAR
```

The `check` task runs JUnit 4 tests, Spotless (Google Java Format), and SpotBugs with FindSecBugs. CI runs on every push via GitHub Actions, and Dependabot keeps Gradle and Actions dependencies up to date weekly.

---

## License

MIT
