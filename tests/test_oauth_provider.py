from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pco_mcp.oauth.provider import create_oauth_router


@pytest.fixture
def mock_session_factory():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=session)
    return factory, session


@pytest.fixture
def app(mock_session_factory):
    factory, _ = mock_session_factory
    app = FastAPI()
    router = create_oauth_router(
        session_factory=factory,
        pco_client_id="test-pco-client",
        pco_client_secret="test-pco-secret",
        base_url="https://pco-mcp.example.com",
        token_encryption_key="HQYbzO62Z1jN8p4DURY5muSedU5KOoZqGf7oWytQ_BI=",
    )
    app.include_router(router, prefix="/oauth")
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestDynamicClientRegistration:
    def test_register_returns_client_credentials(self, client) -> None:
        resp = client.post(
            "/oauth/register",
            json={"redirect_uris": ["https://chatgpt.com/callback"]},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "client_id" in body
        assert "client_secret" in body

    def test_register_requires_redirect_uris(self, client) -> None:
        resp = client.post("/oauth/register", json={})
        assert resp.status_code == 422 or resp.status_code == 400


class TestAuthorizeEndpoint:
    def test_authorize_redirects_to_pco(self, client) -> None:
        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": "test-client",
                "redirect_uri": "https://chatgpt.com/callback",
                "response_type": "code",
                "state": "abc123",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        location = resp.headers["location"]
        assert "api.planningcenteronline.com/oauth/authorize" in location


class TestTokenEndpoint:
    def test_token_rejects_invalid_code(self, client) -> None:
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": "invalid-code",
                "redirect_uri": "https://chatgpt.com/callback",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
        )
        assert resp.status_code in (400, 401)
