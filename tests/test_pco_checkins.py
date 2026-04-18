import json
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from pco_mcp.pco.client import PCOClient, PagedResult
from pco_mcp.pco.checkins import CheckInsAPI

FIXTURES = Path(__file__).parent / "fixtures" / "checkins"

def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())

@pytest.fixture
def mock_client() -> PCOClient:
    return AsyncMock(spec=PCOClient)


class TestGetEvents:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_events.json")["data"],
            total_count=2,
            truncated=False,
        )
        api = CheckInsAPI(mock_client)
        result = await api.get_events()
        assert "items" in result
        assert "meta" in result
        assert len(result["items"]) == 2
        assert result["items"][0]["name"] == "Sunday Morning"
        assert result["items"][0]["id"] == "101"
        assert result["meta"]["total_count"] == 2
        assert result["meta"]["truncated"] is False
        assert result["meta"]["filters_applied"].get("where[archived_at]") == ""

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_events.json")["data"],
            total_count=2,
            truncated=False,
        )
        api = CheckInsAPI(mock_client)
        await api.get_events()
        call_path = mock_client.get_all.call_args.args[0]
        assert "/check-ins/v2/events" in call_path

    async def test_event_has_expected_fields(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_events.json")["data"],
            total_count=2,
            truncated=False,
        )
        api = CheckInsAPI(mock_client)
        result = await api.get_events()
        event = result["items"][0]
        assert "id" in event
        assert "name" in event
        assert "frequency" in event
        assert "created_at" in event
        assert "archived" in event

    async def test_include_archived_drops_default(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(
            items=[], total_count=0, truncated=False,
        )
        api = CheckInsAPI(mock_client)
        result = await api.get_events(include_archived=True)
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "where[archived_at]" not in call_params
        assert "where[archived_at]" not in result["meta"]["filters_applied"]


class TestGetEventCheckins:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_event_checkins.json")["data"],
            total_count=2,
            truncated=False,
        )
        api = CheckInsAPI(mock_client)
        result = await api.get_event_checkins("101")
        assert "items" in result
        assert len(result["items"]) == 2
        assert result["items"][0]["first_name"] == "Alice"
        assert result["items"][0]["security_code"] == "ABC123"
        assert result["meta"]["total_count"] == 2

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CheckInsAPI(mock_client)
        await api.get_event_checkins("101")
        call_path = mock_client.get_all.call_args.args[0]
        assert "101" in call_path
        assert "/check_ins" in call_path

    async def test_passes_date_filters(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CheckInsAPI(mock_client)
        result = await api.get_event_checkins("101", start_date="2026-01-01", end_date="2026-04-01")
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert call_params.get("where[created_at][gte]") == "2026-01-01"
        assert call_params.get("where[created_at][lte]") == "2026-04-01"
        assert result["meta"]["filters_applied"].get("where[created_at][gte]") == "2026-01-01"
        assert result["meta"]["filters_applied"].get("where[created_at][lte]") == "2026-04-01"


class TestGetHeadcounts:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_event_periods.json")["data"],
            total_count=2,
            truncated=False,
        )
        mock_client.get.side_effect = [
            load_fixture("get_headcounts_period1.json"),
            load_fixture("get_headcounts_period2.json"),
        ]
        api = CheckInsAPI(mock_client)
        result = await api.get_headcounts("101")
        assert "items" in result
        assert len(result["items"]) == 2
        assert result["items"][0]["total"] == 195
        assert result["items"][0]["by_location"]["Main Sanctuary"] == 150
        assert result["items"][0]["by_location"]["Kids"] == 45
        assert result["items"][1]["total"] == 130
        assert result["items"][1]["by_location"]["Main Sanctuary"] == 130

    async def test_calls_event_periods_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CheckInsAPI(mock_client)
        await api.get_headcounts("101")
        call_path = mock_client.get_all.call_args.args[0]
        assert "101" in call_path
        assert "/event_periods" in call_path

    async def test_passes_date_filters_to_periods(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CheckInsAPI(mock_client)
        result = await api.get_headcounts("101", start_date="2026-04-01", end_date="2026-04-30")
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert call_params.get("where[starts_at][gte]") == "2026-04-01"
        assert call_params.get("where[starts_at][lte]") == "2026-04-30"
        assert result["meta"]["filters_applied"].get("where[starts_at][gte]") == "2026-04-01"

    async def test_empty_periods_returns_empty_envelope(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = CheckInsAPI(mock_client)
        result = await api.get_headcounts("101")
        assert result["items"] == []
        assert result["meta"]["total_count"] == 0
