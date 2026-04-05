import base64
import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pco_mcp.oauth.provider import _pending_auth_codes, _registered_clients, create_oauth_router


@pytest.fixture(autouse=True)
def _clear_state():
    """Clear global dicts before each test to avoid state leakage."""
    _pending_auth_codes.clear()
    _registered_clients.clear()
    yield
    _pending_auth_codes.clear()
    _registered_clients.clear()


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

    def test_register_accepts_empty_body(self, client) -> None:
        # Be lenient: ChatGPT may probe DCR with minimal payloads to verify
        # the endpoint exists before sending the real registration.
        resp = client.post("/oauth/register", json={})
        assert resp.status_code == 201
        body = resp.json()
        assert "client_id" in body
        assert body["redirect_uris"] == []


class TestAuthorizeEndpoint:
    def test_authorize_redirects_to_pco_unregistered_client(self, client) -> None:
        """Unregistered clients are allowed through (ChatGPT hits /authorize before /register)."""
        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": "unknown-client",
                "redirect_uri": "https://chatgpt.com/callback",
                "response_type": "code",
                "state": "abc123",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        location = resp.headers["location"]
        assert "api.planningcenteronline.com/oauth/authorize" in location

    def test_authorize_redirects_to_pco_registered_client_valid_uri(self, client) -> None:
        """Registered client with a valid redirect_uri is allowed through."""
        reg = client.post(
            "/oauth/register",
            json={"redirect_uris": ["https://chatgpt.com/callback"]},
        )
        info = reg.json()
        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": info["client_id"],
                "redirect_uri": "https://chatgpt.com/callback",
                "response_type": "code",
                "state": "abc123",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        assert "api.planningcenteronline.com/oauth/authorize" in resp.headers["location"]

    def test_authorize_rejects_unregistered_redirect_uri(self, client) -> None:
        """Registered client with an unregistered redirect_uri is rejected (C5)."""
        reg = client.post(
            "/oauth/register",
            json={"redirect_uris": ["https://chatgpt.com/callback"]},
        )
        info = reg.json()
        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": info["client_id"],
                "redirect_uri": "https://evil.com/steal",
                "response_type": "code",
                "state": "abc123",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 400


class TestTokenEndpoint:
    def test_token_rejects_unknown_client(self, client, mock_session_factory) -> None:
        """C4: unknown client_id is rejected with 401."""
        import uuid
        our_code = "some-auth-code"
        _pending_auth_codes[our_code] = {
            "user_id": str(uuid.uuid4()),
            "chatgpt_client_id": "unknown-client",
            "code_challenge": "",
            "type": "auth_code",
        }
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": our_code,
                "redirect_uri": "https://chatgpt.com/callback",
                "client_id": "unknown-client",
                "client_secret": "wrong-secret",
            },
        )
        assert resp.status_code == 401

    def test_token_rejects_wrong_client_secret(self, client, mock_session_factory) -> None:
        """C4: wrong client_secret is rejected with 401."""
        import uuid
        reg = client.post(
            "/oauth/register",
            json={"redirect_uris": ["https://chatgpt.com/callback"]},
        )
        info = reg.json()
        our_code = "some-auth-code"
        _pending_auth_codes[our_code] = {
            "user_id": str(uuid.uuid4()),
            "chatgpt_client_id": info["client_id"],
            "code_challenge": "",
            "type": "auth_code",
        }
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": our_code,
                "redirect_uri": "https://chatgpt.com/callback",
                "client_id": info["client_id"],
                "client_secret": "totally-wrong-secret",
            },
        )
        assert resp.status_code == 401

    def test_token_rejects_invalid_code(self, client) -> None:
        """Invalid auth code is rejected (client must be registered first)."""
        reg = client.post(
            "/oauth/register",
            json={"redirect_uris": ["https://chatgpt.com/callback"]},
        )
        info = reg.json()
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": "invalid-code",
                "redirect_uri": "https://chatgpt.com/callback",
                "client_id": info["client_id"],
                "client_secret": info["client_secret"],
            },
        )
        assert resp.status_code in (400, 401)
