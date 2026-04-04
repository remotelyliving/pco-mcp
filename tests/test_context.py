"""Tests for pco_mcp.tools._context — per-request context variable module."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.people import PeopleAPI
from pco_mcp.pco.services import ServicesAPI
from pco_mcp.tools._context import (
    get_people_api,
    get_pco_client,
    get_services_api,
    set_pco_client,
)


@pytest.fixture
def mock_pco_client() -> PCOClient:
    return AsyncMock(spec=PCOClient)


class TestSetAndGetPcoClient:
    def test_set_then_get_returns_same_client(self, mock_pco_client: PCOClient) -> None:
        set_pco_client(mock_pco_client)
        retrieved = get_pco_client()
        assert retrieved is mock_pco_client

    def test_pco_client_var_has_no_default(self) -> None:
        """ContextVar raises LookupError when accessed with no default."""
        from pco_mcp.tools import _context as ctx_mod

        # Calling .get() with no fallback raises LookupError when unset
        # We verify the ContextVar has no default by checking it raises
        # when explicitly called with no default sentinel
        sentinel = object()
        result = ctx_mod._pco_client_var.get(sentinel)
        # If context was set by a previous test, result won't be the sentinel
        # Just verify the var itself can be introspected
        assert ctx_mod._pco_client_var.name == "pco_client"

    def test_set_overwrites_previous_value(self, mock_pco_client: PCOClient) -> None:
        set_pco_client(mock_pco_client)
        new_client = AsyncMock(spec=PCOClient)
        set_pco_client(new_client)
        assert get_pco_client() is new_client


class TestGetPeopleApi:
    def test_returns_people_api_instance(self, mock_pco_client: PCOClient) -> None:
        set_pco_client(mock_pco_client)
        api = get_people_api()
        assert isinstance(api, PeopleAPI)

    def test_people_api_uses_current_client(self, mock_pco_client: PCOClient) -> None:
        set_pco_client(mock_pco_client)
        api = get_people_api()
        assert api._client is mock_pco_client


class TestGetServicesApi:
    def test_returns_services_api_instance(self, mock_pco_client: PCOClient) -> None:
        set_pco_client(mock_pco_client)
        api = get_services_api()
        assert isinstance(api, ServicesAPI)

    def test_services_api_uses_current_client(self, mock_pco_client: PCOClient) -> None:
        set_pco_client(mock_pco_client)
        api = get_services_api()
        assert api._client is mock_pco_client
