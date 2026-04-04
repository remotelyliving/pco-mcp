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
        assert resp.status_code in (200, 400, 401, 405, 406)


class TestOAuthEndpoints:
    def test_register_endpoint_exists(self, client) -> None:
        resp = client.post(
            "/oauth/register",
            json={"redirect_uris": ["https://chatgpt.com/callback"]},
        )
        assert resp.status_code == 201

    def test_authorize_endpoint_exists(self, client) -> None:
        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": "test",
                "redirect_uri": "https://chatgpt.com/callback",
                "response_type": "code",
                "state": "test",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
