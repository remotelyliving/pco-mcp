"""Tests for check-in tool function bodies."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pco_mcp.pco.client import PCOClient, PagedResult


def _fake_access_token(token: str = "test-pco-token"):
    at = MagicMock()
    at.token = token
    return at


@pytest.fixture
def mock_client() -> PCOClient:
    return AsyncMock(spec=PCOClient)


@pytest.fixture(autouse=True)
def setup_context(mock_client: PCOClient) -> None:
    with patch(
        "pco_mcp.tools._context.get_access_token",
        return_value=_fake_access_token(),
    ), patch(
        "pco_mcp.tools._context.PCOClient",
        return_value=mock_client,
    ):
        yield


def _get_tool_fn(mcp, name):
    for k, v in mcp._local_provider._components.items():
        if k.startswith("tool:") and v.name == name:
            return v.fn
    raise KeyError(f"Tool {name!r} not found")


def make_mcp():
    from fastmcp import FastMCP
    from pco_mcp.tools.checkins import register_checkins_tools
    mcp = FastMCP("test")
    register_checkins_tools(mcp)
    return mcp


class TestListCheckinEventsToolBody:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(
            items=[{
                "type": "Event", "id": "101",
                "attributes": {
                    "name": "Sunday Morning", "frequency": "weekly",
                    "created_at": "2025-01-01T00:00:00Z", "archived_at": None,
                },
            }],
            total_count=1, truncated=False,
        )
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_checkin_events")
        result = await fn()
        assert result["items"][0]["name"] == "Sunday Morning"
        assert result["meta"]["filters_applied"].get("where[archived_at]") == ""


class TestGetEventAttendanceToolBody:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(
            items=[{
                "type": "CheckIn", "id": "501",
                "attributes": {
                    "first_name": "Alice", "last_name": "Smith",
                    "created_at": "2026-04-13T09:15:00Z", "security_code": "ABC123",
                },
            }],
            total_count=1, truncated=False,
        )
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "get_event_attendance")
        result = await fn(event_id="101")
        assert result["items"][0]["first_name"] == "Alice"
        assert result["meta"]["total_count"] == 1


class TestGetHeadcountsToolBody:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(
            items=[{
                "type": "EventPeriod", "id": "301",
                "attributes": {"starts_at": "2026-04-13T09:00:00Z"},
            }],
            total_count=1, truncated=False,
        )
        mock_client.get.return_value = {
            "data": [{
                "type": "Headcount", "id": "401",
                "attributes": {"total": 150},
                "relationships": {
                    "attendance_type": {
                        "data": {
                            "type": "AttendanceType", "id": "50",
                            "attributes": {"name": "Main Sanctuary"},
                        }
                    }
                }
            }]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "get_headcounts")
        result = await fn(event_id="101")
        assert result["items"][0]["total"] == 150
