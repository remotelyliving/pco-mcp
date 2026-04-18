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
    async def test_returns_events(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = load_fixture("list_events.json")["data"]
        api = CalendarAPI(mock_client)
        events = await api.get_events()
        assert len(events) == 2
        assert events[0]["name"] == "Easter Sunday Service"
        assert events[1]["name"] == "Staff Meeting"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = []
        api = CalendarAPI(mock_client)
        await api.get_events()
        call_path = mock_client.get_all.call_args.args[0]
        assert "/calendar/v2/events" in call_path

    async def test_passes_date_filters(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = []
        api = CalendarAPI(mock_client)
        await api.get_events(start_date="2026-04-01", end_date="2026-04-30")
        call_kwargs = mock_client.get_all.call_args.kwargs
        params = call_kwargs.get("params", {})
        assert params.get("where[starts_at][gte]") == "2026-04-01"
        assert params.get("where[starts_at][lte]") == "2026-04-30"

    async def test_featured_filter(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = []
        api = CalendarAPI(mock_client)
        await api.get_events(featured_only=True)
        call_kwargs = mock_client.get_all.call_args.kwargs
        params = call_kwargs.get("params", {})
        assert params.get("filter") == "featured,future"

    async def test_truncates_description(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = load_fixture("list_events.json")["data"]
        api = CalendarAPI(mock_client)
        events = await api.get_events()
        assert len(events[0]["description"]) <= 200

    async def test_event_has_expected_fields(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = load_fixture("list_events.json")["data"]
        api = CalendarAPI(mock_client)
        events = await api.get_events()
        event = events[0]
        for field in ["id", "name", "description", "starts_at", "ends_at", "recurrence", "visible_in_church_center"]:
            assert field in event


class TestGetEventDetail:
    async def test_returns_full_detail(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_event.json")
        mock_client.get_all.side_effect = [
            load_fixture("get_event_instances.json")["data"],
            load_fixture("get_event_resources.json")["data"],
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
        mock_client.get.return_value = load_fixture("get_event.json")
        mock_client.get_all.return_value = []
        api = CalendarAPI(mock_client)
        await api.get_event_detail("201")
        assert mock_client.get.call_count == 1
        assert mock_client.get_all.call_count == 2
