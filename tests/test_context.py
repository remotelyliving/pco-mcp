"""Tests for pco_mcp.tools._context — per-request context module."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.people import PeopleAPI
from pco_mcp.pco.services import ServicesAPI


def _fake_access_token(token: str = "test-pco-token"):
    """Build a mock AccessToken whose .token returns *token*."""
    at = MagicMock()
    at.token = token
    return at


class TestGetPcoClient:
    def test_builds_client_from_access_token(self) -> None:
        with patch(
            "pco_mcp.tools._context.get_access_token",
            return_value=_fake_access_token("my-token"),
        ):
            from pco_mcp.tools._context import get_pco_client

            client = get_pco_client()
        assert isinstance(client, PCOClient)
        assert client._access_token == "my-token"

    def test_raises_when_no_access_token(self) -> None:
        with patch(
            "pco_mcp.tools._context.get_access_token",
            return_value=None,
        ):
            from pco_mcp.tools._context import get_pco_client

            with pytest.raises(RuntimeError, match="No authenticated"):
                get_pco_client()


class TestGetPeopleApi:
    def test_returns_people_api_instance(self) -> None:
        with patch(
            "pco_mcp.tools._context.get_access_token",
            return_value=_fake_access_token(),
        ):
            from pco_mcp.tools._context import get_people_api

            api = get_people_api()
        assert isinstance(api, PeopleAPI)


class TestGetServicesApi:
    def test_returns_services_api_instance(self) -> None:
        with patch(
            "pco_mcp.tools._context.get_access_token",
            return_value=_fake_access_token(),
        ):
            from pco_mcp.tools._context import get_services_api

            api = get_services_api()
        assert isinstance(api, ServicesAPI)
