# tests/test_web_routes.py
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    with patch.dict(
        "os.environ",
        {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "PCO_CLIENT_ID": "test-client",
            "PCO_CLIENT_SECRET": "test-secret",
            "TOKEN_ENCRYPTION_KEY": "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=",
            "SECRET_KEY": "test-secret-key",
            "BASE_URL": "https://pco-mcp.example.com",
        },
    ):
        from pco_mcp.main import create_app
        return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


class TestLandingPage:
    def test_landing_returns_html(self, client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Planning Center" in resp.text

    def test_landing_has_get_started_link(self, client) -> None:
        resp = client.get("/")
        assert "Get Started" in resp.text


class TestSetupGuide:
    def test_setup_guide_returns_html(self, client) -> None:
        resp = client.get("/setup-guide")
        assert resp.status_code == 200
        assert "ChatGPT" in resp.text
