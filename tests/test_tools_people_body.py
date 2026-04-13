"""Tests that invoke the actual tool function bodies for people tools.

These tests call the actual decorated tool functions via their .fn attribute,
after mocking get_access_token so that get_pco_client() returns a mock PCOClient.
"""
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
    """Mock get_access_token and patch PCOClient so get_pco_client() returns our mock."""
    with patch(
        "pco_mcp.tools._context.get_access_token",
        return_value=_fake_access_token(),
    ), patch(
        "pco_mcp.tools._context.PCOClient",
        return_value=mock_client,
    ):
        yield


def _get_tool_fn(mcp, name):
    """Return the raw async function for a named tool."""
    for k, v in mcp._local_provider._components.items():
        if k.startswith("tool:") and v.name == name:
            return v.fn
    raise KeyError(f"Tool {name!r} not found")


def make_mcp():
    from fastmcp import FastMCP
    from pco_mcp.tools.people import register_people_tools

    mcp = FastMCP("test")
    register_people_tools(mcp)
    return mcp


class TestSearchPeopleToolBody:
    async def test_calls_api_and_returns_results(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [
                {
                    "type": "Person",
                    "id": "1001",
                    "attributes": {
                        "first_name": "Alice",
                        "last_name": "Smith",
                        "email_addresses": [{"address": "alice@example.com"}],
                        "phone_numbers": [],
                        "membership": "Member",
                        "status": "active",
                    },
                }
            ]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "search_people")
        results = await fn(name="Alice")
        assert len(results) == 1
        assert results[0]["first_name"] == "Alice"

    async def test_search_with_email(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {"data": []}
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "search_people")
        results = await fn(email="alice@example.com")
        assert results == []

    async def test_search_with_phone(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {"data": []}
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "search_people")
        results = await fn(phone="555-0101")
        assert results == []


class TestGetPersonToolBody:
    async def test_get_person_by_id(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": {
                "type": "Person",
                "id": "1001",
                "attributes": {
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "email_addresses": [],
                    "phone_numbers": [],
                    "membership": "Member",
                    "status": "active",
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "get_person")
        person = await fn(person_id="1001")
        assert person["id"] == "1001"
        assert person["first_name"] == "Alice"


class TestListListsToolBody:
    async def test_list_lists_returns_lists(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [
                {
                    "type": "List",
                    "id": "10",
                    "attributes": {
                        "name": "Volunteers",
                        "description": "All volunteers",
                        "total_count": 45,
                    },
                }
            ]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_lists")
        lists = await fn()
        assert len(lists) == 1
        assert lists[0]["name"] == "Volunteers"


class TestGetListMembersToolBody:
    async def test_get_list_members(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [
                {
                    "type": "Person",
                    "id": "1001",
                    "attributes": {
                        "first_name": "Alice",
                        "last_name": "Smith",
                        "email_addresses": [],
                        "phone_numbers": [],
                        "membership": "Member",
                        "status": "active",
                    },
                }
            ]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "get_list_members")
        members = await fn(list_id="42")
        assert len(members) == 1
        assert members[0]["first_name"] == "Alice"


class TestCreatePersonToolBody:
    async def test_create_person(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Person",
                "id": "1099",
                "attributes": {
                    "first_name": "New",
                    "last_name": "Person",
                    "email_addresses": [],
                    "phone_numbers": [],
                    "membership": None,
                    "status": "active",
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "create_person")
        person = await fn(first_name="New", last_name="Person")
        assert person["id"] == "1099"
        assert person["first_name"] == "New"


class TestUpdatePersonToolBody:
    async def test_update_person_with_first_name(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "Person",
                "id": "1001",
                "attributes": {
                    "first_name": "Alicia",
                    "last_name": "Smith",
                    "email_addresses": [],
                    "phone_numbers": [],
                    "membership": "Member",
                    "status": "active",
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_person")
        person = await fn(person_id="1001", first_name="Alicia")
        assert person["first_name"] == "Alicia"

    async def test_update_person_skips_none_fields(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "Person",
                "id": "1001",
                "attributes": {
                    "first_name": "Alice",
                    "last_name": "NewLastName",
                    "email_addresses": [],
                    "phone_numbers": [],
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_person")
        # first_name=None should be skipped; only last_name passed
        person = await fn(person_id="1001", first_name=None, last_name="NewLastName")
        call_kwargs = mock_client.patch.call_args.kwargs
        attrs = call_kwargs["data"]["data"]["attributes"]
        assert "first_name" not in attrs
        assert "last_name" in attrs


class TestAddEmailToolBody:
    async def test_add_email(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Email",
                "id": "2001",
                "attributes": {
                    "address": "alice@example.com",
                    "location": "Home",
                    "primary": True,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "add_email")
        email = await fn(person_id="1001", address="alice@example.com", location="Home")
        assert email["id"] == "2001"
        assert email["address"] == "alice@example.com"


class TestUpdateEmailToolBody:
    async def test_update_email(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "Email",
                "id": "2001",
                "attributes": {
                    "address": "alice@work.com",
                    "location": "Work",
                    "primary": False,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_email")
        email = await fn(person_id="1001", email_id="2001", location="Work")
        assert email["location"] == "Work"


class TestAddPhoneNumberToolBody:
    async def test_add_phone_number(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "PhoneNumber",
                "id": "3001",
                "attributes": {"number": "5550101", "carrier": None, "location": "Mobile", "primary": True},
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "add_phone_number")
        phone = await fn(person_id="1001", number="5550101", location="Mobile")
        assert phone["id"] == "3001"


class TestAddAddressToolBody:
    async def test_add_address(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {"type": "Address", "id": "4001", "attributes": {"street": "123 Main St", "city": "Springfield", "state": "IL", "zip": "62701", "location": "Home", "primary": True}}
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "add_address")
        addr = await fn(person_id="1001", street="123 Main St", city="Springfield", state="IL", zip_code="62701")
        assert addr["id"] == "4001"
        assert addr["city"] == "Springfield"


class TestUpdateAddressToolBody:
    async def test_update_address(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {"type": "Address", "id": "4001", "attributes": {"street": "456 Oak Ave", "city": "Springfield", "state": "IL", "zip": "62702", "location": "Work", "primary": False}}
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_address")
        addr = await fn(person_id="1001", address_id="4001", street="456 Oak Ave")
        assert addr["street"] == "456 Oak Ave"


class TestListPersonDetailsToolBody:
    async def test_list_person_details(self, mock_client: AsyncMock) -> None:
        mock_client.get.side_effect = [
            {"data": [{"type": "Email", "id": "2001", "attributes": {"address": "a@b.com", "location": "Home", "primary": True}}]},
            {"data": [{"type": "PhoneNumber", "id": "3001", "attributes": {"number": "555", "carrier": None, "location": "Mobile", "primary": True}}]},
            {"data": [{"type": "Address", "id": "4001", "attributes": {"street": "123 St", "city": "Town", "state": "IL", "zip": "60000", "location": "Home", "primary": True}}]},
        ]
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_person_details")
        details = await fn(person_id="1001")
        assert "emails" in details
        assert "phone_numbers" in details
        assert "addresses" in details


class TestAddNoteToolBody:
    async def test_add_note(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {"type": "Note", "id": "5001", "attributes": {"note": "Test note.", "created_at": "2026-04-13T10:00:00Z", "note_category_id": None}}
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "add_note")
        note = await fn(person_id="1001", note="Test note.")
        assert note["id"] == "5001"


class TestListNotesToolBody:
    async def test_list_notes(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [{"type": "Note", "id": "5001", "attributes": {"note": "A note.", "created_at": "2026-04-13T10:00:00Z", "note_category_id": "100"}}]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_notes")
        notes = await fn(person_id="1001")
        assert len(notes) == 1
        assert notes[0]["note"] == "A note."


class TestAddBlockoutToolBody:
    async def test_add_blockout(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {"type": "Blockout", "id": "6001", "attributes": {"description": "Vacation", "reason": "", "starts_at": "2026-04-20T00:00:00Z", "ends_at": "2026-04-27T00:00:00Z", "repeat_frequency": "no_repeat", "repeat_until": None}}
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "add_blockout")
        blockout = await fn(person_id="1001", description="Vacation", starts_at="2026-04-20T00:00:00Z", ends_at="2026-04-27T00:00:00Z")
        assert blockout["id"] == "6001"
        assert blockout["description"] == "Vacation"


class TestUpdatePhoneNumberToolBody:
    async def test_update_phone_number(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "PhoneNumber",
                "id": "3001",
                "attributes": {"number": "5550202", "carrier": None, "location": "Work", "primary": False},
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_phone_number")
        phone = await fn(person_id="1001", phone_id="3001", location="Work")
        assert phone["location"] == "Work"


class TestListWorkflowsToolBody:
    async def test_list_workflows(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [{"type": "Workflow", "id": "7001", "attributes": {"name": "New Member Follow-up", "completed_card_count": 12, "ready_card_count": 3, "total_cards_count": 15}}]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_workflows")
        workflows = await fn()
        assert len(workflows) == 1
        assert workflows[0]["name"] == "New Member Follow-up"


class TestAddPersonToWorkflowToolBody:
    async def test_add_person_to_workflow(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {"type": "Card", "id": "8001", "attributes": {"stage": "Ready", "created_at": "2026-04-13T10:00:00Z", "completed_at": None}, "relationships": {"person": {"data": {"type": "Person", "id": "1001"}}}}
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "add_person_to_workflow")
        card = await fn(workflow_id="7001", person_id="1001")
        assert card["id"] == "8001"
        assert card["stage"] == "Ready"
