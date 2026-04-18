"""Tests for PeopleAPI.create_person, update_person, get_list_members."""
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
    return AsyncMock(spec=PCOClient)


class TestGetListMembers:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_list_members.json")["data"],
            total_count=2, truncated=False,
        )
        api = PeopleAPI(mock_client)
        result = await api.get_list_members("42")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        assert len(result["items"]) == 2
        assert result["items"][0]["first_name"] == "Alice"
        assert result["items"][1]["first_name"] == "Carol"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_list_members.json")["data"],
            total_count=2, truncated=False,
        )
        api = PeopleAPI(mock_client)
        await api.get_list_members("42")
        call_path = mock_client.get_all.call_args.args[0]
        assert "/people/v2/lists/42/people" in call_path

    async def test_returns_simplified_records(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_list_members.json")["data"],
            total_count=2, truncated=False,
        )
        api = PeopleAPI(mock_client)
        result = await api.get_list_members("42")
        record = result["items"][0]
        assert "id" in record
        assert "first_name" in record
        assert "last_name" in record
        assert "emails" in record


class TestCreatePerson:
    async def test_create_person_returns_simplified_record(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_person.json")
        api = PeopleAPI(mock_client)
        person = await api.create_person("New", "Person", email="new@example.com")
        assert person["id"] == "1099"
        assert person["first_name"] == "New"
        assert person["last_name"] == "Person"
        assert person["emails"][0]["address"] == "new@example.com"

    async def test_create_person_posts_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_person.json")
        api = PeopleAPI(mock_client)
        await api.create_person("New", "Person")
        call_path = mock_client.post.call_args.args[0]
        assert "/people/v2/people" in call_path

    async def test_create_person_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_person.json")
        api = PeopleAPI(mock_client)
        await api.create_person("New", "Person", email="new@example.com")
        call_kwargs = mock_client.post.call_args.kwargs
        data = call_kwargs["data"]
        assert data["data"]["type"] == "Person"
        attrs = data["data"]["attributes"]
        assert attrs["first_name"] == "New"
        assert attrs["last_name"] == "Person"
        assert "email_addresses" in attrs

    async def test_create_person_without_email(self, mock_client: AsyncMock) -> None:
        # Without email, payload should not include email_addresses
        mock_client.post.return_value = load_fixture("create_person.json")
        api = PeopleAPI(mock_client)
        await api.create_person("New", "Person")
        call_kwargs = mock_client.post.call_args.kwargs
        data = call_kwargs["data"]
        attrs = data["data"]["attributes"]
        assert "email_addresses" not in attrs


class TestUpdatePerson:
    async def test_update_person_returns_simplified_record(self, mock_client: AsyncMock) -> None:
        updated_fixture = {
            "data": {
                "type": "Person",
                "id": "1001",
                "attributes": {
                    "first_name": "Alicia",
                    "last_name": "Smith",
                    "email_addresses": [{"address": "alice@example.com"}],
                    "phone_numbers": [],
                    "membership": "Member",
                    "status": "active",
                },
            }
        }
        mock_client.patch.return_value = updated_fixture
        api = PeopleAPI(mock_client)
        person = await api.update_person("1001", first_name="Alicia")
        assert person["id"] == "1001"
        assert person["first_name"] == "Alicia"

    async def test_update_person_patches_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "Person",
                "id": "1001",
                "attributes": {
                    "first_name": "Alicia",
                    "last_name": "Smith",
                    "email_addresses": [],
                    "phone_numbers": [],
                },
            }
        }
        api = PeopleAPI(mock_client)
        await api.update_person("1001", first_name="Alicia")
        call_path = mock_client.patch.call_args.args[0]
        assert "/people/v2/people/1001" in call_path

    async def test_update_person_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "Person",
                "id": "1001",
                "attributes": {
                    "first_name": "Alicia",
                    "last_name": "Smith",
                    "email_addresses": [],
                    "phone_numbers": [],
                },
            }
        }
        api = PeopleAPI(mock_client)
        await api.update_person("1001", first_name="Alicia", last_name="Jones")
        call_kwargs = mock_client.patch.call_args.kwargs
        data = call_kwargs["data"]
        assert data["data"]["type"] == "Person"
        assert data["data"]["id"] == "1001"
        attrs = data["data"]["attributes"]
        assert attrs["first_name"] == "Alicia"
        assert attrs["last_name"] == "Jones"
