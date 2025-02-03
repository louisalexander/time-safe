# TimeSafe for Secrets

A **TimeSafe** application that encrypts secrets and locks them until a specified future date. The system uses AES encryption (via [Apache Commons Crypto](https://commons.apache.org/proper/commons-crypto/)) to protect data, and Java’s serialization to store encrypted objects in a local `vault` directory on disk.

This repository contains a simple console-based interface to:
- **Add new secrets** (encrypted immediately).
- **List existing secrets**.
- **Manage secrets** (view metadata, decrypt if unlocked, extend lock time, or delete).

> **Note**: This code is intended for demonstration purposes and is not production-hardened. Storing hard-coded keys and IVs in source code is **not** secure for real-world applications.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Key Components](#key-components)
    - [EncryptDecrypt](#encryptdecrypt)
    - [Secret](#secret)
    - [VaultManager](#vaultmanager)
    - [Main](#main)
3. [Application Flow](#application-flow)
4. [Usage](#usage)
    - [Prerequisites](#prerequisites)
    - [Running the Application](#running-the-application)
5. [Technical Details](#technical-details)
6. [Security Considerations](#security-considerations)
7. [License](#license)

---

## Architecture Overview

```mermaid
flowchart LR
    A[Console] --> B[VaultManager]
    B --> C[EncryptDecrypt]
    B --> D[Secret]

    C -- AES/CBC Encryption/Decryption --> F[Apache Commons Crypto]
    D -- Persist/Load --> E[Local Filesystem (vault/)]