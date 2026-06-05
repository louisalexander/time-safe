import base64

from nacl.public import PrivateKey, SealedBox

from timesafe.github.secrets_api import seal


def test_seal_is_openable_by_the_private_key():
    # GitHub gives you the repo's Actions *public* key; only GitHub holds the private key.
    # Here we simulate: generate a keypair, seal to the public half, open with the private half.
    sk = PrivateKey.generate()
    public_key_b64 = base64.b64encode(bytes(sk.public_key)).decode()

    sealed_b64 = seal(public_key_b64, "ghp_my_token")
    opened = SealedBox(sk).decrypt(base64.b64decode(sealed_b64))

    assert opened == b"ghp_my_token"
