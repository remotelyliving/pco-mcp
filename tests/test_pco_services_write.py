"""Tests for ServicesAPI.get_plan_details, list_team_members, schedule_team_member."""
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


class TestGetPlanDetails:
    def _setup_get_side_effect(self, mock_client: AsyncMock) -> None:
        """Set up mock to return plan details, empty items, and empty team members."""
        plan_fixture = load_fixture("get_plan_details.json")
        empty_list = {"data": []}
        mock_client.get.side_effect = [plan_fixture, empty_list, empty_list]

    async def test_returns_simplified_plan(self, mock_client: AsyncMock) -> None:
        self._setup_get_side_effect(mock_client)
        api = ServicesAPI(mock_client)
        plan = await api.get_plan_details("201", "301")
        assert plan["id"] == "301"
        assert plan["title"] == "Easter Service"
        assert plan["dates"] == "April 20, 2026"
        assert plan["items_count"] == 12
        assert "items" in plan
        assert "team_members" in plan

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        self._setup_get_side_effect(mock_client)
        api = ServicesAPI(mock_client)
        await api.get_plan_details("201", "301")
        # First call is the base plan endpoint
        call_path = mock_client.get.call_args_list[0].args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "service_types" in call_path

    async def test_returns_needed_positions(self, mock_client: AsyncMock) -> None:
        self._setup_get_side_effect(mock_client)
        api = ServicesAPI(mock_client)
        plan = await api.get_plan_details("201", "301")
        assert "needed_positions_count" in plan
        assert plan["needed_positions_count"] == 3


class TestListTeamMembers:
    async def test_returns_team_members(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_team_members.json")
        api = ServicesAPI(mock_client)
        members = await api.list_team_members("201", "301")
        assert len(members) == 2
        assert members[0]["person_name"] == "Alice Smith"
        assert members[0]["team_position_name"] == "Vocalist"
        assert members[1]["person_name"] == "Bob Jones"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_team_members.json")
        api = ServicesAPI(mock_client)
        await api.list_team_members("201", "301")
        call_path = mock_client.get.call_args.args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "team_members" in call_path

    async def test_returns_status_field(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_team_members.json")
        api = ServicesAPI(mock_client)
        members = await api.list_team_members("201", "301")
        assert "status" in members[0]


class TestScheduleTeamMember:
    async def test_returns_simplified_team_member(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("schedule_team_member.json")
        api = ServicesAPI(mock_client)
        result = await api.schedule_team_member("201", "301", "1003", "Pianist")
        assert result["id"] == "503"
        assert result["person_name"] == "Carol Davis"
        assert result["team_position_name"] == "Pianist"

    async def test_posts_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("schedule_team_member.json")
        api = ServicesAPI(mock_client)
        await api.schedule_team_member("201", "301", "1003", "Pianist")
        call_path = mock_client.post.call_args.args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "team_members" in call_path

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("schedule_team_member.json")
        api = ServicesAPI(mock_client)
        await api.schedule_team_member("201", "301", "1003", "Pianist")
        call_kwargs = mock_client.post.call_args.kwargs
        data = call_kwargs["data"]
        assert data["data"]["type"] == "PlanPerson"
        attrs = data["data"]["attributes"]
        assert attrs["person_id"] == 1003  # cast to int
        assert attrs["team_position_name"] == "Pianist"
