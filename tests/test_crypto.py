import pytest

from pco_mcp.crypto import decrypt_token, encrypt_token, generate_encryption_key


def test_encrypt_decrypt_roundtrip() -> None:
    key = generate_encryption_key()
    plaintext = "oauth-access-token-abc123"
    encrypted = encrypt_token(plaintext, key)
    assert encrypted != plaintext.encode()
    decrypted = decrypt_token(encrypted, key)
    assert decrypted == plaintext


def test_decrypt_with_wrong_key_raises() -> None:
    key1 = generate_encryption_key()
    key2 = generate_encryption_key()
    encrypted = encrypt_token("secret", key1)
    with pytest.raises(Exception):
        decrypt_token(encrypted, key2)


def test_encrypt_returns_bytes() -> None:
    key = generate_encryption_key()
    result = encrypt_token("test", key)
    assert isinstance(result, bytes)


def test_generate_key_returns_valid_fernet_key() -> None:
    key = generate_encryption_key()
    assert isinstance(key, str)
    # Fernet keys are 44 chars base64
    assert len(key) == 44
