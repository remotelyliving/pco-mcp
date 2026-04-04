"""Extended tests for OAuth provider — pco_callback and token exchange paths."""
import base64
import hashlib
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


def _register_client(client, redirect_uris=None):
    """Helper: register a client and return its credentials."""
    if redirect_uris is None:
        redirect_uris = ["https://chatgpt.com/callback"]
    resp = client.post("/oauth/register", json={"redirect_uris": redirect_uris})
    assert resp.status_code == 201
    return resp.json()


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

        # Register client first (C4 requirement)
        info = _register_client(client)

        # Pre-populate a valid auth code
        our_code = "valid-auth-code-xyz"
        user_id = str(uuid.uuid4())
        _pending_auth_codes[our_code] = {
            "user_id": user_id,
            "chatgpt_client_id": info["client_id"],
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
                "client_id": info["client_id"],
                "client_secret": info["client_secret"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert "expires_in" in body
        assert "refresh_token" in body

    def test_token_refresh_token_hash_stored(
        self, client, mock_session_factory
    ) -> None:
        """C2: refresh_token_hash should be stored in the DB session."""
        factory, session = mock_session_factory

        info = _register_client(client)
        our_code = "code-for-hash-check"
        user_id = str(uuid.uuid4())
        _pending_auth_codes[our_code] = {
            "user_id": user_id,
            "chatgpt_client_id": info["client_id"],
            "code_challenge": "",
            "type": "auth_code",
        }

        captured_sessions = []
        original_add = MagicMock(side_effect=lambda s: captured_sessions.append(s))
        session.add = original_add
        session.commit = AsyncMock()

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": our_code,
                "redirect_uri": "https://chatgpt.com/callback",
                "client_id": info["client_id"],
                "client_secret": info["client_secret"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        # Verify that the stored hash matches the returned refresh token
        rt = body["refresh_token"]
        expected_hash = hashlib.sha256(rt.encode()).hexdigest()
        assert len(captured_sessions) == 1
        assert captured_sessions[0].refresh_token_hash == expected_hash

    def test_token_with_refresh_grant_valid(self, client, mock_session_factory) -> None:
        """C2: A valid refresh_token should return new tokens."""
        factory, session = mock_session_factory

        refresh_token_value = "valid-refresh-token-xyz"
        rt_hash = hashlib.sha256(refresh_token_value.encode()).hexdigest()

        from pco_mcp.models import OAuthSession

        fake_old_session = MagicMock(spec=OAuthSession)
        fake_old_session.user_id = uuid.uuid4()
        fake_old_session.refresh_token_hash = rt_hash

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = fake_old_session
        session.execute = AsyncMock(return_value=mock_result)
        session.delete = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token_value,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert "expires_in" in body
        # Old session was deleted (token rotation)
        session.delete.assert_called_once_with(fake_old_session)

    def test_token_with_refresh_grant_invalid_token_returns_401(
        self, client, mock_session_factory
    ) -> None:
        """C2: An invalid refresh_token should return 401."""
        factory, session = mock_session_factory

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": "bogus-refresh-token",
            },
        )
        assert resp.status_code == 401

    def test_token_with_refresh_grant_missing_token_returns_400(self, client) -> None:
        """C2: Missing refresh_token body field returns 400."""
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "refresh_token",
            },
        )
        assert resp.status_code == 400

    def test_token_pkce_valid_verifier(
        self, client, mock_session_factory
    ) -> None:
        """C3: Valid PKCE code_verifier is accepted."""
        factory, session = mock_session_factory

        info = _register_client(client)

        code_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        verifier_hash = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b"=").decode()

        our_code = "pkce-auth-code"
        user_id = str(uuid.uuid4())
        _pending_auth_codes[our_code] = {
            "user_id": user_id,
            "chatgpt_client_id": info["client_id"],
            "code_challenge": verifier_hash,
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
                "client_id": info["client_id"],
                "client_secret": info["client_secret"],
                "code_verifier": code_verifier,
            },
        )
        assert resp.status_code == 200

    def test_token_pkce_invalid_verifier_returns_400(
        self, client, mock_session_factory
    ) -> None:
        """C3: Wrong code_verifier is rejected with 400."""
        factory, session = mock_session_factory

        info = _register_client(client)

        code_verifier = "correct-verifier"
        verifier_hash = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b"=").decode()

        our_code = "pkce-fail-code"
        user_id = str(uuid.uuid4())
        _pending_auth_codes[our_code] = {
            "user_id": user_id,
            "chatgpt_client_id": info["client_id"],
            "code_challenge": verifier_hash,
            "type": "auth_code",
        }

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": our_code,
                "redirect_uri": "https://chatgpt.com/callback",
                "client_id": info["client_id"],
                "client_secret": info["client_secret"],
                "code_verifier": "wrong-verifier",
            },
        )
        assert resp.status_code == 400

    def test_token_pkce_missing_verifier_returns_400(
        self, client, mock_session_factory
    ) -> None:
        """C3: Missing code_verifier when challenge is present returns 400."""
        factory, session = mock_session_factory

        info = _register_client(client)

        our_code = "pkce-missing-verifier-code"
        user_id = str(uuid.uuid4())
        _pending_auth_codes[our_code] = {
            "user_id": user_id,
            "chatgpt_client_id": info["client_id"],
            "code_challenge": "some-challenge-hash",
            "type": "auth_code",
        }

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": our_code,
                "redirect_uri": "https://chatgpt.com/callback",
                "client_id": info["client_id"],
                "client_secret": info["client_secret"],
                # No code_verifier
            },
        )
        assert resp.status_code == 400

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

        info = _register_client(client)

        our_code = "one-time-code"
        user_id = str(uuid.uuid4())
        _pending_auth_codes[our_code] = {
            "user_id": user_id,
            "chatgpt_client_id": info["client_id"],
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
                "client_id": info["client_id"],
                "client_secret": info["client_secret"],
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
                "client_id": info["client_id"],
                "client_secret": info["client_secret"],
            },
        )
        assert resp2.status_code == 400
