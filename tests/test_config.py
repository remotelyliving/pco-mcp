import os

import pytest


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/pco")
    monkeypatch.setenv("PCO_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("PCO_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0xMjM0NTY3ODk=")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BASE_URL", "https://pco-mcp.example.com")

    from pco_mcp.config import Settings

    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost/pco"
    assert settings.pco_client_id == "test-client-id"
    assert settings.pco_client_secret == "test-client-secret"
    assert settings.base_url == "https://pco-mcp.example.com"
    assert settings.token_encryption_key != ""
    assert settings.secret_key == "test-secret-key"


def test_settings_has_defaults_for_optional_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/pco")
    monkeypatch.setenv("PCO_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("PCO_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0xMjM0NTY3ODk=")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BASE_URL", "https://pco-mcp.example.com")

    from pco_mcp.config import Settings

    settings = Settings()
    assert settings.pco_api_base == "https://api.planningcenteronline.com"
    assert settings.pco_rate_limit_buffer == 10
    assert settings.token_expiry_hours == 24


def test_settings_missing_required_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PCO_CLIENT_ID", raising=False)
    monkeypatch.delenv("PCO_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("BASE_URL", raising=False)

    from pydantic import ValidationError

    from pco_mcp.config import Settings

    with pytest.raises(ValidationError):
        Settings()
