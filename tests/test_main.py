# tests/test_main.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from pco_mcp.main import create_app
    return create_app()


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


class TestHealthCheck:
    def test_health_returns_ok(self, client) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestMCPEndpoint:
    def test_mcp_endpoint_exists(self, client) -> None:
        resp = client.get("/mcp/")
        # May be 200, 400, 401, 405, 406 — just ensure it is reachable
        assert resp.status_code in (200, 400, 401, 405, 406)


class TestOAuthMetadata:
    """FastMCP's OAuthProxy serves .well-known endpoints automatically."""

    def test_oauth_authorization_server_metadata(self, client) -> None:
        resp = client.get("/.well-known/oauth-authorization-server")
        assert resp.status_code == 200
        body = resp.json()
        assert "authorization_endpoint" in body
        assert "token_endpoint" in body
        assert "registration_endpoint" in body
