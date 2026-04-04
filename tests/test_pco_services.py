import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.services import ServicesAPI

FIXTURES = Path(__file__).parent / "fixtures" / "services"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def mock_client() -> PCOClient:
    return AsyncMock(spec=PCOClient)


class TestListServiceTypes:
    async def test_returns_simplified_types(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_service_types.json")
        api = ServicesAPI(mock_client)
        types = await api.list_service_types()
        assert len(types) == 2
        assert types[0]["name"] == "Sunday Morning"
        assert types[0]["id"] == "201"


class TestGetUpcomingPlans:
    async def test_returns_plans(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_upcoming_plans.json")
        api = ServicesAPI(mock_client)
        plans = await api.get_upcoming_plans("201")
        assert len(plans) == 1
        assert plans[0]["title"] == "Easter Service"
        mock_client.get.assert_called_once()
        call_path = mock_client.get.call_args.args[0]
        assert "201" in call_path


class TestListSongs:
    async def test_returns_songs(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_songs.json")
        api = ServicesAPI(mock_client)
        songs = await api.list_songs()
        assert len(songs) == 1
        assert songs[0]["title"] == "Amazing Grace"
        assert songs[0]["author"] == "John Newton"
