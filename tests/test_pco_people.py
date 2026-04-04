import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.people import PeopleAPI

FIXTURES = Path(__file__).parent / "fixtures" / "people"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def mock_client() -> PCOClient:
    client = AsyncMock(spec=PCOClient)
    return client


class TestSearchPeople:
    async def test_search_by_name(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("search_people.json")
        api = PeopleAPI(mock_client)
        results = await api.search_people(name="Alice")
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "/people/v2/people" in call_args.args[0]
        assert len(results) == 2
        assert results[0]["first_name"] == "Alice"

    async def test_search_returns_simplified_records(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("search_people.json")
        api = PeopleAPI(mock_client)
        results = await api.search_people(name="Alice")
        record = results[0]
        assert "id" in record
        assert "first_name" in record
        assert "last_name" in record
        assert "email" in record


class TestGetPerson:
    async def test_get_by_id(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_person.json")
        api = PeopleAPI(mock_client)
        person = await api.get_person("1001")
        mock_client.get.assert_called_once_with("/people/v2/people/1001")
        assert person["first_name"] == "Alice"
        assert person["id"] == "1001"


class TestListLists:
    async def test_returns_lists(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_lists.json")
        api = PeopleAPI(mock_client)
        lists = await api.list_lists()
        assert len(lists) == 2
        assert lists[0]["name"] == "Volunteers"
        assert lists[0]["total_count"] == 45
