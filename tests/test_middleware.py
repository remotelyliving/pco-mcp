# tests/test_middleware.py
"""Tests for BearerTokenMiddleware."""
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from pco_mcp.crypto import encrypt_token
from pco_mcp.middleware import BearerTokenMiddleware
from pco_mcp.models import Base, OAuthSession, User

# ---------------------------------------------------------------------------
# Constants shared across tests
# ---------------------------------------------------------------------------
_ENCRYPTION_KEY = "JyU3hqD0bM06X5j88vekTdYHJJb5LxI1YWR0f55cw-c="
_PCO_CLIENT_ID = "test-pco-client-id"
_PCO_CLIENT_SECRET = "test-pco-client-secret"
_PCO_API_BASE = "https://api.planningcenteronline.com"
_VALID_TOKEN = "chatgpt-bearer-abc123"
_VALID_TOKEN_HASH = hashlib.sha256(_VALID_TOKEN.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_engine():
    """In-memory async SQLite engine with schema created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(session_factory):
    """Yield a live DB session for seeding test data."""
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(
    *,
    access_token: str = "pco-access-token",
    refresh_token: str = "pco-refresh-token",
    expires_at: datetime | None = None,
) -> User:
    if expires_at is None:
        expires_at = datetime.now(UTC) + timedelta(hours=2)
    return User(
        id=uuid.uuid4(),
        pco_person_id=12345,
        pco_org_name="Test Church",
        pco_access_token_enc=encrypt_token(access_token, _ENCRYPTION_KEY),
        pco_refresh_token_enc=encrypt_token(refresh_token, _ENCRYPTION_KEY),
        pco_token_expires_at=expires_at,
    )


def _make_session(user_id: uuid.UUID, *, token_hash: str = _VALID_TOKEN_HASH, expires_at: datetime | None = None) -> OAuthSession:
    if expires_at is None:
        expires_at = datetime.now(UTC) + timedelta(hours=8)
    return OAuthSession(
        id=uuid.uuid4(),
        user_id=user_id,
        chatgpt_access_token_hash=token_hash,
        expires_at=expires_at,
    )


def _make_backend_app() -> Starlette:
    """Tiny ASGI app to confirm the middleware passes requests through."""

    async def mcp_handler(request: Request) -> PlainTextResponse:
        return PlainTextResponse("mcp-ok")

    async def health_handler(request: Request) -> PlainTextResponse:
        return PlainTextResponse("health-ok")

    return Starlette(
        routes=[
            Route("/mcp/messages", mcp_handler),
            Route("/health", health_handler),
        ]
    )


def _wrap(session_factory) -> Starlette:
    backend = _make_backend_app()
    return BearerTokenMiddleware(
        backend,
        session_factory=session_factory,
        token_encryption_key=_ENCRYPTION_KEY,
        pco_client_id=_PCO_CLIENT_ID,
        pco_client_secret=_PCO_CLIENT_SECRET,
        pco_api_base=_PCO_API_BASE,
        mcp_path_prefix="/mcp",
    )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestValidBearerToken:
    """Test 1: valid bearer token — set_pco_client is called, request passes through."""

    @pytest.mark.asyncio
    async def test_valid_token_passes_through(self, session_factory, db_session):
        user = _make_user()
        oauth_session = _make_session(user.id)
        db_session.add(user)
        db_session.add(oauth_session)
        await db_session.commit()

        app = _wrap(session_factory)
        captured = {}

        with patch("pco_mcp.middleware.set_pco_client") as mock_set:
            mock_set.side_effect = lambda client: captured.update({"client": client})

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(
                    "/mcp/messages",
                    headers={"Authorization": f"Bearer {_VALID_TOKEN}"},
                )

        assert resp.status_code == 200
        assert resp.text == "mcp-ok"
        assert "client" in captured, "set_pco_client was not called"


class TestUnknownToken:
    """Test 2: unknown bearer token returns 401."""

    @pytest.mark.asyncio
    async def test_unknown_token_returns_401(self, session_factory):
        app = _wrap(session_factory)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/mcp/messages",
                headers={"Authorization": "Bearer completely-unknown-token"},
            )

        assert resp.status_code == 401
        body = resp.json()
        assert "error" in body
        assert "not found" in body["error"].lower() or "reconnect" in body["error"].lower()


class TestExpiredSession:
    """Test 3: expired OAuth session returns 401."""

    @pytest.mark.asyncio
    async def test_expired_session_returns_401(self, session_factory, db_session):
        user = _make_user()
        expired_session = _make_session(
            user.id,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        db_session.add(user)
        db_session.add(expired_session)
        await db_session.commit()

        app = _wrap(session_factory)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/mcp/messages",
                headers={"Authorization": f"Bearer {_VALID_TOKEN}"},
            )

        assert resp.status_code == 401
        body = resp.json()
        assert "expired" in body["error"].lower()


class TestNoAuthorizationHeader:
    """Test 4: non-MCP routes pass through without any Authorization header."""

    @pytest.mark.asyncio
    async def test_health_route_passes_without_auth(self, session_factory):
        app = _wrap(session_factory)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")

        assert resp.status_code == 200
        assert resp.text == "health-ok"

    @pytest.mark.asyncio
    async def test_mcp_without_auth_returns_401(self, session_factory):
        """MCP route without any Authorization header should get 401."""
        app = _wrap(session_factory)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/mcp/messages")

        assert resp.status_code == 401
        body = resp.json()
        assert "error" in body


class TestPCOTokenRefresh:
    """Test 5: PCO token near expiry triggers a refresh and DB update."""

    @pytest.mark.asyncio
    async def test_near_expiry_triggers_refresh(self, session_factory, db_session):
        # Token expires in 3 minutes — within the 5-minute buffer
        near_expiry = datetime.now(UTC) + timedelta(minutes=3)
        user = _make_user(
            access_token="old-pco-access",
            refresh_token="old-pco-refresh",
            expires_at=near_expiry,
        )
        oauth_session = _make_session(user.id)
        db_session.add(user)
        db_session.add(oauth_session)
        await db_session.commit()

        user_id = user.id
        new_token_data = {
            "access_token": "new-pco-access",
            "refresh_token": "new-pco-refresh",
            "expires_in": 7200,
        }

        app = _wrap(session_factory)
        captured = {}

        with (
            patch("pco_mcp.middleware.refresh_pco_token", new=AsyncMock(return_value=new_token_data)) as mock_refresh,
            patch("pco_mcp.middleware.set_pco_client") as mock_set,
        ):
            mock_set.side_effect = lambda client: captured.update({"client": client})

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get(
                    "/mcp/messages",
                    headers={"Authorization": f"Bearer {_VALID_TOKEN}"},
                )

        assert resp.status_code == 200, resp.text
        mock_refresh.assert_awaited_once()

        # Verify DB was updated with new encrypted tokens
        from sqlalchemy import select
        from pco_mcp.crypto import decrypt_token
        async with session_factory() as verify_session:
            result = await verify_session.execute(select(User).where(User.id == user_id))
            updated_user = result.scalar_one()
            assert decrypt_token(updated_user.pco_access_token_enc, _ENCRYPTION_KEY) == "new-pco-access"
            assert decrypt_token(updated_user.pco_refresh_token_enc, _ENCRYPTION_KEY) == "new-pco-refresh"
            updated_expires = updated_user.pco_token_expires_at
            if updated_expires.tzinfo is None:
                updated_expires = updated_expires.replace(tzinfo=UTC)
            # near_expiry is tz-aware; new expiry should be ~2 hours from now
            assert updated_expires > near_expiry
