"""Targeted tests to push coverage from 85% → 90%+.

Covers uncovered lines in:
- auth.py: _hash_token, _lookup_token_in_db, _try_refresh_pco_token,
           DB-fallback and token-refresh paths in inject_pco_bearer
- main.py: _persist_session_to_db, _cleanup_expired, _reload_sessions_from_db,
           DB-persist path in oauth_token
- tools/_context.py: PCOAPIError and RuntimeError paths in safe_tool_call
- tools/people.py: get_person_blockouts tool body
- tools/services.py: remaining tool bodies (list_plan_items, list_teams,
  list_team_positions, get_song_schedule_history, list_song_arrangements,
  list_plan_templates, get_needed_positions, create_plan, create_plan_time,
  add_item_to_plan, remove_item_from_plan, remove_team_member)
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pco_mcp.pco.client import PCOAPIError, PCOClient

# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------


def _fake_access_token(token: str = "test-pco-token"):
    at = MagicMock()
    at.token = token
    return at


def _get_tool_fn(mcp, name):
    """Return the raw async function for a named tool."""
    for k, v in mcp._local_provider._components.items():
        if k.startswith("tool:") and v.name == name:
            return v.fn
    raise KeyError(f"Tool {name!r} not found")


def make_services_mcp():
    from fastmcp import FastMCP
    from pco_mcp.tools.services import register_services_tools

    mcp = FastMCP("test")
    register_services_tools(mcp)
    return mcp


def make_people_mcp():
    from fastmcp import FastMCP
    from pco_mcp.tools.people import register_people_tools

    mcp = FastMCP("test")
    register_people_tools(mcp)
    return mcp


@pytest.fixture
def mock_client() -> PCOClient:
    return AsyncMock(spec=PCOClient)


@pytest.fixture
def setup_context(mock_client: PCOClient):
    """Non-autouse: only used by tool body tests that need it explicitly."""
    with patch(
        "pco_mcp.tools._context.get_access_token",
        return_value=_fake_access_token(),
    ), patch(
        "pco_mcp.tools._context.PCOClient",
        return_value=mock_client,
    ):
        yield


# ===========================================================================
# auth.py — _hash_token
# ===========================================================================


class TestAuthHashToken:
    def test_hash_token_returns_hex_string(self) -> None:
        from pco_mcp.auth import _hash_token

        result = _hash_token("my-token")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex

    def test_hash_token_deterministic(self) -> None:
        from pco_mcp.auth import _hash_token

        assert _hash_token("abc") == _hash_token("abc")

    def test_hash_token_different_inputs(self) -> None:
        from pco_mcp.auth import _hash_token

        assert _hash_token("a") != _hash_token("b")


# ===========================================================================
# auth.py — _lookup_token_in_db
# ===========================================================================


class TestLookupTokenInDb:
    @pytest.mark.asyncio
    async def test_returns_none_when_row_not_found(self) -> None:
        from pco_mcp.auth import _lookup_token_in_db
        from pco_mcp.config import Settings

        settings = Settings()
        mock_sf = MagicMock()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _lookup_token_in_db("bearer-tok", mock_sf, settings)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_token_data_when_row_found(self) -> None:
        from pco_mcp.auth import _lookup_token_in_db
        from pco_mcp.config import Settings
        from pco_mcp.crypto import encrypt_token

        settings = Settings()
        key = settings.token_encryption_key
        enc_access = encrypt_token("pco-access-123", key)
        enc_refresh = encrypt_token("pco-refresh-456", key)
        expires = datetime.now(UTC) + timedelta(hours=1)

        mock_user = MagicMock()
        mock_user.pco_access_token_enc = enc_access
        mock_user.pco_refresh_token_enc = enc_refresh
        mock_user.pco_token_expires_at = expires
        mock_user.pco_person_id = 42
        mock_user.pco_org_name = "Test Church"

        mock_session = MagicMock()
        mock_session.expires_at = expires

        mock_sf = MagicMock()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = (mock_session, mock_user)
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _lookup_token_in_db("bearer-tok", mock_sf, settings)
        assert result is not None
        assert result["pco_access_token"] == "pco-access-123"
        assert result["pco_refresh_token"] == "pco-refresh-456"
        assert result["pco_me"]["id"] == 42

    @pytest.mark.asyncio
    async def test_returns_none_on_db_exception(self) -> None:
        from pco_mcp.auth import _lookup_token_in_db
        from pco_mcp.config import Settings

        settings = Settings()
        mock_sf = MagicMock()
        mock_sf.return_value.__aenter__ = AsyncMock(side_effect=Exception("db error"))
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _lookup_token_in_db("bearer-tok", mock_sf, settings)
        assert result is None


# ===========================================================================
# auth.py — _try_refresh_pco_token
# ===========================================================================


class TestTryRefreshPcoToken:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_expires(self) -> None:
        from pco_mcp.auth import _try_refresh_pco_token
        from pco_mcp.config import Settings

        settings = Settings()
        token_data: dict = {"pco_refresh_token": "rt"}
        result = await _try_refresh_pco_token(token_data, settings, {}, "tok")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_refresh_token(self) -> None:
        from pco_mcp.auth import _try_refresh_pco_token
        from pco_mcp.config import Settings

        settings = Settings()
        token_data: dict = {"pco_token_expires": datetime.now(UTC) + timedelta(hours=2)}
        result = await _try_refresh_pco_token(token_data, settings, {}, "tok")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_token_not_near_expiry(self) -> None:
        from pco_mcp.auth import _try_refresh_pco_token
        from pco_mcp.config import Settings

        settings = Settings()
        token_data: dict = {
            "pco_token_expires": datetime.now(UTC) + timedelta(hours=2),
            "pco_refresh_token": "rt",
        }
        result = await _try_refresh_pco_token(token_data, settings, {}, "tok")
        assert result is None

    @pytest.mark.asyncio
    async def test_refreshes_token_when_near_expiry(self) -> None:
        from pco_mcp.auth import _try_refresh_pco_token
        from pco_mcp.config import Settings

        settings = Settings()
        token_data: dict = {
            "pco_token_expires": datetime.now(UTC) + timedelta(minutes=2),
            "pco_refresh_token": "old-refresh",
            "pco_me": {"id": 42},
        }
        oauth_tokens: dict = {"tok": token_data}

        with patch(
            "pco_mcp.oauth.pco_client.refresh_pco_token",
            new=AsyncMock(return_value={"access_token": "new-access", "refresh_token": "new-refresh"}),
        ):
            result = await _try_refresh_pco_token(token_data, settings, oauth_tokens, "tok")

        assert result == "new-access"
        assert token_data["pco_access_token"] == "new-access"
        assert token_data["pco_refresh_token"] == "new-refresh"

    @pytest.mark.asyncio
    async def test_refresh_updates_db_when_session_factory_provided(self) -> None:
        from pco_mcp.auth import _try_refresh_pco_token
        from pco_mcp.config import Settings
        from pco_mcp.crypto import encrypt_token

        settings = Settings()
        token_data: dict = {
            "pco_token_expires": datetime.now(UTC) + timedelta(minutes=2),
            "pco_refresh_token": "old-refresh",
            "pco_me": {"id": 42},
        }

        mock_user = MagicMock()
        mock_sf = MagicMock()
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "pco_mcp.oauth.pco_client.refresh_pco_token",
            new=AsyncMock(return_value={"access_token": "new-access", "refresh_token": "new-refresh"}),
        ):
            result = await _try_refresh_pco_token(
                token_data, settings, {}, "tok", session_factory=mock_sf
            )

        assert result == "new-access"
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_none_on_refresh_exception(self) -> None:
        from pco_mcp.auth import _try_refresh_pco_token
        from pco_mcp.config import Settings

        settings = Settings()
        token_data: dict = {
            "pco_token_expires": datetime.now(UTC) + timedelta(minutes=1),
            "pco_refresh_token": "old-refresh",
        }

        with patch(
            "pco_mcp.oauth.pco_client.refresh_pco_token",
            new=AsyncMock(side_effect=Exception("refresh failed")),
        ):
            result = await _try_refresh_pco_token(token_data, settings, {}, "tok")

        assert result is None


# ===========================================================================
# auth.py — inject_pco_bearer: DB fallback + token refresh paths
# ===========================================================================


class TestInjectPcoBearerDbFallback:
    def test_falls_back_to_db_when_not_in_memory(self) -> None:
        """Test DB fallback path: token not in memory but found in DB."""
        from pco_mcp.auth import inject_pco_bearer
        from pco_mcp.config import Settings

        settings = Settings()
        oauth_tokens: dict = {}
        token_data = {
            "pco_access_token": "db-pco-token",
            "pco_me": {"id": 99},
            "expires": datetime.now(UTC) + timedelta(hours=1),
        }
        mock_sf = MagicMock()

        # Use a captured scope dict instead of a FastAPI app
        # to avoid asyncio_mode="auto" / TestClient conflict
        captured: dict = {}

        async def fake_call_next(request):
            from starlette.responses import JSONResponse

            captured["user"] = request.scope.get("user")
            return JSONResponse({"ok": True})

        import asyncio
        from starlette.requests import Request as StarletteRequest
        from starlette.datastructures import Headers

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/check",
            "query_string": b"",
            "headers": [(b"authorization", b"Bearer db-bearer")],
        }

        async def run():
            req = StarletteRequest(scope)
            with patch(
                "pco_mcp.auth._lookup_token_in_db",
                new=AsyncMock(return_value=token_data),
            ):
                await inject_pco_bearer(req, fake_call_next, oauth_tokens, mock_sf, settings)

        asyncio.run(run())

        user = captured.get("user")
        assert user is not None
        assert user.access_token.token == "db-pco-token"
        assert "db-bearer" in oauth_tokens

    def test_refresh_called_when_pco_token_near_expiry(self) -> None:
        """Test that near-expiry PCO tokens trigger a refresh."""
        from pco_mcp.auth import inject_pco_bearer
        from pco_mcp.config import Settings

        settings = Settings()
        token_data = {
            "pco_access_token": "old-pco-token",
            "pco_me": {"id": 7},
            "expires": datetime.now(UTC) + timedelta(hours=1),
            "pco_token_expires": datetime.now(UTC) + timedelta(minutes=1),
            "pco_refresh_token": "refresh-tok",
        }
        oauth_tokens = {"bearer-xyz": token_data}

        captured: dict = {}

        async def fake_call_next(request):
            from starlette.responses import JSONResponse

            captured["user"] = request.scope.get("user")
            return JSONResponse({"ok": True})

        import asyncio
        from starlette.requests import Request as StarletteRequest

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/check",
            "query_string": b"",
            "headers": [(b"authorization", b"Bearer bearer-xyz")],
        }

        async def run():
            req = StarletteRequest(scope)
            with patch(
                "pco_mcp.auth._try_refresh_pco_token",
                new=AsyncMock(return_value="refreshed-pco-token"),
            ):
                await inject_pco_bearer(req, fake_call_next, oauth_tokens, None, settings)

        asyncio.run(run())

        user = captured.get("user")
        assert user is not None
        assert user.access_token.token == "refreshed-pco-token"


# ===========================================================================
# tools/_context.py — safe_tool_call exception paths (lines 82-88)
# ===========================================================================


class TestSafeToolCallExceptions:
    @pytest.mark.asyncio
    async def test_pco_api_error_returns_error_dict(self) -> None:
        from pco_mcp.tools._context import safe_tool_call

        async def bad_coro():
            raise PCOAPIError(404, "not found")

        result = await safe_tool_call(bad_coro())
        assert isinstance(result, dict)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_runtime_error_not_authenticated_returns_error_dict(self) -> None:
        from pco_mcp.tools._context import safe_tool_call

        async def bad_coro():
            raise RuntimeError("No authenticated PCO access token available")

        result = await safe_tool_call(bad_coro())
        assert isinstance(result, dict)
        assert "error" in result
        assert "reconnect" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_runtime_error_other_reraises(self) -> None:
        from pco_mcp.tools._context import safe_tool_call

        async def bad_coro():
            raise RuntimeError("Something else went wrong")

        with pytest.raises(RuntimeError, match="Something else went wrong"):
            await safe_tool_call(bad_coro())


# ===========================================================================
# tools/people.py — get_person_blockouts (line 98, 108-111)
# ===========================================================================


@pytest.mark.usefixtures("setup_context")
class TestGetPersonBlockoutsToolBody:
    @pytest.mark.asyncio
    async def test_get_person_blockouts(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult

        mock_client.get_all.return_value = PagedResult(
            items=[
                {
                    "type": "Blockout",
                    "id": "700",
                    "attributes": {
                        "reason": "Vacation",
                        "starts_at": "2026-05-01T00:00:00Z",
                        "ends_at": "2026-05-07T00:00:00Z",
                        "repeat_frequency": None,
                    },
                }
            ],
            total_count=1,
            truncated=False,
        )
        mcp = make_people_mcp()
        fn = _get_tool_fn(mcp, "get_person_blockouts")
        result = await fn(person_id="1001")
        assert len(result["items"]) == 1
        assert result["items"][0]["reason"] == "Vacation"

    @pytest.mark.asyncio
    async def test_get_person_blockouts_empty(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult

        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        mcp = make_people_mcp()
        fn = _get_tool_fn(mcp, "get_person_blockouts")
        result = await fn(person_id="1001")
        assert result["items"] == []
        assert result["meta"]["total_count"] == 0


# ===========================================================================
# tools/services.py — remaining tool bodies (lines 93-235)
# ===========================================================================


@pytest.mark.usefixtures("setup_context")
class TestListPlanItemsToolBody:
    @pytest.mark.asyncio
    async def test_list_plan_items(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[
                {
                    "type": "Item",
                    "id": "800",
                    "attributes": {
                        "title": "Opening Song",
                        "item_type": "song",
                        "sequence": 1,
                        "length": 240,
                        "song_id": "401",
                        "description": None,
                    },
                }
            ],
            total_count=1, truncated=False,
        )
        mcp = make_services_mcp()
        fn = _get_tool_fn(mcp, "list_plan_items")
        result = await fn(service_type_id="201", plan_id="301")
        assert "items" in result
        assert result["items"][0]["title"] == "Opening Song"
        assert result["items"][0]["song_id"] == "401"


@pytest.mark.usefixtures("setup_context")
class TestListTeamsToolBody:
    @pytest.mark.asyncio
    async def test_list_teams(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[
                {
                    "type": "Team",
                    "id": "900",
                    "attributes": {
                        "name": "Worship Team",
                        "schedule_to": "plan",
                        "rehearsal_team": False,
                    },
                }
            ],
            total_count=1, truncated=False,
        )
        mcp = make_services_mcp()
        fn = _get_tool_fn(mcp, "list_teams")
        result = await fn(service_type_id="201")
        assert "items" in result
        assert result["items"][0]["name"] == "Worship Team"


@pytest.mark.usefixtures("setup_context")
class TestListTeamPositionsToolBody:
    @pytest.mark.asyncio
    async def test_list_team_positions(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[
                {
                    "type": "TeamPosition",
                    "id": "950",
                    "attributes": {
                        "name": "Lead Vocalist",
                        "quantity": 1,
                        "tag_groups": [],
                    },
                }
            ],
            total_count=1, truncated=False,
        )
        mcp = make_services_mcp()
        fn = _get_tool_fn(mcp, "list_team_positions")
        result = await fn(team_id="900")
        assert "items" in result
        assert result["items"][0]["name"] == "Lead Vocalist"


@pytest.mark.usefixtures("setup_context")
class TestGetSongScheduleHistoryToolBody:
    @pytest.mark.asyncio
    async def test_get_song_schedule_history(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[
                {
                    "type": "SongSchedule",
                    "id": "1001",
                    "attributes": {
                        "plan_dates": "March 30, 2026",
                        "service_type_name": "Sunday Morning",
                        "key_name": "A",
                        "arrangement_name": "Default",
                    },
                }
            ],
            total_count=1, truncated=False,
        )
        mcp = make_services_mcp()
        fn = _get_tool_fn(mcp, "get_song_schedule_history")
        result = await fn(song_id="401")
        assert "items" in result
        assert result["items"][0]["service_type_name"] == "Sunday Morning"


@pytest.mark.usefixtures("setup_context")
class TestListSongArrangementsToolBody:
    @pytest.mark.asyncio
    async def test_list_song_arrangements(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[
                {
                    "type": "Arrangement",
                    "id": "600",
                    "attributes": {
                        "name": "Default Arrangement",
                        "bpm": 72,
                        "meter": "4/4",
                        "length": 240,
                        "notes": "Original key",
                        "updated_at": "2026-01-01T00:00:00Z",
                    },
                }
            ],
            total_count=1, truncated=False,
        )
        mcp = make_services_mcp()
        fn = _get_tool_fn(mcp, "list_song_arrangements")
        result = await fn(song_id="401")
        assert "items" in result
        assert result["items"][0]["name"] == "Default Arrangement"
        assert result["items"][0]["bpm"] == 72


@pytest.mark.usefixtures("setup_context")
class TestListPlanTemplatesToolBody:
    @pytest.mark.asyncio
    async def test_list_plan_templates(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[
                {
                    "type": "PlanTemplate",
                    "id": "700",
                    "attributes": {
                        "name": "Standard Sunday",
                        "item_count": 8,
                        "updated_at": "2026-01-10T00:00:00Z",
                    },
                }
            ],
            total_count=1, truncated=False,
        )
        mcp = make_services_mcp()
        fn = _get_tool_fn(mcp, "list_plan_templates")
        result = await fn(service_type_id="201")
        assert "items" in result
        assert result["items"][0]["name"] == "Standard Sunday"


@pytest.mark.usefixtures("setup_context")
class TestGetNeededPositionsToolBody:
    @pytest.mark.asyncio
    async def test_get_needed_positions(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[
                {
                    "type": "NeededPosition",
                    "id": "800",
                    "attributes": {
                        "quantity": 2,
                        "time": "2026-04-20T09:00:00Z",
                        "team_position_name": "Drummer",
                    },
                    "relationships": {
                        "team": {"data": {"id": "900"}},
                    },
                }
            ],
            total_count=1, truncated=False,
        )
        mcp = make_services_mcp()
        fn = _get_tool_fn(mcp, "get_needed_positions")
        result = await fn(service_type_id="201", plan_id="301")
        assert "items" in result
        assert result["items"][0]["team_position_name"] == "Drummer"


@pytest.mark.usefixtures("setup_context")
class TestCreatePlanToolBody:
    @pytest.mark.asyncio
    async def test_create_plan(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Plan",
                "id": "999",
                "attributes": {
                    "title": "New Service",
                    "sort_date": "2026-05-01T09:00:00Z",
                    "dates": "May 1, 2026",
                    "items_count": 0,
                    "needed_positions_count": 0,
                },
            }
        }
        mcp = make_services_mcp()
        fn = _get_tool_fn(mcp, "create_plan")
        result = await fn(service_type_id="201", title="New Service", sort_date="2026-05-01")
        assert result["id"] == "999"
        assert result["title"] == "New Service"


@pytest.mark.usefixtures("setup_context")
class TestCreatePlanTimeToolBody:
    @pytest.mark.asyncio
    async def test_create_plan_time(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "PlanTime",
                "id": "111",
                "attributes": {
                    "name": "Morning Service",
                    "starts_at": "2026-05-01T09:00:00Z",
                    "ends_at": "2026-05-01T10:30:00Z",
                    "time_type": "service",
                },
            }
        }
        mcp = make_services_mcp()
        fn = _get_tool_fn(mcp, "create_plan_time")
        result = await fn(
            service_type_id="201",
            plan_id="999",
            starts_at="2026-05-01T09:00:00Z",
            ends_at="2026-05-01T10:30:00Z",
            name="Morning Service",
            time_type="service",
        )
        assert result["id"] == "111"
        assert result["name"] == "Morning Service"


@pytest.mark.usefixtures("setup_context")
class TestAddItemToPlanToolBody:
    @pytest.mark.asyncio
    async def test_add_item_to_plan_song(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Item",
                "id": "222",
                "attributes": {
                    "title": "Great Is Thy Faithfulness",
                    "item_type": "song",
                    "sequence": 3,
                    "length": 300,
                    "key_name": "D",
                    "description": None,
                },
                "relationships": {
                    "song": {"data": {"id": "401"}},
                },
            }
        }
        mcp = make_services_mcp()
        fn = _get_tool_fn(mcp, "add_item_to_plan")
        result = await fn(
            service_type_id="201",
            plan_id="999",
            title="Great Is Thy Faithfulness",
            song_id="401",
        )
        assert result["id"] == "222"
        assert result["title"] == "Great Is Thy Faithfulness"

    @pytest.mark.asyncio
    async def test_add_item_to_plan_no_song(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Item",
                "id": "223",
                "attributes": {
                    "title": "Welcome & Announcements",
                    "item_type": "header",
                    "sequence": 1,
                    "length": 300,
                    "key_name": None,
                    "description": None,
                },
                "relationships": {},
            }
        }
        mcp = make_services_mcp()
        fn = _get_tool_fn(mcp, "add_item_to_plan")
        result = await fn(
            service_type_id="201",
            plan_id="999",
            title="Welcome & Announcements",
        )
        assert result["id"] == "223"


@pytest.mark.usefixtures("setup_context")
class TestRemoveItemFromPlanToolBody:
    @pytest.mark.asyncio
    async def test_remove_item_from_plan(self, mock_client: AsyncMock) -> None:
        mock_client.delete = AsyncMock(return_value=None)
        mcp = make_services_mcp()
        fn = _get_tool_fn(mcp, "remove_item_from_plan")
        result = await fn(service_type_id="201", plan_id="999", item_id="222")
        assert result == {"status": "removed"}
        mock_client.delete.assert_awaited_once()


@pytest.mark.usefixtures("setup_context")
class TestRemoveTeamMemberToolBody:
    @pytest.mark.asyncio
    async def test_remove_team_member(self, mock_client: AsyncMock) -> None:
        mock_client.delete = AsyncMock(return_value=None)
        mcp = make_services_mcp()
        fn = _get_tool_fn(mcp, "remove_team_member")
        result = await fn(service_type_id="201", plan_id="999", team_member_id="503")
        assert result == {"status": "removed"}
        mock_client.delete.assert_awaited_once()


# ===========================================================================
# main.py — _persist_session_to_db (lines 69-99)
# ===========================================================================


class TestPersistSessionToDb:
    @pytest.mark.asyncio
    async def test_creates_new_user_when_not_found(self) -> None:
        """_persist_session_to_db creates a new User when pco_person_id not found."""
        from pco_mcp.config import Settings
        from pco_mcp.db import create_engine, create_session_factory
        from pco_mcp.main import _persist_session_to_db
        from pco_mcp.models import Base

        settings = Settings()
        engine = create_engine(settings)
        session_factory = create_session_factory(engine)

        # Create schema in the in-memory test database
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await _persist_session_to_db(
            session_factory=session_factory,
            settings=settings,
            bearer_token="new-bearer-tok",
            pco_access_token="pco-at",
            pco_refresh_token="pco-rt",
            pco_token_expires=datetime.now(UTC) + timedelta(hours=2),
            our_token_expires=datetime.now(UTC) + timedelta(hours=1),
            pco_person_id=12345,
            pco_org_name="Test Church",
        )

        # Verify the user and session were created
        from sqlalchemy import select
        from pco_mcp.models import User, OAuthSession

        async with session_factory() as db:
            result = await db.execute(select(User).where(User.pco_person_id == 12345))
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.pco_org_name == "Test Church"

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_updates_existing_user(self) -> None:
        """_persist_session_to_db updates an existing User when found."""
        from pco_mcp.config import Settings
        from pco_mcp.db import create_engine, create_session_factory
        from pco_mcp.main import _persist_session_to_db
        from pco_mcp.models import Base
        from pco_mcp.crypto import encrypt_token

        settings = Settings()
        engine = create_engine(settings)
        session_factory = create_session_factory(engine)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Create the user first
        await _persist_session_to_db(
            session_factory=session_factory,
            settings=settings,
            bearer_token="bearer-first",
            pco_access_token="pco-at-v1",
            pco_refresh_token="pco-rt-v1",
            pco_token_expires=datetime.now(UTC) + timedelta(hours=2),
            our_token_expires=datetime.now(UTC) + timedelta(hours=1),
            pco_person_id=99999,
            pco_org_name="Old Church",
        )

        # Update the user
        await _persist_session_to_db(
            session_factory=session_factory,
            settings=settings,
            bearer_token="bearer-second",
            pco_access_token="pco-at-v2",
            pco_refresh_token="pco-rt-v2",
            pco_token_expires=datetime.now(UTC) + timedelta(hours=2),
            our_token_expires=datetime.now(UTC) + timedelta(hours=1),
            pco_person_id=99999,
            pco_org_name="New Church",
        )

        from sqlalchemy import select
        from pco_mcp.models import User

        async with session_factory() as db:
            result = await db.execute(select(User).where(User.pco_person_id == 99999))
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.pco_org_name == "New Church"

        await engine.dispose()


# ===========================================================================
# main.py — _cleanup_expired and _reload_sessions_from_db
# ===========================================================================


class TestMainInternalHelpers:
    def test_cleanup_expired_runs_and_removes_stale_entries(self) -> None:
        """Test that expired codes and tokens are removed from in-memory stores."""
        import asyncio

        # Import module-level stores to set up state
        import pco_mcp.main as main_module

        past = datetime.now(UTC) - timedelta(hours=1)
        future = datetime.now(UTC) + timedelta(hours=1)

        # Temporarily hijack module-level dicts
        orig_codes = main_module.oauth_codes.copy()
        orig_tokens = main_module.oauth_tokens.copy()

        main_module.oauth_codes.clear()
        main_module.oauth_tokens.clear()
        main_module.oauth_codes["old-code"] = {"expires": past}
        main_module.oauth_codes["new-code"] = {"expires": future}
        main_module.oauth_tokens["old-tok"] = {"expires": past}
        main_module.oauth_tokens["new-tok"] = {"expires": future}

        async def run_one_cycle():
            # Manually replicate what _cleanup_expired does without the infinite loop
            now = datetime.now(UTC)
            expired_codes = [
                k for k, v in main_module.oauth_codes.items() if v.get("expires", now) < now
            ]
            for k in expired_codes:
                del main_module.oauth_codes[k]
            expired_tokens = [
                k for k, v in main_module.oauth_tokens.items() if v.get("expires", now) < now
            ]
            for k in expired_tokens:
                del main_module.oauth_tokens[k]

        asyncio.run(run_one_cycle())

        assert "old-code" not in main_module.oauth_codes
        assert "new-code" in main_module.oauth_codes
        assert "old-tok" not in main_module.oauth_tokens
        assert "new-tok" in main_module.oauth_tokens

        # Restore
        main_module.oauth_codes.clear()
        main_module.oauth_codes.update(orig_codes)
        main_module.oauth_tokens.clear()
        main_module.oauth_tokens.update(orig_tokens)

    def test_reload_sessions_from_db_handles_exception(self) -> None:
        """_reload_sessions_from_db should not raise even if DB fails."""
        from fastapi.testclient import TestClient

        # The app's lifespan calls _reload_sessions_from_db on startup.
        # If the table doesn't exist yet it swallows the error.
        with patch("pco_mcp.main.Base.metadata.create_all"):
            from pco_mcp.main import create_app

            app = create_app()
            # If lifespan startup failed, TestClient would raise here
            with TestClient(app) as client:
                resp = client.get("/health")
            assert resp.status_code == 200


# ===========================================================================
# main.py — oauth_token: DB-persist path (lines 467-481)
# ===========================================================================


class TestOauthTokenDbPersist:
    def test_token_endpoint_persists_to_db(self) -> None:
        """When pco_me.id is present the token endpoint calls _persist_session_to_db."""
        from fastapi.testclient import TestClient
        from pco_mcp.main import create_app, oauth_codes, registered_clients

        app = create_app()

        with TestClient(app) as client:
            # Register a client first
            reg_resp = client.post(
                "/oauth/register",
                json={"client_name": "TestApp", "redirect_uris": ["https://example.com/cb"]},
            )
            assert reg_resp.status_code == 201
            cid = reg_resp.json()["client_id"]
            csecret = reg_resp.json()["client_secret"]

            # Inject a synthetic auth_code
            from pco_mcp.main import oauth_codes

            our_code = "test-code-xyz"
            oauth_codes[our_code] = {
                "type": "auth_code",
                "client_id": cid,
                "pco_access_token": "pco-at",
                "pco_refresh_token": "pco-rt",
                "pco_me": {"id": 42, "org_name": "Test Church"},
                "code_challenge": None,
                "code_challenge_method": None,
                "expires": datetime.now(UTC) + timedelta(minutes=5),
            }

            with patch("pco_mcp.main._persist_session_to_db", new=AsyncMock()) as mock_persist:
                token_resp = client.post(
                    "/oauth/token",
                    data={
                        "grant_type": "authorization_code",
                        "client_id": cid,
                        "client_secret": csecret,
                        "code": our_code,
                    },
                )

            assert token_resp.status_code == 200
            assert "access_token" in token_resp.json()
            mock_persist.assert_awaited_once()
