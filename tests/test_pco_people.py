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


class TestSimplifyPersonIncludesBirthdateGender:
    async def test_get_person_includes_birthdate(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_person.json")
        api = PeopleAPI(mock_client)
        person = await api.get_person("1001")
        assert "birthdate" in person
        assert person["birthdate"] == "1990-05-15"

    async def test_get_person_includes_gender(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_person.json")
        api = PeopleAPI(mock_client)
        person = await api.get_person("1001")
        assert "gender" in person
        assert person["gender"] == "Female"


class TestGetPersonBlockouts:
    async def test_returns_blockouts(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_person_blockouts.json")
        api = PeopleAPI(mock_client)
        blockouts = await api.get_person_blockouts("1001")
        assert len(blockouts) == 2
        assert blockouts[0]["description"] == "Vacation"
        assert blockouts[0]["reason"] == "Out of town"
        assert blockouts[1]["repeat_frequency"] == "weekly"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_person_blockouts.json")
        api = PeopleAPI(mock_client)
        await api.get_person_blockouts("1001")
        mock_client.get.assert_called_once_with("/people/v2/people/1001/blockouts")

    async def test_blockout_has_expected_fields(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_person_blockouts.json")
        api = PeopleAPI(mock_client)
        blockouts = await api.get_person_blockouts("1001")
        b = blockouts[0]
        assert "id" in b
        assert "description" in b
        assert "starts_at" in b
        assert "ends_at" in b
        assert "repeat_frequency" in b

    async def test_returns_empty_list_when_no_blockouts(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {"data": [], "meta": {"total_count": 0, "count": 0}}
        api = PeopleAPI(mock_client)
        blockouts = await api.get_person_blockouts("9999")
        assert blockouts == []


class TestAddEmail:
    async def test_returns_created_email(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_email.json")
        api = PeopleAPI(mock_client)
        email = await api.add_email("1001", address="alice@example.com", location="Home", is_primary=True)
        assert email["id"] == "2001"
        assert email["address"] == "alice@example.com"
        assert email["location"] == "Home"
        assert email["primary"] is True

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_email.json")
        api = PeopleAPI(mock_client)
        await api.add_email("1001", address="alice@example.com")
        call_path = mock_client.post.call_args.args[0]
        assert "1001" in call_path
        assert "/emails" in call_path
        data = mock_client.post.call_args.kwargs["data"]
        assert data["data"]["type"] == "Email"
        assert data["data"]["attributes"]["address"] == "alice@example.com"

    async def test_only_required_fields(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_email.json")
        api = PeopleAPI(mock_client)
        await api.add_email("1001", address="alice@example.com")
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert "address" in attrs
        assert "location" not in attrs
        assert "primary" not in attrs


class TestUpdateEmail:
    async def test_returns_updated_email(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_email.json")
        api = PeopleAPI(mock_client)
        email = await api.update_email("1001", "2001", address="alice@work.com", location="Work")
        assert email["address"] == "alice@work.com"
        assert email["location"] == "Work"

    async def test_sends_patch_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_email.json")
        api = PeopleAPI(mock_client)
        await api.update_email("1001", "2001", location="Work")
        call_path = mock_client.patch.call_args.args[0]
        assert "1001" in call_path
        assert "2001" in call_path
        assert "/emails/" in call_path
