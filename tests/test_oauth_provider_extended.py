"""Extended tests for OAuth provider — pco_callback and token exchange paths."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

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


VALID_FERNET_KEY = "qf3WS_ifAWXQ6Pve5_lRuNIcyDstvOGlYN8EvHSfAzE="


@pytest.fixture
def app(mock_session_factory):
    factory, _ = mock_session_factory
    app = FastAPI()
    router = create_oauth_router(
        session_factory=factory,
        pco_client_id="test-pco-client",
        pco_client_secret="test-pco-secret",
        base_url="https://pco-mcp.example.com",
        token_encryption_key=VALID_FERNET_KEY,
    )
    app.include_router(router, prefix="/oauth")
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=True)


class TestPcoCallbackEndpoint:
    def test_callback_with_error_returns_400(self, client) -> None:
        resp = client.get(
            "/oauth/pco-callback",
            params={"error": "access_denied", "state": "some-state"},
            follow_redirects=False,
        )
        assert resp.status_code == 400

    def test_callback_with_invalid_state_returns_400(self, client) -> None:
        resp = client.get(
            "/oauth/pco-callback",
            params={"code": "some-code", "state": "nonexistent-state"},
            follow_redirects=False,
        )
        assert resp.status_code == 400

    def test_callback_with_valid_state_exchanges_code(
        self, client, mock_session_factory
    ) -> None:
        factory, session = mock_session_factory

        # Pre-populate pending state
        internal_state = "valid-internal-state-abc123"
        _pending_auth_codes[internal_state] = {
            "chatgpt_client_id": "test-client",
            "chatgpt_redirect_uri": "https://chatgpt.com/callback",
            "chatgpt_state": "original-state",
            "code_challenge": "",
            "code_challenge_method": "",
        }

        # Mock PCO exchange and /me response
        fake_tokens = {
            "access_token": "pco-access-token",
            "refresh_token": "pco-refresh-token",
            "expires_in": 7200,
        }
        fake_me = {
            "id": 42,
            "first_name": "Alice",
            "last_name": "Smith",
            "org_name": "TestChurch",
        }

        # Simulate no existing user in DB
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.commit = AsyncMock()

        # We need refresh on the user to set user.id
        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        session.refresh = AsyncMock(side_effect=lambda u: setattr(u, "id", fake_user.id))

        with (
            patch(
                "pco_mcp.oauth.pco_client.exchange_pco_code",
                new=AsyncMock(return_value=fake_tokens),
            ),
            patch(
                "pco_mcp.oauth.pco_client.get_pco_me",
                new=AsyncMock(return_value=fake_me),
            ),
        ):
            resp = client.get(
                "/oauth/pco-callback",
                params={"code": "pco-auth-code", "state": internal_state},
                follow_redirects=False,
            )

        assert resp.status_code in (302, 307)
        location = resp.headers["location"]
        assert "chatgpt.com/callback" in location
        assert "code=" in location
        assert "state=original-state" in location

    def test_callback_updates_existing_user(
        self, client, mock_session_factory
    ) -> None:
        factory, session = mock_session_factory

        internal_state = "valid-state-existing-user"
        _pending_auth_codes[internal_state] = {
            "chatgpt_client_id": "test-client",
            "chatgpt_redirect_uri": "https://chatgpt.com/callback",
            "chatgpt_state": "state-xyz",
            "code_challenge": "",
            "code_challenge_method": "",
        }

        fake_tokens = {
            "access_token": "pco-access-token",
            "refresh_token": "pco-refresh-token",
            "expires_in": 7200,
        }
        fake_me = {"id": 99, "first_name": "Bob", "last_name": "Jones", "org_name": "Church"}

        # Simulate existing user
        existing_user = MagicMock()
        existing_user.id = uuid.uuid4()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        session.execute = AsyncMock(return_value=mock_result)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()

        with (
            patch(
                "pco_mcp.oauth.pco_client.exchange_pco_code",
                new=AsyncMock(return_value=fake_tokens),
            ),
            patch(
                "pco_mcp.oauth.pco_client.get_pco_me",
                new=AsyncMock(return_value=fake_me),
            ),
        ):
            resp = client.get(
                "/oauth/pco-callback",
                params={"code": "pco-auth-code", "state": internal_state},
                follow_redirects=False,
            )

        assert resp.status_code in (302, 307)


class TestTokenEndpointExtended:
    def test_token_with_valid_authorization_code(
        self, client, mock_session_factory
    ) -> None:
        factory, session = mock_session_factory

        # Pre-populate a valid auth code
        our_code = "valid-auth-code-xyz"
        user_id = str(uuid.uuid4())
        _pending_auth_codes[our_code] = {
            "user_id": user_id,
            "chatgpt_client_id": "test-client",
            "code_challenge": "",
            "type": "auth_code",
        }

        session.add = MagicMock()
        session.commit = AsyncMock()

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": our_code,
                "redirect_uri": "https://chatgpt.com/callback",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert "expires_in" in body
        assert "refresh_token" in body

    def test_token_with_refresh_grant_returns_new_token(self, client) -> None:
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": "some-refresh-token",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert "expires_in" in body

    def test_token_with_unsupported_grant_type_returns_400(self, client) -> None:
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
            },
        )
        assert resp.status_code == 400

    def test_token_code_consumed_after_use(self, client, mock_session_factory) -> None:
        """Auth code should be consumed (one-time use)."""
        factory, session = mock_session_factory

        our_code = "one-time-code"
        user_id = str(uuid.uuid4())
        _pending_auth_codes[our_code] = {
            "user_id": user_id,
            "chatgpt_client_id": "test-client",
            "code_challenge": "",
            "type": "auth_code",
        }
        session.add = MagicMock()
        session.commit = AsyncMock()

        # First use — should succeed
        resp1 = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": our_code,
                "redirect_uri": "https://chatgpt.com/callback",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
        )
        assert resp1.status_code == 200

        # Second use — code is gone, should fail
        resp2 = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": our_code,
                "redirect_uri": "https://chatgpt.com/callback",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
        )
        assert resp2.status_code == 400
