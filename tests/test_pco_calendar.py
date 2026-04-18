import json
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.calendar import CalendarAPI

FIXTURES = Path(__file__).parent / "fixtures" / "calendar"

def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())

@pytest.fixture
def mock_client() -> PCOClient:
    return AsyncMock(spec=PCOClient)


class TestGetEvents:
    async def test_returns_envelope_shape(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_events.json")["data"],
            total_count=1,
            truncated=False,
        )
        api = CalendarAPI(mock_client)
        result = await api.get_events()
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 1
        assert result["meta"]["truncated"] is False

    async def test_default_applies_filter_future(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CalendarAPI(mock_client)
        result = await api.get_events()
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert call_params.get("filter") == "future"
        assert result["meta"]["filters_applied"].get("filter") == "future"

    async def test_include_past_drops_filter_future(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CalendarAPI(mock_client)
        result = await api.get_events(include_past=True)
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "filter" not in call_params
        assert "filter" not in result["meta"]["filters_applied"]

    async def test_passes_include_owner_only(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CalendarAPI(mock_client)
        await api.get_events()
        call_params = mock_client.get_all.call_args.kwargs["params"]
        # include=event_instances is NOT valid on this endpoint — only owner.
        assert call_params.get("include") == "owner"

    async def test_does_not_send_order_param(self, mock_client: AsyncMock) -> None:
        """Calendar v2 events endpoint does not support ordering."""
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CalendarAPI(mock_client)
        await api.get_events()
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "order" not in call_params

    async def test_featured_only_sends_where_featured(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CalendarAPI(mock_client)
        result = await api.get_events(featured_only=True)
        call_params = mock_client.get_all.call_args.kwargs["params"]
        # Featured events are filtered via where[featured]=true, NOT via
        # `filter=featured` — the latter is not in can_filter.
        assert call_params.get("where[featured]") == "true"
        assert result["meta"]["filters_applied"].get("where[featured]") == "true"

    async def test_simplified_event_includes_owner_name(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        raw_events = load_fixture("list_events.json")["data"]
        raw_included = load_fixture("list_events.json")["included"]
        mock_client.get_all.return_value = PagedResult(
            items=raw_events, total_count=1, truncated=False, included=raw_included,
        )
        api = CalendarAPI(mock_client)
        result = await api.get_events()
        event = result["items"][0]
        assert event["owner_name"] == "Alice Smith"
        assert event["instances"][0]["location"] == "Sanctuary"

    async def test_truncation_surfaces_in_meta(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[], total_count=15000, truncated=True,
        )
        api = CalendarAPI(mock_client)
        result = await api.get_events()
        assert result["meta"]["truncated"] is True
        assert result["meta"]["total_count"] == 15000

    async def test_description_not_truncated(self, mock_client: AsyncMock) -> None:
        """Full description must be preserved — no 200-char truncation."""
        from pco_mcp.pco.client import PagedResult
        long_desc = "This is a long description. " * 20  # ~560 chars
        raw = {
            "type": "Event",
            "id": "201",
            "attributes": {
                "name": "Easter",
                "description": long_desc,
                "visible_in_church_center": True,
            },
            "relationships": {},
        }
        mock_client.get_all.return_value = PagedResult(items=[raw], total_count=1, truncated=False)
        api = CalendarAPI(mock_client)
        result = await api.get_events()
        assert result["items"][0]["description"] == long_desc
        assert "..." not in result["items"][0]["description"]

    async def test_owner_id_flattened_from_relationship(self, mock_client: AsyncMock) -> None:
        """owner_id must be present whenever the owner relationship ref exists."""
        from pco_mcp.pco.client import PagedResult
        raw = {
            "type": "Event", "id": "201",
            "attributes": {
                "name": "E", "description": "", "visible_in_church_center": False,
            },
            "relationships": {
                "owner": {"data": {"type": "Person", "id": "42"}}
            },
        }
        mock_client.get_all.return_value = PagedResult(items=[raw], total_count=1, truncated=False)
        api = CalendarAPI(mock_client)
        result = await api.get_events()
        assert result["items"][0]["owner_id"] == "42"

    async def test_list_path_does_not_leak_eventinstance_fields(
        self, mock_client: AsyncMock,
    ) -> None:
        """starts_at/ends_at/recurrence live on EventInstance, not Event —
        the list path must NOT include those keys (they're always None on
        Event.attributes and would be misleading)."""
        from pco_mcp.pco.client import PagedResult
        raw_events = load_fixture("list_events.json")["data"]
        raw_included = load_fixture("list_events.json")["included"]
        mock_client.get_all.return_value = PagedResult(
            items=raw_events, total_count=1, truncated=False, included=raw_included,
        )
        api = CalendarAPI(mock_client)
        result = await api.get_events()
        event = result["items"][0]
        assert "starts_at" not in event
        assert "ends_at" not in event
        assert "recurrence" not in event


class TestGetEventDetail:
    async def test_returns_full_detail(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get.return_value = load_fixture("get_event.json")
        mock_client.get_all.side_effect = [
            PagedResult(items=load_fixture("get_event_instances.json")["data"]),
            PagedResult(items=load_fixture("get_event_resources.json")["data"]),
        ]
        api = CalendarAPI(mock_client)
        detail = await api.get_event_detail("201")
        assert detail["name"] == "Easter Sunday Service"
        assert len(detail["instances"]) == 1
        assert detail["instances"][0]["starts_at"] == "2026-04-20T09:00:00Z"
        assert len(detail["resources"]) == 2
        assert detail["resources"][0]["name"] == "Main Sanctuary"
        assert detail["resources"][1]["resource_type"] == "Equipment"

    async def test_calls_three_endpoints(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get.return_value = load_fixture("get_event.json")
        mock_client.get_all.return_value = PagedResult(items=[])
        api = CalendarAPI(mock_client)
        await api.get_event_detail("201")
        assert mock_client.get.call_count == 1
        assert mock_client.get_all.call_count == 2
