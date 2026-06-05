# Security

## What the lock guarantees

Confidentiality **before** the unlock time is **cryptographic**. Each secret is timelock-encrypted (drand/tlock) to a future round; the threshold-BLS signature that decrypts it does not exist until that wall-clock time. So before then:

- **You** can't read it early — there's no key to find, no bypass flow.
- **GitHub** can't read it — the repo holds only ciphertext.
- **Anyone who copies the repo** can't read it — same reason.

This is a real improvement over a "key sitting next to the ciphertext" design, where anyone with repo access could decrypt at any time.

## Trust assumptions

- **drand threshold integrity.** Decryption depends on the drand "quicknet" network (a ~t-of-n threshold across independent operators, the League of Entropy). The lock holds as long as that threshold isn't compromised before the unlock time.
- **drand liveness.** The round signature must eventually be published. drand is a robust, multi-organisation network built for exactly this; the chain hash is pinned per secret so decryption is reproducible. If quicknet ever permanently disappeared, affected secrets would become undecryptable. (A future option is to double-wrap with a key you control as outage insurance.)

## After unlock

Once a secret's round passes, its signature is public, so **anyone with read access to the vault repo can decrypt it.** Therefore:

- Keep the vault repo **private**. (time-safe should refuse to initialize a public repo.)
- "Reveal" decrypts locally and never writes plaintext to disk.

## The unlock time is immutable

A genuine time-lock can't be shortened or extended while locked — the ciphertext is cryptographically bound to its round, and you'd need the plaintext (which you can't read yet) to re-encrypt. **Renew** therefore only works on a secret that's already **ready**: it reveals and re-encrypts to a new round.

## Credentials

- **GitHub PAT** — stored in your OS keychain (`keyring`), never in a plaintext file. Use a fine-grained token scoped to the vault repo; rotate if exposed.
- **Gmail OAuth** (only if you use email delivery) — the refresh token and client secret are stored **only** as GitHub Actions secrets in the vault repo (written via a libsodium sealed box), never locally. A revoked token surfaces as a GitHub issue prompting you to re-link.

## Email delivery carries plaintext

The optional "Email it" path sends the **decrypted secret** to the delivery address via Gmail at/after the unlock time. If you'd rather plaintext never traverse email, use local **Reveal** instead (the default), which keeps it on your machine.

## Out of scope

- Malware on your machine (a keylogger/memory scraper could capture plaintext at reveal time).
- Compromise of the delivery email account (if you use email delivery).
- A determined attacker who already has read access to a vault repo *after* its secrets unlock.

For protecting secrets from a third party (rather than from your future self / premature access), use a purpose-built secrets manager.
