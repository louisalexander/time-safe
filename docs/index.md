# TimeSafe for Secrets

[![CI](https://github.com/louisalexander/time-safe/actions/workflows/ci.yml/badge.svg)](https://github.com/louisalexander/time-safe/actions/workflows/ci.yml)
![Java](https://img.shields.io/badge/Java-21-orange?logo=openjdk)
![Gradle](https://img.shields.io/badge/Gradle-8.8-02303A?logo=gradle)

**Encrypt a password and time-lock it so that not even you can access it until the unlock date.**

TimeSafe is a console tool for locking passwords to sites you want to stay off. You encrypt a secret, choose a lock duration (e.g. 90 days), and the decryption key is delivered to you by email on the unlock date. Until then — even if you're desperate — the key does not exist anywhere you can reach it.

## Why it works

The core insight: if the decryption key is never stored locally, and the only way to get it is an email sent by a scheduled job on a future date, then there is no bypass flow. You cannot "recover" the key early. You cannot reset the password on the locked site without access to the vault email — which you've also locked.

## Quick links

- [Architecture](architecture.md) — how the encryption and time-lock mechanism work
- [Getting Started](getting-started.md) — setup guide
- [Usage](usage.md) — CLI reference
- [Security](security.md) — threat model and known trade-offs
