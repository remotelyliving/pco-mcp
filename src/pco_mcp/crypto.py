from cryptography.fernet import Fernet


def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key. Use this once to create TOKEN_ENCRYPTION_KEY."""
    return Fernet.generate_key().decode()


def encrypt_token(plaintext: str, key: str) -> bytes:
    """Encrypt a token string. Returns encrypted bytes for database storage."""
    f = Fernet(key.encode())
    return f.encrypt(plaintext.encode())


def decrypt_token(encrypted: bytes, key: str) -> str:
    """Decrypt token bytes back to a string."""
    f = Fernet(key.encode())
    return f.decrypt(encrypted).decode()
