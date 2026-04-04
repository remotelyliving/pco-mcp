import httpx
import pytest

from pco_mcp.oauth.pco_client import exchange_pco_code, get_pco_me, refresh_pco_token


class TestExchangePCOCode:
    async def test_exchanges_code_for_tokens(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json={
                    "access_token": "pco-access-123",
                    "refresh_token": "pco-refresh-456",
                    "expires_in": 7200,
                    "token_type": "Bearer",
                },
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await exchange_pco_code(
                code="auth-code-789",
                client_id="test-client",
                client_secret="test-secret",
                redirect_uri="https://example.com/callback",
                http_client=client,
            )
        assert result["access_token"] == "pco-access-123"
        assert result["refresh_token"] == "pco-refresh-456"

    async def test_raises_on_error_response(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(400, json={"error": "invalid_grant"})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(Exception):
                await exchange_pco_code(
                    code="bad-code",
                    client_id="test-client",
                    client_secret="test-secret",
                    redirect_uri="https://example.com/callback",
                    http_client=client,
                )


class TestGetPCOMe:
    async def test_returns_user_info(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json={
                    "data": {
                        "id": "12345",
                        "attributes": {
                            "first_name": "Alice",
                            "last_name": "Smith",
                        },
                    },
                    "meta": {
                        "parent": {
                            "id": "org-1",
                            "attributes": {"name": "First Church"},
                        }
                    },
                },
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await get_pco_me("pco-token", http_client=client)
        assert result["id"] == 12345
        assert result["org_name"] == "First Church"


class TestRefreshPCOToken:
    async def test_refreshes_token(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "expires_in": 7200,
                },
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await refresh_pco_token(
                refresh_token="old-refresh",
                client_id="test-client",
                client_secret="test-secret",
                http_client=client,
            )
        assert result["access_token"] == "new-access"
