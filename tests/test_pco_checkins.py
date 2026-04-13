import json
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.checkins import CheckInsAPI

FIXTURES = Path(__file__).parent / "fixtures" / "checkins"

def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())

@pytest.fixture
def mock_client() -> PCOClient:
    return AsyncMock(spec=PCOClient)


class TestGetEvents:
    async def test_returns_events(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_events.json")
        api = CheckInsAPI(mock_client)
        events = await api.get_events()
        assert len(events) == 2
        assert events[0]["name"] == "Sunday Morning"
        assert events[0]["id"] == "101"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_events.json")
        api = CheckInsAPI(mock_client)
        await api.get_events()
        call_path = mock_client.get.call_args.args[0]
        assert "/check-ins/v2/events" in call_path

    async def test_event_has_expected_fields(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_events.json")
        api = CheckInsAPI(mock_client)
        events = await api.get_events()
        event = events[0]
        assert "id" in event
        assert "name" in event
        assert "frequency" in event
        assert "created_at" in event
        assert "archived" in event


class TestGetEventCheckins:
    async def test_returns_checkins(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = load_fixture("get_event_checkins.json")["data"]
        api = CheckInsAPI(mock_client)
        checkins = await api.get_event_checkins("101")
        assert len(checkins) == 2
        assert checkins[0]["first_name"] == "Alice"
        assert checkins[0]["security_code"] == "ABC123"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = []
        api = CheckInsAPI(mock_client)
        await api.get_event_checkins("101")
        call_path = mock_client.get_all.call_args.args[0]
        assert "101" in call_path
        assert "/check_ins" in call_path

    async def test_passes_date_filters(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = []
        api = CheckInsAPI(mock_client)
        await api.get_event_checkins("101", start_date="2026-04-01", end_date="2026-04-30")
        call_kwargs = mock_client.get_all.call_args.kwargs
        params = call_kwargs.get("params", {})
        assert params.get("where[created_at][gte]") == "2026-04-01"
        assert params.get("where[created_at][lte]") == "2026-04-30"

    async def test_caps_at_500_records(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = []
        api = CheckInsAPI(mock_client)
        await api.get_event_checkins("101")
        call_kwargs = mock_client.get_all.call_args.kwargs
        assert call_kwargs.get("max_pages", 50) <= 20
