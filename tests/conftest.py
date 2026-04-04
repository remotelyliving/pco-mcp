# tests/conftest.py
import pytest


@pytest.fixture(autouse=True)
def _test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure test environment variables are set for all tests."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("PCO_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("PCO_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BASE_URL", "https://pco-mcp.test")
