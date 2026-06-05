from __future__ import annotations

import base64

from nacl.public import PublicKey, SealedBox


def seal(public_key_b64: str, value: str) -> str:
    """Encrypt `value` to a repo's Actions public key (libsodium sealed box), base64-encoded."""
    public_key = PublicKey(base64.b64decode(public_key_b64))
    sealed = SealedBox(public_key).encrypt(value.encode())
    return base64.b64encode(sealed).decode()
