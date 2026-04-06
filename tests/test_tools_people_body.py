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
