"""Tests for CORS headers and RFC 7591 public client registration flow."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from pco_mcp.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


class TestCORS:
    """ChatGPT and Claude.ai run in the browser — CORS must allow them."""

    def test_preflight_to_register_is_allowed(self, client: TestClient) -> None:
        resp = client.options(
            "/oauth/register",
            headers={
                "Origin": "https://chatgpt.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert resp.status_code in (200, 204)
        assert resp.headers.get("access-control-allow-origin") in ("https://chatgpt.com", "*")
        assert "POST" in resp.headers.get("access-control-allow-methods", "")

    def test_preflight_to_metadata_is_allowed(self, client: TestClient) -> None:
        resp = client.options(
            "/.well-known/oauth-authorization-server",
            headers={
                "Origin": "https://chatgpt.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code in (200, 204)
        assert resp.headers.get("access-control-allow-origin") in ("https://chatgpt.com", "*")

    def test_actual_post_to_register_has_cors_origin(self, client: TestClient) -> None:
        resp = client.post(
            "/oauth/register",
            json={"redirect_uris": ["https://chatgpt.com/callback"]},
            headers={"Origin": "https://chatgpt.com"},
        )
        assert resp.status_code == 201
        assert resp.headers.get("access-control-allow-origin") in ("https://chatgpt.com", "*")

    def test_www_authenticate_header_exposed(self, client: TestClient) -> None:
        # Expose-headers are added to actual responses (not preflight) by
        # Starlette's CORSMiddleware. Make a real cross-origin request to /mcp/
        # to verify WWW-Authenticate is exposed to browser JS.
        resp = client.post(
            "/mcp/",
            headers={
                "Origin": "https://chatgpt.com",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
            content=b'{}',
        )
        # 401 from the middleware
        assert resp.status_code == 401
        exposed = resp.headers.get("access-control-expose-headers", "")
        assert "www-authenticate" in exposed.lower()
        # And the actual WWW-Authenticate header should be there
        assert "Bearer" in resp.headers.get("www-authenticate", "")


class TestPublicClientRegistration:
    """RFC 7591: public clients (auth_method=none) don't receive client_secret."""

    def test_public_client_no_secret_issued(self, client: TestClient) -> None:
        resp = client.post(
            "/oauth/register",
            json={
                "redirect_uris": ["https://chatgpt.com/callback"],
                "token_endpoint_auth_method": "none",
                "client_name": "ChatGPT",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "client_secret" not in body
        assert "client_secret_expires_at" not in body
        assert body["token_endpoint_auth_method"] == "none"
        assert body["client_id"]

    def test_confidential_client_gets_secret(self, client: TestClient) -> None:
        resp = client.post(
            "/oauth/register",
            json={
                "redirect_uris": ["https://example.com/callback"],
                "token_endpoint_auth_method": "client_secret_post",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["client_secret"]
        assert body["client_secret_expires_at"] == 0
        assert body["token_endpoint_auth_method"] == "client_secret_post"

    def test_default_auth_method_when_unspecified(self, client: TestClient) -> None:
        resp = client.post(
            "/oauth/register",
            json={"redirect_uris": ["https://example.com/callback"]},
        )
        assert resp.status_code == 201
        body = resp.json()
        # Default is confidential with client_secret_post
        assert body["client_secret"]
        assert body["token_endpoint_auth_method"] == "client_secret_post"

    def test_unsupported_auth_method_falls_back(self, client: TestClient) -> None:
        resp = client.post(
            "/oauth/register",
            json={
                "redirect_uris": ["https://example.com/callback"],
                "token_endpoint_auth_method": "private_key_jwt",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["token_endpoint_auth_method"] == "client_secret_post"

    def test_rfc7591_required_response_fields(self, client: TestClient) -> None:
        resp = client.post(
            "/oauth/register",
            json={"redirect_uris": ["https://example.com/callback"]},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "client_id" in body
        assert "client_id_issued_at" in body
        assert "redirect_uris" in body
        assert "grant_types" in body
        assert "response_types" in body
        assert "token_endpoint_auth_method" in body


class TestPublicClientTokenFlow:
    """Public clients exchange auth codes without a client_secret."""

    def test_public_client_can_exchange_code_without_secret(
        self, client: TestClient
    ) -> None:
        # Register a public client
        reg = client.post(
            "/oauth/register",
            json={
                "redirect_uris": ["https://chatgpt.com/callback"],
                "token_endpoint_auth_method": "none",
            },
        ).json()
        client_id = reg["client_id"]

        # Try to exchange a (fake) auth code without client_secret
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": "invalid-but-well-formed",
                "redirect_uri": "https://chatgpt.com/callback",
                "client_id": client_id,
                # No client_secret — this is the public client flow
            },
        )
        # Should fail with 400 (invalid code), NOT 401 (invalid client_secret)
        # The important thing: we got past the client auth check.
        assert resp.status_code == 400

    def test_confidential_client_rejected_without_secret(
        self, client: TestClient
    ) -> None:
        reg = client.post(
            "/oauth/register",
            json={
                "redirect_uris": ["https://example.com/callback"],
                "token_endpoint_auth_method": "client_secret_post",
            },
        ).json()
        client_id = reg["client_id"]

        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": "any-code",
                "redirect_uri": "https://example.com/callback",
                "client_id": client_id,
                "client_secret": "wrong-secret",
            },
        )
        assert resp.status_code == 401
