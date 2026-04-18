"""Targeted tests to boost coverage to 90%+.

Covers uncovered lines in:
- pco/client.py (lines 41, 46, 89->99, 97, 107-113, 133-135)
- oauth/pco_client.py (lines 40, 55-56, 70, 92, 97)
- main.py (lines for health check DB error)
- auth.py (PCOTokenVerifier and PCOProvider)
- tools/_context.py (get_pco_client with no token)
"""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pco_mcp.oauth.pco_client import exchange_pco_code, get_pco_me, refresh_pco_token
from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.people import PeopleAPI


# ---------------------------------------------------------------------------
# pco/client.py — close() (line 41)
# ---------------------------------------------------------------------------


class TestPCOClientClose:
    @pytest.mark.asyncio
    async def test_close_closes_underlying_client(self) -> None:
        client = PCOClient(
            base_url="https://api.planningcenteronline.com",
            access_token="tok",
        )
        mock_aclose = AsyncMock()
        client._client = MagicMock()
        client._client.aclose = mock_aclose
        await client.close()
        mock_aclose.assert_awaited_once()


# ---------------------------------------------------------------------------
# pco/client.py — _url with absolute URL (line 46)
# ---------------------------------------------------------------------------


class TestPCOClientUrl:
    def test_url_passes_through_absolute_http_url(self) -> None:
        client = PCOClient(base_url="https://api.planningcenteronline.com", access_token="t")
        assert client._url("http://other.example.com/path") == "http://other.example.com/path"

    def test_url_passes_through_absolute_https_url(self) -> None:
        client = PCOClient(base_url="https://api.planningcenteronline.com", access_token="t")
        assert client._url("https://other.example.com/path") == "https://other.example.com/path"


# ---------------------------------------------------------------------------
# pco/client.py — get_all max_pages limit (lines 89->99 / line 97)
# ---------------------------------------------------------------------------


class TestPCOClientGetAllMaxPages:
    @pytest.mark.asyncio
    async def test_get_all_stops_at_max_pages(self) -> None:
        """get_all should stop after max_pages even if next links remain."""
        call_count = 0

        def always_next(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json={
                    "data": [{"id": str(call_count)}],
                    "meta": {"next": {"offset": call_count}},
                    "links": {"next": f"https://api.planningcenteronline.com/people?offset={call_count}"},
                },
            )

        client = PCOClient(base_url="https://api.planningcenteronline.com", access_token="t")
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(always_next))
        results = await client.get_all("/people/v2/people", max_pages=3)
        assert len(results) == 3
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_get_all_stops_when_no_next_offset(self) -> None:
        """get_all stops when next link exists but no offset in meta."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json={
                    "data": [{"id": "1"}],
                    "meta": {},
                    "links": {"next": "https://api.planningcenteronline.com/people?offset=1"},
                },
            )

        client = PCOClient(base_url="https://api.planningcenteronline.com", access_token="t")
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        results = await client.get_all("/people/v2/people")
        assert len(results) == 1
        assert call_count == 1


# ---------------------------------------------------------------------------
# pco/client.py — rate limit warning (lines 107-113)
# ---------------------------------------------------------------------------


class TestPCOClientRateLimitWarning:
    @pytest.mark.asyncio
    async def test_low_rate_limit_remaining_logs_warning(self) -> None:
        client = PCOClient(base_url="https://api.planningcenteronline.com", access_token="t")
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(
                    200,
                    json={"data": []},
                    headers={"X-RateLimit-Remaining": "5"},
                )
            )
        )
        with patch("pco_mcp.pco.client.logger") as mock_logger:
            await client.get("/people/v2/people")
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_rate_limit_remaining_does_not_raise(self) -> None:
        client = PCOClient(base_url="https://api.planningcenteronline.com", access_token="t")
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(
                    200,
                    json={"data": []},
                    headers={"X-RateLimit-Remaining": "not-a-number"},
                )
            )
        )
        result = await client.get("/people/v2/people")
        assert result == {"data": []}


# ---------------------------------------------------------------------------
# pco/client.py — _extract_error_detail with non-JSON body (lines 133-135)
# ---------------------------------------------------------------------------


class TestPCOClientExtractErrorDetail:
    @pytest.mark.asyncio
    async def test_non_json_error_response_returns_http_status(self) -> None:
        client = PCOClient(base_url="https://api.planningcenteronline.com", access_token="t")
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(500, content=b"Internal Server Error")
            )
        )
        from pco_mcp.pco.client import PCOAPIError

        with pytest.raises(PCOAPIError) as exc_info:
            await client.get("/people/v2/people")
        assert "500" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_json_error_with_no_errors_key_returns_http_status(self) -> None:
        client = PCOClient(base_url="https://api.planningcenteronline.com", access_token="t")
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(503, json={"message": "service unavailable"})
            )
        )
        from pco_mcp.pco.client import PCOAPIError

        with pytest.raises(PCOAPIError) as exc_info:
            await client.get("/people/v2/people")
        assert "503" in exc_info.value.detail


# ---------------------------------------------------------------------------
# oauth/pco_client.py — without http_client (auto-close paths)
# ---------------------------------------------------------------------------


class TestOAuthPcoClientAutoClose:
    @pytest.mark.asyncio
    async def test_exchange_pco_code_creates_and_closes_client(self) -> None:
        with patch("httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(
                return_value=MagicMock(
                    is_success=True,
                    json=MagicMock(return_value={"access_token": "tok"}),
                )
            )
            mock_cls.return_value = mock_instance

            result = await exchange_pco_code(
                code="c",
                client_id="id",
                client_secret="secret",
                redirect_uri="https://example.com/cb",
            )

        mock_instance.aclose.assert_awaited_once()
        assert result["access_token"] == "tok"

    @pytest.mark.asyncio
    async def test_get_pco_me_creates_and_closes_client(self) -> None:
        with patch("httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.get = AsyncMock(
                return_value=MagicMock(
                    is_success=True,
                    json=MagicMock(
                        return_value={
                            "data": {
                                "id": "42",
                                "attributes": {"first_name": "Alice", "last_name": "Smith"},
                            },
                            "meta": {"parent": {"attributes": {"name": "Church"}}},
                        }
                    ),
                )
            )
            mock_cls.return_value = mock_instance

            result = await get_pco_me("access-token")

        mock_instance.aclose.assert_awaited_once()
        assert result["id"] == 42

    @pytest.mark.asyncio
    async def test_refresh_pco_token_creates_and_closes_client(self) -> None:
        with patch("httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_instance.post = AsyncMock(
                return_value=MagicMock(
                    is_success=True,
                    json=MagicMock(return_value={"access_token": "new-tok"}),
                )
            )
            mock_cls.return_value = mock_instance

            result = await refresh_pco_token(
                refresh_token="rt", client_id="id", client_secret="secret"
            )

        mock_instance.aclose.assert_awaited_once()
        assert result["access_token"] == "new-tok"


# ---------------------------------------------------------------------------
# oauth/pco_client.py — error paths
# ---------------------------------------------------------------------------


class TestOAuthPcoClientErrors:
    @pytest.mark.asyncio
    async def test_get_pco_me_raises_on_error_response(self) -> None:
        transport = httpx.MockTransport(lambda req: httpx.Response(401, json={"error": "unauth"}))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(Exception, match="PCO /me request failed"):
                await get_pco_me("bad-token", http_client=client)

    @pytest.mark.asyncio
    async def test_refresh_pco_token_raises_on_error_response(self) -> None:
        transport = httpx.MockTransport(lambda req: httpx.Response(400, json={"error": "invalid"}))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(Exception, match="PCO token refresh failed"):
                await refresh_pco_token(
                    refresh_token="bad-rt",
                    client_id="id",
                    client_secret="secret",
                    http_client=client,
                )


# ---------------------------------------------------------------------------
# main.py — health check DB error
# ---------------------------------------------------------------------------


class TestMainHealthDBError:
    def test_health_returns_503_on_db_error(self) -> None:
        from fastapi.testclient import TestClient

        from pco_mcp.main import create_app

        app = create_app()

        with TestClient(app) as client:
            with patch("pco_mcp.main.text", side_effect=Exception("db down")):
                resp = client.get("/health")

        assert resp.status_code == 503
        assert resp.json()["status"] == "unhealthy"


# ---------------------------------------------------------------------------
# pco/people.py — both email and phone warning
# ---------------------------------------------------------------------------


class TestPeopleAPIEmailAndPhoneWarning:
    @pytest.mark.asyncio
    async def test_search_people_warns_when_email_and_phone_both_provided(self) -> None:
        from pco_mcp.pco.client import PagedResult

        mock_client = AsyncMock(spec=PCOClient)
        mock_client.get_all = AsyncMock(
            return_value=PagedResult(items=[], total_count=0, truncated=False)
        )
        api = PeopleAPI(mock_client)

        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = await api.search_people(email="a@b.com", phone="555-1234")

        assert any("email" in str(w.message).lower() for w in caught)
        assert result["items"] == []
        assert result["meta"]["total_count"] == 0


# ---------------------------------------------------------------------------
# tools/people.py — update_person with email field
# ---------------------------------------------------------------------------


class TestToolsPeopleUpdatePersonEmail:
    @pytest.mark.asyncio
    async def test_update_person_passes_email_field(self) -> None:
        from pco_mcp.pco.people import PeopleAPI

        mock_client = AsyncMock(spec=PCOClient)
        mock_client.patch = AsyncMock(
            return_value={
                "data": {
                    "id": "42",
                    "attributes": {
                        "first_name": "Alice",
                        "last_name": "Smith",
                        "email_addresses": [],
                        "phone_numbers": [],
                    },
                }
            }
        )
        api = PeopleAPI(mock_client)
        result = await api.update_person("42", email="newemail@example.com")

        mock_client.patch.assert_awaited_once()
        call_kwargs = mock_client.patch.call_args
        payload = call_kwargs[1]["data"] if "data" in call_kwargs[1] else call_kwargs[0][1]
        assert "email" in payload["data"]["attributes"]
        assert result["id"] == "42"


# ---------------------------------------------------------------------------
# auth.py — inject_pco_bearer middleware tests
# ---------------------------------------------------------------------------


class TestInjectPcoBearerMiddleware:
    @pytest.mark.asyncio
    async def test_injects_user_when_valid_bearer(self) -> None:
        from datetime import UTC, datetime, timedelta

        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient

        from pco_mcp.auth import inject_pco_bearer

        tokens = {
            "valid-tok": {
                "pco_access_token": "pco-abc",
                "pco_me": {"id": 42},
                "expires": datetime.now(UTC) + timedelta(hours=1),
            }
        }

        app = FastAPI()

        @app.middleware("http")
        async def mw(request: Request, call_next):
            return await inject_pco_bearer(request, call_next, tokens)

        @app.get("/check")
        async def check(request: Request):
            user = request.scope.get("user")
            if user and hasattr(user, "access_token"):
                return {"token": user.access_token.token}
            return {"token": None}

        with TestClient(app) as client:
            resp = client.get("/check", headers={"Authorization": "Bearer valid-tok"})
        assert resp.json()["token"] == "pco-abc"

    @pytest.mark.asyncio
    async def test_no_user_when_no_bearer(self) -> None:
        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient

        from pco_mcp.auth import inject_pco_bearer

        app = FastAPI()

        @app.middleware("http")
        async def mw(request: Request, call_next):
            return await inject_pco_bearer(request, call_next, {})

        @app.get("/check")
        async def check(request: Request):
            user = request.scope.get("user")
            return {"has_user": user is not None}

        with TestClient(app) as client:
            resp = client.get("/check")
        assert resp.json()["has_user"] is False

    @pytest.mark.asyncio
    async def test_expired_token_not_injected(self) -> None:
        from datetime import UTC, datetime, timedelta

        from fastapi import FastAPI, Request
        from fastapi.testclient import TestClient

        from pco_mcp.auth import inject_pco_bearer

        tokens = {
            "expired-tok": {
                "pco_access_token": "pco-abc",
                "pco_me": {"id": 42},
                "expires": datetime.now(UTC) - timedelta(hours=1),
            }
        }

        app = FastAPI()

        @app.middleware("http")
        async def mw(request: Request, call_next):
            return await inject_pco_bearer(request, call_next, tokens)

        @app.get("/check")
        async def check(request: Request):
            user = request.scope.get("user")
            return {"has_user": user is not None}

        with TestClient(app) as client:
            resp = client.get("/check", headers={"Authorization": "Bearer expired-tok"})
        # Expired tokens now return an explicit 401 instead of silently passing through
        assert resp.status_code == 401
        assert "expired" in resp.json()["error"].lower()


# ---------------------------------------------------------------------------
# oauth/provider.py — dashboard flow helpers
# ---------------------------------------------------------------------------


class TestOAuthProviderHelpers:
    def test_create_direct_auth_state(self) -> None:
        from pco_mcp.oauth.provider import create_direct_auth_state

        codes: dict = {}
        url = create_direct_auth_state(
            pco_client_id="test-id",
            base_url="https://pco-mcp.test",
            oauth_codes=codes,
        )
        assert "api.planningcenteronline.com/oauth/authorize" in url
        assert "client_id=test-id" in url
        assert "state=" in url
        assert len(codes) == 1

    def test_redeem_dashboard_token_valid(self) -> None:
        from pco_mcp.oauth.provider import (
            _pending_dashboard_tokens,
            redeem_dashboard_token,
            store_dashboard_token,
        )

        store_dashboard_token("tok123", {
            "user_id": "abc",
            "org_name": "Church",
        })
        result = redeem_dashboard_token("tok123")
        assert result is not None
        assert result["org_name"] == "Church"

    def test_redeem_dashboard_token_invalid(self) -> None:
        from pco_mcp.oauth.provider import redeem_dashboard_token

        result = redeem_dashboard_token("nonexistent")
        assert result is None

    def test_redeem_dashboard_token_wrong_type(self) -> None:
        from pco_mcp.oauth.provider import (
            _pending_dashboard_tokens,
            redeem_dashboard_token,
        )

        _pending_dashboard_tokens["tok456"] = {
            "flow": "direct",
        }
        result = redeem_dashboard_token("tok456")
        assert result is None
