"""Tests for PeopleAPI.create_person, update_person, get_list_members."""
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from pco_mcp.pco.client import PCOAPIError, PCOClient
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
        # Happy path: one POST for the person, one POST for the email.
        person_fixture = load_fixture("create_person.json")
        email_fixture = {"data": {"type": "Email", "id": "999", "attributes": {}}}
        mock_client.post.side_effect = [person_fixture, email_fixture]
        api = PeopleAPI(mock_client)
        person = await api.create_person("New", "Person", email="new@example.com")
        assert person["id"] == "1099"
        assert person["first_name"] == "New"
        assert person["last_name"] == "Person"
        assert person["emails"][0]["address"] == "new@example.com"
        assert person["emails"][0]["location"] == "Home"
        assert person["emails"][0]["primary"] is True

    async def test_create_person_posts_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_person.json")
        api = PeopleAPI(mock_client)
        await api.create_person("New", "Person")
        call_path = mock_client.post.call_args.args[0]
        assert "/people/v2/people" in call_path

    async def test_create_person_body_omits_email_addresses(
        self, mock_client: AsyncMock
    ) -> None:
        """PCO rejects ``email_addresses`` in the Person POST body, so we never
        include it — even when an email is provided."""
        person_fixture = load_fixture("create_person.json")
        email_fixture = {"data": {"type": "Email", "id": "999", "attributes": {}}}
        mock_client.post.side_effect = [person_fixture, email_fixture]
        api = PeopleAPI(mock_client)
        await api.create_person("New", "Person", email="new@example.com")
        # First POST is the person create — inspect its payload
        first_call = mock_client.post.call_args_list[0]
        data = first_call.kwargs["data"]
        assert data["data"]["type"] == "Person"
        attrs = data["data"]["attributes"]
        assert attrs["first_name"] == "New"
        assert attrs["last_name"] == "Person"
        assert "email_addresses" not in attrs

    async def test_create_person_without_email(self, mock_client: AsyncMock) -> None:
        # Without email, only the person POST happens — no emails POST.
        mock_client.post.return_value = load_fixture("create_person.json")
        api = PeopleAPI(mock_client)
        await api.create_person("New", "Person")
        assert mock_client.post.call_count == 1
        call_kwargs = mock_client.post.call_args.kwargs
        attrs = call_kwargs["data"]["data"]["attributes"]
        assert "email_addresses" not in attrs

    async def test_create_person_posts_email_separately(
        self, mock_client: AsyncMock
    ) -> None:
        """With email provided, a second POST to /emails must fire."""
        person_fixture = load_fixture("create_person.json")
        email_fixture = {"data": {"type": "Email", "id": "999", "attributes": {}}}
        mock_client.post.side_effect = [person_fixture, email_fixture]
        api = PeopleAPI(mock_client)
        await api.create_person("New", "Person", email="new@example.com")
        assert mock_client.post.call_count == 2
        second_call = mock_client.post.call_args_list[1]
        assert "/people/v2/people/1099/emails" in second_call.args[0]
        email_payload = second_call.kwargs["data"]
        assert email_payload["data"]["type"] == "Email"
        assert email_payload["data"]["attributes"]["address"] == "new@example.com"

    async def test_create_person_email_422_returns_warning(
        self, mock_client: AsyncMock
    ) -> None:
        """When the separate /emails POST returns 422 (email in use), the
        person is returned with a ``_warning`` note instead of raising."""
        person_fixture = load_fixture("create_person.json")
        mock_client.post.side_effect = [
            person_fixture,
            PCOAPIError(422, "email is taken"),
        ]
        api = PeopleAPI(mock_client)
        person = await api.create_person("New", "Person", email="taken@example.com")
        assert person["id"] == "1099"
        assert "_warning" in person
        assert "taken@example.com" in person["_warning"]

    async def test_create_person_email_fallback_uses_emails_array(
        self, mock_client: AsyncMock
    ) -> None:
        """Compatibility with the prior fallback shape — after a successful
        separate-email POST, the returned person dict uses the ``emails:
        [{...}]`` array shape (not a top-level ``email`` key)."""
        person_fixture = load_fixture("create_person.json")
        email_fixture = {"data": {"type": "Email", "id": "999", "attributes": {}}}
        mock_client.post.side_effect = [person_fixture, email_fixture]
        api = PeopleAPI(mock_client)
        person = await api.create_person("New", "Person", email="new@example.com")
        assert "email" not in person
        assert person["emails"] == [
            {"address": "new@example.com", "location": "Home", "primary": True}
        ]


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
