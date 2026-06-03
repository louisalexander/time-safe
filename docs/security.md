# Security

## Threat model

TimeSafe is designed for one specific adversary: **yourself in a weaker moment**.

The goal is to protect access to sites you've chosen to avoid (e.g. gambling, porn, social media) during a period of self-imposed abstinence. The lock is meaningful because:

- You made the decision to lock when you were clear-headed.
- At the moment you most want access, there is no bypass path — not even one you forgot about.

TimeSafe is **not** designed to protect secrets from an external adversary. It does not protect against:

- A motivated attacker with access to your machine, vault repo, or Gmail account.
- Nation-state actors.
- Subpoenas or legal compulsion.

If your use case involves protecting secrets from someone else, use a purpose-built secrets manager (e.g. HashiCorp Vault, 1Password Secrets Automation).

---

## Why there is no bypass

The lock chain is designed so that every bypass path leads back to the vault Gmail account:

1. **The AES key is not stored locally.** It exists only in the private vault repo.

2. **The vault repo requires the vault Gmail.** GitHub account recovery goes to the recovery email — which is the vault Gmail itself (or is absent). There is no secondary recovery path.

3. **The vault Gmail password is locked in TimeSafe.** To access the vault Gmail, you need the vault Gmail password. That password is itself a locked secret.

4. **The vault Gmail has no recovery options.** No recovery email. No recovery phone. Removing these is a required setup step (see [Getting Started](getting-started.md)).

5. **Physical backup codes are the only emergency path.** If you truly need emergency access, the backup codes (stored physically) can get you into the vault Gmail. But this requires physical access to the backup codes — which you (ideally) stored somewhere deliberately inconvenient.

The recursive structure means breaking the lock early requires physically retrieving backup codes from storage. That friction is the point.

---

## AES/CBC trade-off

TimeSafe uses **AES/CBC/PKCS5Padding** without a message authentication code (MAC). This means the ciphertext is **not authenticated**.

Without a MAC, an attacker with write access to the local `.enc` files could perform a bit-flipping attack to corrupt or manipulate the decrypted output. The attacker would not learn the plaintext, but could produce garbage or partially controlled output.

This is an accepted trade-off for this threat model:

- The threat is self-restraint, not adversarial tampering.
- The lock guarantee comes from key inaccessibility (stored remotely, delivered by schedule), not from cipher authentication.
- AES/GCM (which provides authentication) requires a unique nonce per encryption and adds implementation complexity for marginal security gain in this context.

The SpotBugs/FindSecBugs `CIPHER_INTEGRITY` finding for this is suppressed in the build configuration with this justification documented inline.

---

## Key strength

- **AES key**: 256-bit, generated with `java.security.SecureRandom`. This is cryptographically strong random — not `java.util.Random`.
- **IV**: 128-bit, generated with `java.security.SecureRandom` per secret. A fresh IV per secret ensures that two secrets with the same plaintext produce different ciphertext.

The FindSecBugs `DMI_RANDOM_USED_ONLY_ONCE` finding is a false positive on `SecureRandom` — it is intended to be used once per encryption operation.

---

## GitHub as key store

The vault repo is a private GitHub repository. Access requires either:

- A GitHub account with repo access (login → vault Gmail), OR
- A GitHub PAT with `repo` scope for that repo

**PAT compromise**: If the PAT stored in `~/.timesafe/config.json` is compromised, an attacker could read the key files from the vault repo and decrypt your secrets. Mitigation:

- Use a fine-grained PAT scoped to only the vault repo.
- Protect `~/.timesafe/config.json` with `chmod 600`.
- Rotate the PAT periodically.

**GitHub outage**: If GitHub is unavailable on the scheduled unlock date, the Actions workflow will not run. The `workflow_dispatch` trigger allows manual re-run once GitHub is available — but only from within the vault repo interface, which requires vault Gmail access.

---

## SpotBugs / FindSecBugs

The build runs FindSecBugs static analysis on every `./gradlew check`. The following findings are suppressed with documented justifications:

| Finding | Location | Justification |
|---------|----------|--------------|
| `CIPHER_INTEGRITY` | `EncryptDecrypt` | AES/CBC without HMAC is an accepted trade-off for this threat model (documented above) |
| `DMI_RANDOM_USED_ONLY_ONCE` | Key/IV generation | False positive — `SecureRandom` is correctly used once per encryption operation |
| `DM_DEFAULT_ENCODING` | Console `Scanner` | Terminal character encoding is intentional for the interactive console UI |

All other SpotBugs findings must be clean for the build to pass.

---

## What this does NOT protect against

| Threat | Why it's out of scope |
|--------|-----------------------|
| Adversarial attack on the vault repo | The repo is private but not hardened against a determined attacker with a compromised PAT |
| Physical access to backup codes | Backup codes are the designed emergency path; physical security is the user's responsibility |
| Malware on the machine | Keyloggers or memory scrapers could capture the plaintext at the moment of decryption |
| Account takeover of delivery email | The key email is sent to a delivery address; if that account is compromised, the key is exposed |
| Social engineering GitHub support | GitHub support account recovery policies are outside TimeSafe's control |

If you are protecting against any of these threats, TimeSafe is not the right tool for your use case.
