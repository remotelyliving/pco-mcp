# tests/test_oauth_endpoints.py
"""Tests for the plain-FastAPI OAuth layer in main.py.

Covers: discovery, protected-resource, register, authorize, token,
pco-callback (both ChatGPT and direct flows), and bearer middleware.
"""
import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

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


# -- helpers --

def _register_client(client: TestClient) -> dict:
    """Register a dynamic client and return the response body."""
    resp = client.post(
        "/oauth/register",
        json={"redirect_uris": ["https://example.com/cb"], "client_name": "Test"},
    )
    assert resp.status_code == 201
    return resp.json()


def _seed_auth_code(client_id: str) -> str:
    """Seed an auth code in the global store and return it."""
    from pco_mcp.main import oauth_codes

    code = secrets.token_urlsafe(32)
    oauth_codes[code] = {
        "type": "auth_code",
        "client_id": client_id,
        "pco_access_token": "pco-test-token",
        "pco_refresh_token": "pco-test-refresh",
        "pco_me": {"id": 99, "org_name": "Test Church"},
        "expires": datetime.now(UTC) + timedelta(minutes=10),
    }
    return code


# =========================================================================
# OAuth Discovery
# =========================================================================


class TestOAuthDiscovery:
    def test_authorization_server_metadata(self, client) -> None:
        resp = client.get("/.well-known/oauth-authorization-server")
        assert resp.status_code == 200
        body = resp.json()
        assert "authorization_endpoint" in body
        assert "token_endpoint" in body
        assert "registration_endpoint" in body
        assert body["response_types_supported"] == ["code"]
        assert "client_credentials" in body["grant_types_supported"]
        assert "authorization_code" in body["grant_types_supported"]
        assert "client_secret_post" in body["token_endpoint_auth_methods_supported"]

    def test_issuer_uses_settings_base_url(self, client) -> None:
        resp = client.get("/.well-known/oauth-authorization-server")
        body = resp.json()
        # Uses settings.base_url (HTTPS), not request.base_url (HTTP behind proxy)
        assert body["issuer"] == "https://pco-mcp.test"

    def test_protected_resource(self, client) -> None:
        resp = client.get("/.well-known/oauth-protected-resource")
        assert resp.status_code == 200
        body = resp.json()
        assert body["resource"] == "https://pco-mcp.test"
        assert "https://pco-mcp.test" in body["authorization_servers"]
        assert body["bearer_methods_supported"] == ["header"]


# =========================================================================
# OAuth Register (DCR)
# =========================================================================


class TestOAuthRegister:
    def test_register_returns_client_credentials(self, client) -> None:
        body = _register_client(client)
        assert "client_id" in body
        assert "client_secret" in body
        assert body["client_id"].startswith("chatgpt-")
        assert body["client_secret_expires_at"] == 0
        assert body["token_endpoint_auth_method"] == "client_secret_post"
        assert "authorization_code" in body["grant_types"]
        assert "client_credentials" in body["grant_types"]
        assert body["response_types"] == ["code"]
        assert "client_id_issued_at" in body

    def test_register_stores_client(self, client) -> None:
        from pco_mcp.main import registered_clients

        body = _register_client(client)
        assert body["client_id"] in registered_clients
        stored = registered_clients[body["client_id"]]
        assert stored["client_secret"] == body["client_secret"]

    def test_register_preserves_redirect_uris(self, client) -> None:
        resp = client.post(
            "/oauth/register",
            json={"redirect_uris": ["https://a.com/cb", "https://b.com/cb"]},
        )
        body = resp.json()
        assert body["redirect_uris"] == ["https://a.com/cb", "https://b.com/cb"]

    def test_register_invalid_json(self, client) -> None:
        resp = client.post(
            "/oauth/register",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400

    def test_register_default_client_name(self, client) -> None:
        from pco_mcp.main import registered_clients

        resp = client.post("/oauth/register", json={})
        body = resp.json()
        assert registered_clients[body["client_id"]]["client_name"] == "ChatGPT MCP"


# =========================================================================
# OAuth Authorize
# =========================================================================


class TestOAuthAuthorize:
    def test_authorize_redirects_to_pco(self, client) -> None:
        reg = _register_client(client)
        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": reg["client_id"],
                "redirect_uri": "https://example.com/cb",
                "response_type": "code",
                "state": "mystate",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "api.planningcenteronline.com/oauth/authorize" in location
        assert "client_id=test-client-id" in location
        assert "pco-callback" in location

    def test_authorize_stores_pending_code(self, client) -> None:
        from pco_mcp.main import oauth_codes

        reg = _register_client(client)
        client.get(
            "/oauth/authorize",
            params={
                "client_id": reg["client_id"],
                "redirect_uri": "https://example.com/cb",
            },
            follow_redirects=False,
        )
        # Should have a pending_pco_auth entry for this client
        pending = [
            v for v in oauth_codes.values()
            if v.get("type") == "pending_pco_auth" and v.get("client_id") == reg["client_id"]
        ]
        assert len(pending) >= 1

    def test_authorize_invalid_client_id(self, client) -> None:
        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": "nonexistent",
                "redirect_uri": "https://example.com/cb",
            },
        )
        assert resp.status_code == 400


# =========================================================================
# OAuth Token
# =========================================================================


class TestOAuthToken:
    def test_token_exchange_authorization_code(self, client) -> None:
        reg = _register_client(client)
        code = _seed_auth_code(reg["client_id"])

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "code": code,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 3600

    def test_token_exchange_stores_pco_token(self, client) -> None:
        from pco_mcp.main import oauth_tokens

        reg = _register_client(client)
        code = _seed_auth_code(reg["client_id"])

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "code": code,
            },
        )
        access_token = resp.json()["access_token"]
        assert access_token in oauth_tokens
        assert oauth_tokens[access_token]["pco_access_token"] == "pco-test-token"

    def test_token_invalid_client(self, client) -> None:
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": "bad-client",
                "client_secret": "bad-secret",
                "code": "whatever",
            },
        )
        assert resp.status_code == 401

    def test_token_wrong_secret(self, client) -> None:
        reg = _register_client(client)
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg["client_id"],
                "client_secret": "wrong-secret",
                "code": "whatever",
            },
        )
        assert resp.status_code == 401

    def test_token_invalid_code(self, client) -> None:
        reg = _register_client(client)
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "code": "nonexistent-code",
            },
        )
        assert resp.status_code == 400

    def test_token_code_wrong_type(self, client) -> None:
        from pco_mcp.main import oauth_codes

        reg = _register_client(client)
        # seed a code with wrong type
        bad_code = "bad-type-code"
        oauth_codes[bad_code] = {
            "type": "pending_pco_auth",  # not auth_code
            "expires": datetime.now(UTC) + timedelta(minutes=10),
        }
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "code": bad_code,
            },
        )
        assert resp.status_code == 400

    def test_token_expired_code(self, client) -> None:
        from pco_mcp.main import oauth_codes

        reg = _register_client(client)
        expired_code = "expired-code"
        oauth_codes[expired_code] = {
            "type": "auth_code",
            "client_id": reg["client_id"],
            "pco_access_token": "pco-tok",
            "expires": datetime.now(UTC) - timedelta(minutes=1),
        }
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "code": expired_code,
            },
        )
        assert resp.status_code == 400

    def test_token_client_credentials_grant_rejected(self, client) -> None:
        reg = _register_client(client)
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
            },
        )
        assert resp.status_code == 400
        assert "not supported" in resp.json()["detail"]

    def test_token_unsupported_grant_type(self, client) -> None:
        reg = _register_client(client)
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
            },
        )
        assert resp.status_code == 400

    def test_token_code_consumed_single_use(self, client) -> None:
        """Auth codes are single-use."""
        reg = _register_client(client)
        code = _seed_auth_code(reg["client_id"])

        # First exchange succeeds
        resp1 = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "code": code,
            },
        )
        assert resp1.status_code == 200

        # Second exchange fails
        resp2 = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "code": code,
            },
        )
        assert resp2.status_code == 400


# =========================================================================
# PCO Callback
# =========================================================================


class TestPCOCallback:
    def test_callback_error_returns_400(self, client) -> None:
        resp = client.get("/oauth/pco-callback", params={"error": "access_denied"})
        assert resp.status_code == 400

    def test_callback_missing_code_returns_400(self, client) -> None:
        resp = client.get("/oauth/pco-callback", params={"state": "some-state"})
        assert resp.status_code == 400

    def test_callback_missing_state_returns_400(self, client) -> None:
        resp = client.get("/oauth/pco-callback", params={"code": "some-code"})
        assert resp.status_code == 400

    def test_callback_invalid_state_returns_400(self, client) -> None:
        resp = client.get(
            "/oauth/pco-callback",
            params={"code": "some-code", "state": "bad-state"},
        )
        assert resp.status_code == 400

    def test_callback_expired_state_returns_400(self, client) -> None:
        from pco_mcp.main import oauth_codes

        state = "expired-state"
        oauth_codes[state] = {
            "type": "pending_pco_auth",
            "client_id": "c1",
            "redirect_uri": "https://example.com/cb",
            "chatgpt_state": None,
            "expires": datetime.now(UTC) - timedelta(minutes=1),
        }
        resp = client.get(
            "/oauth/pco-callback",
            params={"code": "some-code", "state": state},
        )
        assert resp.status_code == 400

    @patch("pco_mcp.main.get_pco_me", new_callable=AsyncMock)
    @patch("pco_mcp.main.exchange_pco_code", new_callable=AsyncMock)
    def test_callback_chatgpt_flow_redirects_back(
        self, mock_exchange, mock_me, client
    ) -> None:
        from pco_mcp.main import oauth_codes

        mock_exchange.return_value = {
            "access_token": "pco-tok",
            "refresh_token": "pco-refresh",
        }
        mock_me.return_value = {"id": 42, "org_name": "Test Church"}

        state = "chatgpt-state-abc"
        oauth_codes[state] = {
            "type": "pending_pco_auth",
            "client_id": "chatgpt-test-client",
            "redirect_uri": "https://chatgpt.com/callback",
            "chatgpt_state": "original-chatgpt-state",
            "expires": datetime.now(UTC) + timedelta(minutes=10),
        }

        resp = client.get(
            "/oauth/pco-callback",
            params={"code": "pco-code", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "chatgpt.com/callback" in location
        assert "code=" in location
        assert "state=original-chatgpt-state" in location

    @patch("pco_mcp.main.get_pco_me", new_callable=AsyncMock)
    @patch("pco_mcp.main.exchange_pco_code", new_callable=AsyncMock)
    def test_callback_direct_flow_redirects_to_dashboard(
        self, mock_exchange, mock_me, client
    ) -> None:
        from pco_mcp.main import oauth_codes

        mock_exchange.return_value = {
            "access_token": "pco-direct-tok",
            "refresh_token": "pco-refresh",
        }
        mock_me.return_value = {"id": 77, "org_name": "Direct Church"}

        state = "direct-state-xyz"
        oauth_codes[state] = {
            "type": "pending_direct_auth",
            "expires": datetime.now(UTC) + timedelta(minutes=10),
        }

        resp = client.get(
            "/oauth/pco-callback",
            params={"code": "pco-code", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "/dashboard?token=" in location

    @patch("pco_mcp.main.get_pco_me", new_callable=AsyncMock)
    @patch("pco_mcp.main.exchange_pco_code", new_callable=AsyncMock)
    def test_callback_chatgpt_flow_without_state(
        self, mock_exchange, mock_me, client
    ) -> None:
        """chatgpt_state=None means no state param in redirect."""
        from pco_mcp.main import oauth_codes

        mock_exchange.return_value = {"access_token": "pco-tok"}
        mock_me.return_value = {"id": 42}

        state = "no-state-flow"
        oauth_codes[state] = {
            "type": "pending_pco_auth",
            "client_id": "chatgpt-test-client",
            "redirect_uri": "https://chatgpt.com/callback",
            "chatgpt_state": None,
            "expires": datetime.now(UTC) + timedelta(minutes=10),
        }

        resp = client.get(
            "/oauth/pco-callback",
            params={"code": "pco-code", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        location = resp.headers["location"]
        assert "state=" not in location

    @patch("pco_mcp.main.get_pco_me", new_callable=AsyncMock)
    @patch("pco_mcp.main.exchange_pco_code", new_callable=AsyncMock)
    def test_callback_pco_me_failure_still_works(
        self, mock_exchange, mock_me, client
    ) -> None:
        """If get_pco_me fails, the flow still completes with empty me data."""
        from pco_mcp.main import oauth_codes

        mock_exchange.return_value = {"access_token": "pco-tok"}
        mock_me.side_effect = Exception("PCO /me failed")

        state = "me-failure-state"
        oauth_codes[state] = {
            "type": "pending_pco_auth",
            "client_id": "chatgpt-test-client",
            "redirect_uri": "https://chatgpt.com/callback",
            "chatgpt_state": "s1",
            "expires": datetime.now(UTC) + timedelta(minutes=10),
        }

        resp = client.get(
            "/oauth/pco-callback",
            params={"code": "pco-code", "state": state},
            follow_redirects=False,
        )
        assert resp.status_code == 302


# =========================================================================
# Security Headers
# =========================================================================


class TestSecurityHeaders:
    def test_responses_have_security_headers(self, client) -> None:
        resp = client.get("/health")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


# =========================================================================
# Fix C2: redirect_uri validation
# =========================================================================


class TestRedirectUriValidation:
    def test_authorize_rejects_unregistered_redirect_uri(self, client) -> None:
        reg = _register_client(client)  # registered with https://example.com/cb
        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": reg["client_id"],
                "redirect_uri": "https://evil.com/cb",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 400
        assert "redirect_uri not registered" in resp.json()["detail"]

    def test_authorize_allows_registered_redirect_uri(self, client) -> None:
        reg = _register_client(client)
        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": reg["client_id"],
                "redirect_uri": "https://example.com/cb",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302

    def test_authorize_allows_any_uri_when_none_registered(self, client) -> None:
        """Clients with no registered redirect_uris allow any URI."""
        resp = client.post("/oauth/register", json={"redirect_uris": []})
        reg = resp.json()
        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": reg["client_id"],
                "redirect_uri": "https://anything.com/cb",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302


# =========================================================================
# Fix C4: auth code bound to client_id
# =========================================================================


class TestAuthCodeClientBinding:
    def test_token_rejects_code_for_different_client(self, client) -> None:
        reg1 = _register_client(client)
        reg2 = _register_client(client)
        code = _seed_auth_code(reg1["client_id"])  # bound to reg1

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg2["client_id"],  # wrong client
                "client_secret": reg2["client_secret"],
                "code": code,
            },
        )
        assert resp.status_code == 400
        assert "not issued to this client" in resp.json()["detail"]

    def test_token_accepts_code_for_correct_client(self, client) -> None:
        reg = _register_client(client)
        code = _seed_auth_code(reg["client_id"])

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "code": code,
            },
        )
        assert resp.status_code == 200


# =========================================================================
# Fix I1: PKCE verification
# =========================================================================


def _pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


class TestPKCE:
    def test_pkce_valid_verifier_succeeds(self, client) -> None:
        from pco_mcp.main import oauth_codes

        reg = _register_client(client)
        verifier, challenge = _pkce_pair()

        code = secrets.token_urlsafe(32)
        oauth_codes[code] = {
            "type": "auth_code",
            "client_id": reg["client_id"],
            "pco_access_token": "pco-test-token",
            "pco_refresh_token": "pco-test-refresh",
            "pco_me": {"id": 99},
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "expires": datetime.now(UTC) + timedelta(minutes=10),
        }

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "code": code,
                "code_verifier": verifier,
            },
        )
        assert resp.status_code == 200

    def test_pkce_missing_verifier_fails(self, client) -> None:
        from pco_mcp.main import oauth_codes

        reg = _register_client(client)
        _, challenge = _pkce_pair()

        code = secrets.token_urlsafe(32)
        oauth_codes[code] = {
            "type": "auth_code",
            "client_id": reg["client_id"],
            "pco_access_token": "pco-test-token",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "expires": datetime.now(UTC) + timedelta(minutes=10),
        }

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "code": code,
                # no code_verifier
            },
        )
        assert resp.status_code == 400
        assert "code_verifier required" in resp.json()["detail"]

    def test_pkce_wrong_verifier_fails(self, client) -> None:
        from pco_mcp.main import oauth_codes

        reg = _register_client(client)
        _, challenge = _pkce_pair()

        code = secrets.token_urlsafe(32)
        oauth_codes[code] = {
            "type": "auth_code",
            "client_id": reg["client_id"],
            "pco_access_token": "pco-test-token",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "expires": datetime.now(UTC) + timedelta(minutes=10),
        }

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "code": code,
                "code_verifier": "wrong-verifier-value",
            },
        )
        assert resp.status_code == 400
        assert "Invalid code_verifier" in resp.json()["detail"]

    def test_no_pkce_challenge_skips_verification(self, client) -> None:
        """When no code_challenge was stored, PKCE is not enforced."""
        reg = _register_client(client)
        code = _seed_auth_code(reg["client_id"])  # no code_challenge

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
                "code": code,
            },
        )
        assert resp.status_code == 200


# =========================================================================
# Fix I2: explicit 401 on expired bearer tokens
# =========================================================================


class TestExpiredBearerToken:
    def test_expired_bearer_returns_401(self, client) -> None:
        from pco_mcp.main import oauth_tokens

        expired_token = secrets.token_urlsafe(32)
        oauth_tokens[expired_token] = {
            "pco_access_token": "pco-tok",
            "pco_me": {"id": 1},
            "expires": datetime.now(UTC) - timedelta(hours=1),
        }

        resp = client.get(
            "/health",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401
        assert "expired" in resp.json()["error"].lower()

    def test_valid_bearer_passes_through(self, client) -> None:
        from pco_mcp.main import oauth_tokens

        valid_token = secrets.token_urlsafe(32)
        oauth_tokens[valid_token] = {
            "pco_access_token": "pco-tok",
            "pco_me": {"id": 1},
            "expires": datetime.now(UTC) + timedelta(hours=1),
        }

        resp = client.get(
            "/health",
            headers={"Authorization": f"Bearer {valid_token}"},
        )
        assert resp.status_code == 200


# =========================================================================
# Fix I3: client_credentials rejected
# =========================================================================


class TestClientCredentialsRejected:
    def test_client_credentials_returns_400_with_message(self, client) -> None:
        reg = _register_client(client)
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": reg["client_id"],
                "client_secret": reg["client_secret"],
            },
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "client_credentials" in detail
        assert "authorization_code" in detail.lower() or "Use authorization_code" in detail

    def test_discovery_still_lists_client_credentials(self, client) -> None:
        """Keep in metadata for ChatGPT compatibility."""
        resp = client.get("/.well-known/oauth-authorization-server")
        body = resp.json()
        assert "client_credentials" in body["grant_types_supported"]
