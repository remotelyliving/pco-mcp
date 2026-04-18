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
    def _setup_mocks(self, mock_client: AsyncMock) -> None:
        """Mock plan detail (single .get) + items/team_members (paginated .get_all)."""
        from pco_mcp.pco.client import PagedResult
        mock_client.get.return_value = load_fixture("get_plan_details.json")
        mock_client.get_all.side_effect = [
            PagedResult(items=[], total_count=0, truncated=False),  # items
            PagedResult(items=[], total_count=0, truncated=False),  # team_members
        ]

    async def test_returns_single_resource_dict_with_nested_lists(
        self, mock_client: AsyncMock,
    ) -> None:
        self._setup_mocks(mock_client)
        api = ServicesAPI(mock_client)
        plan = await api.get_plan_details("201", "301")
        assert plan["id"] == "301"
        assert plan["title"] == "Easter Service"
        assert plan["dates"] == "April 20, 2026"
        assert plan["items_count"] == 12
        assert "items" in plan
        assert "team_members" in plan
        # Confirm nested lists are bare arrays, NOT envelopes
        assert isinstance(plan["items"], list)
        assert isinstance(plan["team_members"], list)
        # And the composite is NOT itself an envelope
        assert "meta" not in plan

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        self._setup_mocks(mock_client)
        api = ServicesAPI(mock_client)
        await api.get_plan_details("201", "301")
        call_path = mock_client.get.call_args_list[0].args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "service_types" in call_path

    async def test_returns_needed_positions(self, mock_client: AsyncMock) -> None:
        self._setup_mocks(mock_client)
        api = ServicesAPI(mock_client)
        plan = await api.get_plan_details("201", "301")
        assert "needed_positions_count" in plan
        assert plan["needed_positions_count"] == 3

    async def test_team_members_include_params_sent(
        self, mock_client: AsyncMock,
    ) -> None:
        """get_plan_details hits the client directly and passes include= for
        both items (song,arrangement) and team_members (person,team_position)."""
        from pco_mcp.pco.client import PagedResult
        mock_client.get.return_value = load_fixture("get_plan_details.json")
        mock_client.get_all.side_effect = [
            PagedResult(items=[], total_count=0, truncated=False),  # items
            PagedResult(items=[], total_count=0, truncated=False),  # team_members
        ]
        api = ServicesAPI(mock_client)
        await api.get_plan_details("201", "301")
        # Second get_all call is team_members — check its include params
        team_call = mock_client.get_all.call_args_list[1]
        team_params = team_call.kwargs.get("params", {})
        assert "include" in team_params
        assert "person" in team_params["include"]
        assert "team_position" in team_params["include"]
        # First call is items — now sends include=song,arrangement
        items_call = mock_client.get_all.call_args_list[0]
        items_params = items_call.kwargs.get("params", {})
        assert "include" in items_params
        assert "song" in items_params["include"]
        assert "arrangement" in items_params["include"]

    async def test_items_flattened_via_items_included_index(
        self, mock_client: AsyncMock,
    ) -> None:
        """Items fetched via get_plan_details get song_id/arrangement_id from
        relationships and song_title/arrangement_name from the items-specific
        included array (separate from team_members' included)."""
        from pco_mcp.pco.client import PagedResult
        mock_client.get.return_value = load_fixture("get_plan_details.json")
        items_fixture = load_fixture("list_plan_items.json")
        mock_client.get_all.side_effect = [
            PagedResult(
                items=items_fixture["data"],
                total_count=3, truncated=False,
                included=items_fixture["included"],
            ),
            PagedResult(items=[], total_count=0, truncated=False),  # team_members
        ]
        api = ServicesAPI(mock_client)
        plan = await api.get_plan_details("201", "301")
        item = plan["items"][0]
        assert item["song_id"] == "1001"
        assert item["song_title"] == "Amazing Grace"
        assert item["arrangement_id"] == "2001"
        assert item["arrangement_name"] == "Standard"

    async def test_team_members_flattened_via_included_index(
        self, mock_client: AsyncMock,
    ) -> None:
        """Team members fetched via get_plan_details get person/team_position names flattened."""
        from pco_mcp.pco.client import PagedResult
        mock_client.get.return_value = load_fixture("get_plan_details.json")
        fixture = load_fixture("list_team_members.json")
        mock_client.get_all.side_effect = [
            PagedResult(items=[], total_count=0, truncated=False),  # items
            PagedResult(
                items=fixture["data"],
                total_count=2,
                truncated=False,
                included=fixture["included"],
            ),
        ]
        api = ServicesAPI(mock_client)
        plan = await api.get_plan_details("201", "301")
        tm = plan["team_members"][0]
        assert tm["person_id"] == "1001"
        assert tm["person_name"] == "Alice Smith"
        assert tm["team_position_id"] == "11"
        assert tm["team_position_name"] == "Vocalist"

    async def test_truncation_warns_but_does_not_raise(
        self, mock_client: AsyncMock, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """If items or team_members get_all truncates, log warning but still return plan."""
        import logging
        from pco_mcp.pco.client import PagedResult
        mock_client.get.return_value = load_fixture("get_plan_details.json")
        mock_client.get_all.side_effect = [
            PagedResult(items=[], total_count=None, truncated=True),  # items truncated
            PagedResult(items=[], total_count=0, truncated=False),  # team_members ok
        ]
        api = ServicesAPI(mock_client)
        with caplog.at_level(logging.WARNING):
            plan = await api.get_plan_details("201", "301")
        assert plan["id"] == "301"
        # Warning should mention "items" and the plan_id
        assert any(
            "items" in rec.message and "301" in rec.message
            for rec in caplog.records
            if rec.levelno == logging.WARNING
        )


class TestListTeamMembers:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        fixture = load_fixture("list_team_members.json")
        mock_client.get_all.return_value = PagedResult(
            items=fixture["data"],
            total_count=2, truncated=False,
            included=fixture["included"],
        )
        api = ServicesAPI(mock_client)
        result = await api.list_team_members("201", "301")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        call_path = mock_client.get_all.call_args.args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "team_members" in call_path

    async def test_curated_includes_person_id_and_name(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        fixture = load_fixture("list_team_members.json")
        mock_client.get_all.return_value = PagedResult(
            items=fixture["data"],
            total_count=2, truncated=False,
            included=fixture["included"],
        )
        api = ServicesAPI(mock_client)
        result = await api.list_team_members("201", "301")
        tm = result["items"][0]
        assert tm["person_id"] == "1001"
        assert tm["person_name"] == "Alice Smith"
        assert tm["team_position_id"] == "11"
        assert tm["team_position_name"] == "Vocalist"
        assert tm["status"] == "C"

    async def test_passes_include_params(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = ServicesAPI(mock_client)
        await api.list_team_members("201", "301")
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "include" in call_params
        assert "person" in call_params["include"]
        assert "team_position" in call_params["include"]


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
