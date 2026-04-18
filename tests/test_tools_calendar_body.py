"""Tests for calendar tool function bodies."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pco_mcp.pco.client import PCOClient


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
    from pco_mcp.tools.calendar import register_calendar_tools
    mcp = FastMCP("test")
    register_calendar_tools(mcp)
    return mcp


class TestListCalendarEventsToolBody:
    async def test_list_events(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = [
            {"type": "Event", "id": "201", "attributes": {"name": "Easter Service", "description": "Easter.", "starts_at": "2026-04-20T09:00:00Z", "ends_at": "2026-04-20T11:00:00Z", "recurrence": None, "visible_in_church_center": True}}
        ]
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_calendar_events")
        events = await fn()
        assert len(events) == 1
        assert events[0]["name"] == "Easter Service"


class TestGetEventDetailsToolBody:
    async def test_get_event_details(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {"data": {"type": "Event", "id": "201", "attributes": {"name": "Easter", "description": "", "starts_at": "2026-04-20T09:00:00Z", "ends_at": "2026-04-20T11:00:00Z", "recurrence": None, "visible_in_church_center": True}}}
        mock_client.get_all.side_effect = [
            [{"type": "EventInstance", "id": "301", "attributes": {"starts_at": "2026-04-20T09:00:00Z", "ends_at": "2026-04-20T11:00:00Z", "location": "Sanctuary"}}],
            [{"type": "EventResourceRequest", "id": "401", "attributes": {"name": "Sanctuary", "resource_type": "Room", "approval_status": "approved"}}],
        ]
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "get_event_details")
        detail = await fn(event_id="201")
        assert detail["name"] == "Easter"
        assert len(detail["instances"]) == 1
        assert len(detail["resources"]) == 1
