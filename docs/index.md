# time-safe

[![Python](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
![Textual](https://img.shields.io/badge/TUI-Textual-5A2CA0)
![timelock](https://img.shields.io/badge/timelock-drand%2Ftlock-F46036)

**Lock a secret until a future moment — so that *nobody*, not even you, can read it early.**

time-safe timelock-encrypts your secrets, stores the ciphertext in a GitHub repo, and lets you reveal them only **after a date you choose**. The lock is enforced by cryptography — the [drand](https://drand.love) randomness beacon via [tlock](https://github.com/drand/tlock) — not by an honour system.

![secrets list](screenshots/02-secrets-list.svg)

## Why it works

Each secret is encrypted to a **future drand round**. The round's threshold signature — the only thing that can decrypt it — is not produced by the beacon network until that wall-clock time arrives. So there is **no key stored anywhere** and **no bypass**: you cannot "recover" it early, GitHub cannot read it, and copying the repo doesn't help. Once the time passes, the signature becomes public and the app decrypts locally, in memory.

## Quick links

- [Getting Started](getting-started.md) — install, create a vault, add a secret
- [Usage](usage.md) — screens and keys
- [Architecture](architecture.md) — how the timelock + delivery work
- [Security](security.md) — threat model and trade-offs

## At a glance

| Vaults | Secret (ready) | Add secret |
|:---:|:---:|:---:|
| ![](screenshots/01-vault-picker.svg) | ![](screenshots/03-secret-detail-ready.svg) | ![](screenshots/04-add-secret.svg) |
