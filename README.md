# TimeSafe for Secrets
[![CI](https://github.com/louisalexander/time-safe/actions/workflows/ci.yml/badge.svg)](https://github.com/louisalexander/time-safe/actions/workflows/ci.yml)
![Java](https://img.shields.io/badge/Java-21-orange?logo=openjdk)
![Gradle](https://img.shields.io/badge/Gradle-8.8-02303A?logo=gradle)
![License](https://img.shields.io/badge/License-MIT-blue)

Encrypt a password and time-lock it so that not even you can access it until the unlock date.

---

## How it works

- **Encrypt & push** — a random 256-bit AES key is generated per secret. The encrypted blob and JSON metadata are pushed to a private GitHub repo (your vault). The key is stored there too, never locally.
- **Schedule delivery** — a GitHub Actions cron workflow is created in the vault repo for the unlock date. On that date it emails the base64-encoded key to your delivery address.
- **Wait** — the key exists only inside the vault repo, which you cannot access without the vault Gmail password — which is itself locked in the vault.
- **Decrypt** — paste the key from the email into the CLI and your secret is revealed.

---

## Prerequisites

- **Java 21+** (Temurin recommended)
- A **private GitHub repo** to use as the vault (separate from this one)
- A **dedicated Gmail account** for key delivery (set up with no recovery options and physical backup codes stored offline)

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
   java -jar build/libs/time-safe-all.jar
   ```

3. **First-time setup** — choose option `0` (Setup) and enter:
   - GitHub personal access token (needs `repo` and `workflow` scopes)
   - Vault repo name (e.g. `louisalexander/my-vault`)
   - Gmail address and app password for key delivery

4. **Add a secret** — choose option `1`, then enter a name, the secret value, and how many days to lock it for.

---

## CLI Reference

| Option | Action |
|--------|--------|
| `0` | Setup — first-time configuration |
| `1` | Add a new secret |
| `2` | List / manage secrets (view metadata, decrypt, extend lock, delete) |

---

## Development

```bash
./gradlew check          # compile + test + Spotless + SpotBugs
./gradlew spotlessApply  # auto-format
./gradlew shadowJar      # build fat JAR
```

The `check` task runs 17 JUnit 4 tests, Spotless (Google Java Format), and SpotBugs with FindSecBugs. CI runs on every push via GitHub Actions, and Dependabot keeps Gradle and Actions dependencies up to date weekly.

---

## License

MIT

---

Full documentation at [louisalexander.github.io/time-safe](https://louisalexander.github.io/time-safe)
