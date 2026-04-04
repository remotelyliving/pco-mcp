"""Targeted tests to boost coverage to 90%+.

Covers uncovered lines in:
- middleware.py (lines 26-31, 62-63, 99->95, 115-127, 133-158, 162-168)
- pco/client.py (lines 41, 46, 89->99, 97, 107-113, 133-135)
- oauth/pco_client.py (lines 40, 55-56, 70, 92, 97)
- main.py (lines 62, 71-72)
- oauth/provider.py (lines 195-202)
- pco/people.py (lines 23-24)
- tools/people.py (line 97)
"""
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from pco_mcp.crypto import encrypt_token
from pco_mcp.middleware import BearerTokenMiddleware, _json_error
from pco_mcp.models import Base, OAuthSession, User
from pco_mcp.oauth.pco_client import exchange_pco_code, get_pco_me, refresh_pco_token
from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.people import PeopleAPI


# ---------------------------------------------------------------------------
# middleware.py — _json_error helper (lines 26-31)
# ---------------------------------------------------------------------------


class TestJsonErrorHelper:
    def test_json_error_returns_correct_status(self) -> None:
        status, headers, body = _json_error(401, "Unauthorized")
        assert status == 401

    def test_json_error_returns_json_content_type(self) -> None:
        status, headers, body = _json_error(403, "Forbidden")
        header_dict = dict(headers)
        assert header_dict[b"content-type"] == b"application/json"

    def test_json_error_body_contains_error_key(self) -> None:
        import json

        status, headers, body = _json_error(500, "Internal error")
        parsed = json.loads(body)
        assert parsed["error"] == "Internal error"

    def test_json_error_content_length_matches_body(self) -> None:
        status, headers, body = _json_error(404, "Not found")
        header_dict = dict(headers)
        assert int(header_dict[b"content-length"]) == len(body)


# ---------------------------------------------------------------------------
# middleware.py — non-HTTP scope passthrough (lines 62-63)
# ---------------------------------------------------------------------------


class TestMiddlewareNonHttpScope:
    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self) -> None:
        """WebSocket (or lifespan) scopes should bypass auth entirely."""
        inner_called = []

        async def inner_app(scope, receive, send):
            inner_called.append(scope["type"])

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        mw = BearerTokenMiddleware(
            inner_app,
            session_factory=factory,
            token_encryption_key="JyU3hqD0bM06X5j88vekTdYHJJb5LxI1YWR0f55cw-c=",
            pco_client_id="cid",
            pco_client_secret="csecret",
        )
        await mw({"type": "websocket", "path": "/mcp/messages"}, None, None)
        assert inner_called == ["websocket"]
        await engine.dispose()


# ---------------------------------------------------------------------------
# middleware.py — missing user record (line 135-137)
# ---------------------------------------------------------------------------


class TestMiddlewareMissingUser:
    @pytest.mark.asyncio
    async def test_missing_user_returns_401(self) -> None:
        """OAuth session exists but its user_id doesn't match any User row."""
        from httpx import ASGITransport, AsyncClient
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route

        ENCRYPTION_KEY = "JyU3hqD0bM06X5j88vekTdYHJJb5LxI1YWR0f55cw-c="
        TOKEN = "bearer-orphan-session"
        TOKEN_HASH = hashlib.sha256(TOKEN.encode()).hexdigest()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        # Insert an OAuthSession that points to a non-existent user
        nonexistent_user_id = uuid.uuid4()
        orphan_session = OAuthSession(
            id=uuid.uuid4(),
            user_id=nonexistent_user_id,
            chatgpt_access_token_hash=TOKEN_HASH,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        async with factory() as db:
            db.add(orphan_session)
            await db.commit()

        async def handler(request):
            return PlainTextResponse("ok")

        backend = Starlette(routes=[Route("/mcp/test", handler)])
        mw = BearerTokenMiddleware(
            backend,
            session_factory=factory,
            token_encryption_key=ENCRYPTION_KEY,
            pco_client_id="cid",
            pco_client_secret="csecret",
            mcp_path_prefix="/mcp",
        )

        async with AsyncClient(transport=ASGITransport(app=mw), base_url="http://test") as client:
            resp = await client.get("/mcp/test", headers={"Authorization": f"Bearer {TOKEN}"})

        assert resp.status_code == 401
        assert "not found" in resp.json()["error"].lower()
        await engine.dispose()


# ---------------------------------------------------------------------------
# middleware.py — PCO token refresh failure (lines 162-168)
# ---------------------------------------------------------------------------


class TestMiddlewareRefreshFailure:
    @pytest.mark.asyncio
    async def test_refresh_failure_returns_401(self) -> None:
        from httpx import ASGITransport, AsyncClient
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route

        ENCRYPTION_KEY = "JyU3hqD0bM06X5j88vekTdYHJJb5LxI1YWR0f55cw-c="
        TOKEN = "bearer-refresh-fail"
        TOKEN_HASH = hashlib.sha256(TOKEN.encode()).hexdigest()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        near_expiry = datetime.now(UTC) + timedelta(minutes=1)  # within 5-minute buffer
        user = User(
            id=uuid.uuid4(),
            pco_person_id=999,
            pco_org_name="Fail Church",
            pco_access_token_enc=encrypt_token("old-access", ENCRYPTION_KEY),
            pco_refresh_token_enc=encrypt_token("old-refresh", ENCRYPTION_KEY),
            pco_token_expires_at=near_expiry,
        )
        session_row = OAuthSession(
            id=uuid.uuid4(),
            user_id=user.id,
            chatgpt_access_token_hash=TOKEN_HASH,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        async with factory() as db:
            db.add(user)
            db.add(session_row)
            await db.commit()

        async def handler(request):
            return PlainTextResponse("ok")

        backend = Starlette(routes=[Route("/mcp/test", handler)])
        mw = BearerTokenMiddleware(
            backend,
            session_factory=factory,
            token_encryption_key=ENCRYPTION_KEY,
            pco_client_id="cid",
            pco_client_secret="csecret",
            mcp_path_prefix="/mcp",
        )

        with patch(
            "pco_mcp.middleware.refresh_pco_token",
            new=AsyncMock(side_effect=RuntimeError("network error")),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=mw), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/mcp/test", headers={"Authorization": f"Bearer {TOKEN}"}
                )

        assert resp.status_code == 401
        assert "refresh" in resp.json()["error"].lower() or "reconnect" in resp.json()["error"].lower()
        await engine.dispose()


# ---------------------------------------------------------------------------
# middleware.py — token refresh without new refresh_token in response (line 153)
# ---------------------------------------------------------------------------


class TestMiddlewareRefreshNoNewRefreshToken:
    @pytest.mark.asyncio
    async def test_refresh_uses_old_refresh_token_when_not_returned(self) -> None:
        from httpx import ASGITransport, AsyncClient
        from starlette.applications import Starlette
        from starlette.responses import PlainTextResponse
        from starlette.routing import Route

        ENCRYPTION_KEY = "JyU3hqD0bM06X5j88vekTdYHJJb5LxI1YWR0f55cw-c="
        TOKEN = "bearer-no-new-refresh"
        TOKEN_HASH = hashlib.sha256(TOKEN.encode()).hexdigest()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        near_expiry = datetime.now(UTC) + timedelta(minutes=1)
        user = User(
            id=uuid.uuid4(),
            pco_person_id=777,
            pco_org_name="No New Refresh Church",
            pco_access_token_enc=encrypt_token("old-access", ENCRYPTION_KEY),
            pco_refresh_token_enc=encrypt_token("old-refresh", ENCRYPTION_KEY),
            pco_token_expires_at=near_expiry,
        )
        session_row = OAuthSession(
            id=uuid.uuid4(),
            user_id=user.id,
            chatgpt_access_token_hash=TOKEN_HASH,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        async with factory() as db:
            db.add(user)
            db.add(session_row)
            await db.commit()

        # Response without refresh_token — exercises the .get("refresh_token", refresh_token) fallback
        new_token_data = {"access_token": "new-access-token"}  # no refresh_token key

        async def handler(request):
            return PlainTextResponse("ok")

        backend = Starlette(routes=[Route("/mcp/test", handler)])
        mw = BearerTokenMiddleware(
            backend,
            session_factory=factory,
            token_encryption_key=ENCRYPTION_KEY,
            pco_client_id="cid",
            pco_client_secret="csecret",
            mcp_path_prefix="/mcp",
        )

        with (
            patch(
                "pco_mcp.middleware.refresh_pco_token",
                new=AsyncMock(return_value=new_token_data),
            ),
            patch("pco_mcp.middleware.set_pco_client"),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=mw), base_url="http://test"
            ) as client:
                resp = await client.get(
                    "/mcp/test", headers={"Authorization": f"Bearer {TOKEN}"}
                )

        assert resp.status_code == 200
        await engine.dispose()


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
            # Has next link but no meta.next.offset
            return httpx.Response(
                200,
                json={
                    "data": [{"id": "1"}],
                    "meta": {},  # no "next" key
                    "links": {"next": "https://api.planningcenteronline.com/people?offset=1"},
                },
            )

        client = PCOClient(base_url="https://api.planningcenteronline.com", access_token="t")
        client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        results = await client.get_all("/people/v2/people")
        # Should stop after 1 page since next_offset is None
        assert len(results) == 1
        assert call_count == 1


# ---------------------------------------------------------------------------
# pco/client.py — rate limit warning (lines 107-113)
# ---------------------------------------------------------------------------


class TestPCOClientRateLimitWarning:
    @pytest.mark.asyncio
    async def test_low_rate_limit_remaining_logs_warning(self) -> None:
        """X-RateLimit-Remaining < 10 should trigger a warning log."""
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
        import logging

        with patch("pco_mcp.pco.client.logger") as mock_logger:
            await client.get("/people/v2/people")
            mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_rate_limit_remaining_does_not_raise(self) -> None:
        """Non-integer X-RateLimit-Remaining should be silently ignored."""
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
        # Should not raise
        result = await client.get("/people/v2/people")
        assert result == {"data": []}


# ---------------------------------------------------------------------------
# pco/client.py — _extract_error_detail with non-JSON body (lines 133-135)
# ---------------------------------------------------------------------------


class TestPCOClientExtractErrorDetail:
    @pytest.mark.asyncio
    async def test_non_json_error_response_returns_http_status(self) -> None:
        """When the error body isn't JSON, detail should be 'HTTP <status>'."""
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
        """JSON body with no 'errors' key should fall through to 'HTTP <status>'."""
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
# oauth/pco_client.py — without http_client (auto-close paths, lines 39-40, 69-70, 96-97)
# ---------------------------------------------------------------------------


class TestOAuthPcoClientAutoClose:
    @pytest.mark.asyncio
    async def test_exchange_pco_code_creates_and_closes_client(self) -> None:
        """When no http_client is passed, a new client is created and closed."""
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
        """When no http_client is passed to get_pco_me, a new client is created and closed."""
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
        """When no http_client is passed to refresh_pco_token, a new client is created and closed."""
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
# oauth/pco_client.py — error paths (lines 55-56, 92)
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
# main.py — health check DB error (lines 71-72)
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
# oauth/provider.py — direct flow callback (lines 195-202)
# ---------------------------------------------------------------------------


class TestOAuthProviderDirectFlow:
    def test_callback_direct_flow_redirects_to_dashboard(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from pco_mcp.oauth.provider import (
            _pending_auth_codes,
            _registered_clients,
            create_oauth_router,
        )

        _pending_auth_codes.clear()
        _registered_clients.clear()

        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        factory = MagicMock(return_value=session)

        FERNET_KEY = "qf3WS_ifAWXQ6Pve5_lRuNIcyDstvOGlYN8EvHSfAzE="

        app = FastAPI()
        router = create_oauth_router(
            session_factory=factory,
            pco_client_id="test-pco-client",
            pco_client_secret="test-pco-secret",
            base_url="https://pco-mcp.example.com",
            token_encryption_key=FERNET_KEY,
        )
        app.include_router(router, prefix="/oauth")
        client = TestClient(app, raise_server_exceptions=True)

        # Pre-populate a pending state for the "direct" flow
        internal_state = "direct-flow-state-xyz"
        _pending_auth_codes[internal_state] = {
            "flow": "direct",
            "chatgpt_client_id": "test-client",
            "chatgpt_redirect_uri": "https://chatgpt.com/callback",
            "chatgpt_state": "some-state",
            "code_challenge": "",
            "code_challenge_method": "",
        }

        fake_tokens = {
            "access_token": "pco-access",
            "refresh_token": "pco-refresh",
            "expires_in": 7200,
        }
        fake_me = {"id": 55, "first_name": "Direct", "last_name": "User", "org_name": "DirectChurch"}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.commit = AsyncMock()

        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        fake_user.pco_org_name = "DirectChurch"
        session.refresh = AsyncMock(
            side_effect=lambda u: (
                setattr(u, "id", fake_user.id) or setattr(u, "pco_org_name", "DirectChurch")
            )
        )

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

        # Direct flow should redirect to /dashboard
        assert resp.status_code in (302, 307)
        location = resp.headers["location"]
        assert "dashboard" in location
        assert "token=" in location

        _pending_auth_codes.clear()
        _registered_clients.clear()


# ---------------------------------------------------------------------------
# pco/people.py — both email and phone warning (lines 23-24)
# ---------------------------------------------------------------------------


class TestPeopleAPIEmailAndPhoneWarning:
    @pytest.mark.asyncio
    async def test_search_people_warns_when_email_and_phone_both_provided(self) -> None:
        """When both email and phone are given, a warning is issued."""
        mock_client = AsyncMock(spec=PCOClient)
        mock_client.get = AsyncMock(return_value={"data": []})
        api = PeopleAPI(mock_client)

        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = await api.search_people(email="a@b.com", phone="555-1234")

        assert any("email" in str(w.message).lower() for w in caught)
        assert result == []


# ---------------------------------------------------------------------------
# tools/people.py — update_person with email field (line 97)
# ---------------------------------------------------------------------------


class TestToolsPeopleUpdatePersonEmail:
    @pytest.mark.asyncio
    async def test_update_person_passes_email_field(self) -> None:
        """When email is provided to update_person, it is passed to the API."""
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
