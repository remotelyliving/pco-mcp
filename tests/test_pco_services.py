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


class TestListServiceTypes:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_service_types.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.list_service_types()
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        assert result["items"][0]["name"] == "Sunday Morning"
        assert result["items"][0]["id"] == "201"


class TestGetUpcomingPlans:
    async def test_default_applies_filter_future(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = ServicesAPI(mock_client)
        result = await api.get_upcoming_plans("201")
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert call_params.get("filter") == "future"
        assert result["meta"]["filters_applied"].get("filter") == "future"

    async def test_include_past_drops_filter_future(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = ServicesAPI(mock_client)
        result = await api.get_upcoming_plans("201", include_past=True)
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "filter" not in call_params
        assert "filter" not in result["meta"]["filters_applied"]

    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        fixture = load_fixture("get_upcoming_plans.json")
        mock_client.get_all.return_value = PagedResult(
            items=fixture["data"], total_count=1, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.get_upcoming_plans("201")
        assert "items" in result
        assert "meta" in result
        assert len(result["items"]) == 1
        assert result["items"][0]["title"] == "Easter Service"
        mock_client.get_all.assert_called_once()
        call_path = mock_client.get_all.call_args.args[0]
        assert "201" in call_path


class TestListSongs:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_songs.json")["data"],
            total_count=1, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.list_songs()
        assert "items" in result
        assert "meta" in result
        assert result["items"][0]["title"] == "Amazing Grace"
        assert result["items"][0]["author"] == "John Newton"

    async def test_query_sets_exact_match_filter(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = ServicesAPI(mock_client)
        result = await api.list_songs(query="Amazing Grace")
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert call_params.get("where[title]") == "Amazing Grace"
        assert result["meta"]["filters_applied"].get("where[title]") == "Amazing Grace"


class TestListPlanItems:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        fixture = load_fixture("list_plan_items.json")
        mock_client.get_all.return_value = PagedResult(
            items=fixture["data"],
            total_count=3, truncated=False,
            included=fixture["included"],
        )
        api = ServicesAPI(mock_client)
        result = await api.list_plan_items("201", "301")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 3
        assert result["items"][0]["title"] == "Amazing Grace"
        assert result["items"][0]["item_type"] == "song"
        assert result["items"][1]["item_type"] == "regular"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        fixture = load_fixture("list_plan_items.json")
        mock_client.get_all.return_value = PagedResult(
            items=fixture["data"],
            total_count=3, truncated=False,
            included=fixture["included"],
        )
        api = ServicesAPI(mock_client)
        await api.list_plan_items("201", "301")
        call_path = mock_client.get_all.call_args.args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "items" in call_path

    async def test_passes_include_song_and_arrangement(
        self, mock_client: AsyncMock,
    ) -> None:
        """list_plan_items must send include=song,arrangement so IDs and names
        are available (song_id etc. are NOT on Item.attributes)."""
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(items=[], total_count=0, truncated=False)
        api = ServicesAPI(mock_client)
        await api.list_plan_items("201", "301")
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "include" in call_params
        assert "song" in call_params["include"]
        assert "arrangement" in call_params["include"]

    async def test_item_has_expected_fields(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        fixture = load_fixture("list_plan_items.json")
        mock_client.get_all.return_value = PagedResult(
            items=fixture["data"],
            total_count=3, truncated=False,
            included=fixture["included"],
        )
        api = ServicesAPI(mock_client)
        result = await api.list_plan_items("201", "301")
        item = result["items"][0]
        assert "id" in item
        assert "title" in item
        assert "sequence" in item
        assert "song_id" in item

    async def test_includes_song_arrangement_key_ids_from_relationships(
        self, mock_client: AsyncMock,
    ) -> None:
        """song_id/arrangement_id/key_id are read from relationships refs —
        they are NOT in Item.attributes (live-confirmed)."""
        from pco_mcp.pco.client import PagedResult
        raw = {
            "type": "Item",
            "id": "1",
            "attributes": {
                "title": "Amazing Grace",
                "sequence": 1,
                "item_type": "song",
                "length": 240,
                "description": None,
                "service_position": "during",
                "key_name": "G",
            },
            "relationships": {
                "song": {"data": {"type": "Song", "id": "101"}},
                "arrangement": {"data": {"type": "Arrangement", "id": "202"}},
                "key": {"data": {"type": "Key", "id": "303"}},
            },
        }
        mock_client.get_all.return_value = PagedResult(items=[raw], total_count=1, truncated=False)
        api = ServicesAPI(mock_client)
        result = await api.list_plan_items("1", "2")
        item = result["items"][0]
        assert item["song_id"] == "101"
        assert item["arrangement_id"] == "202"
        assert item["key_id"] == "303"
        assert item["key_name"] == "G"

    async def test_flattens_song_title_and_arrangement_name_from_included(
        self, mock_client: AsyncMock,
    ) -> None:
        """With include=song,arrangement, song_title and arrangement_name
        are flattened from the included records."""
        from pco_mcp.pco.client import PagedResult
        fixture = load_fixture("list_plan_items.json")
        mock_client.get_all.return_value = PagedResult(
            items=fixture["data"],
            total_count=3, truncated=False,
            included=fixture["included"],
        )
        api = ServicesAPI(mock_client)
        result = await api.list_plan_items("201", "301")
        item = result["items"][0]
        assert item["song_id"] == "1001"
        assert item["arrangement_id"] == "2001"
        assert item["key_id"] == "3001"
        assert item["song_title"] == "Amazing Grace"
        assert item["arrangement_name"] == "Standard"


class TestCreatePlan:
    async def test_returns_simplified_plan(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_plan.json")
        api = ServicesAPI(mock_client)
        plan = await api.create_plan("201", "Sunday Morning")
        assert plan["id"] == "401"
        assert plan["title"] == "Sunday Morning"

    async def test_posts_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_plan.json")
        api = ServicesAPI(mock_client)
        await api.create_plan("201", "Sunday Morning")
        call_path = mock_client.post.call_args.args[0]
        assert "201" in call_path
        assert "plans" in call_path

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_plan.json")
        api = ServicesAPI(mock_client)
        await api.create_plan("201", "Sunday Morning")
        data = mock_client.post.call_args.kwargs["data"]
        assert data["data"]["type"] == "Plan"
        attrs = data["data"]["attributes"]
        assert attrs["title"] == "Sunday Morning"

    async def test_does_not_send_sort_date(self, mock_client: AsyncMock) -> None:
        """PCO rejects ``sort_date`` at creation with 422 — it must NOT be
        in the request attributes. Dates are derived from plan_times."""
        mock_client.post.return_value = load_fixture("create_plan.json")
        api = ServicesAPI(mock_client)
        await api.create_plan("201", "Sunday Morning")
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert "sort_date" not in attrs


class TestCreatePlanTime:
    async def test_returns_simplified_plan_time(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_plan_time.json")
        api = ServicesAPI(mock_client)
        result = await api.create_plan_time(
            "201", "301", "2026-04-13T10:00:00Z", "2026-04-13T11:30:00Z", "Main Service"
        )
        assert result["id"] == "601"
        assert result["name"] == "Main Service"
        assert result["time_type"] == "service"

    async def test_posts_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_plan_time.json")
        api = ServicesAPI(mock_client)
        await api.create_plan_time(
            "201", "301", "2026-04-13T10:00:00Z", "2026-04-13T11:30:00Z"
        )
        call_path = mock_client.post.call_args.args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "plan_times" in call_path


class TestAddItemToPlan:
    async def test_returns_simplified_item(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_item_to_plan.json")
        api = ServicesAPI(mock_client)
        item = await api.add_item_to_plan("201", "301", title="Holy Spirit", song_id="1003")
        assert item["id"] == "504"
        assert item["title"] == "Holy Spirit"
        # song_id from relationships.song.data.id (string in JSON:API)
        assert item["song_id"] == "1003"

    async def test_posts_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_item_to_plan.json")
        api = ServicesAPI(mock_client)
        await api.add_item_to_plan("201", "301", title="Holy Spirit")
        call_path = mock_client.post.call_args.args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "items" in call_path

    async def test_sends_song_ids_as_int(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("add_item_to_plan.json")
        api = ServicesAPI(mock_client)
        await api.add_item_to_plan("201", "301", song_id="1003", arrangement_id="2001")
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert attrs["song_id"] == 1003
        assert attrs["arrangement_id"] == 2001


class TestRemoveItemFromPlan:
    async def test_calls_delete(self, mock_client: AsyncMock) -> None:
        mock_client.delete.return_value = None
        api = ServicesAPI(mock_client)
        await api.remove_item_from_plan("201", "301", "504")
        mock_client.delete.assert_called_once()
        call_path = mock_client.delete.call_args.args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "504" in call_path


class TestListTeams:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_teams.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.list_teams("201")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        assert result["items"][0]["name"] == "Worship Team"
        assert result["items"][1]["name"] == "Tech Team"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_teams.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        await api.list_teams("201")
        call_path = mock_client.get_all.call_args.args[0]
        assert "201" in call_path
        assert "teams" in call_path

    async def test_team_has_expected_fields(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_teams.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.list_teams("201")
        team = result["items"][0]
        assert "id" in team
        assert "name" in team
        assert "rehearsal_team" in team


class TestListTeamPositions:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_team_positions.json")["data"],
            total_count=3, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.list_team_positions("701")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 3
        assert result["items"][0]["name"] == "Lead Vocalist"
        assert result["items"][1]["name"] == "Electric Guitar"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_team_positions.json")["data"],
            total_count=3, truncated=False,
        )
        api = ServicesAPI(mock_client)
        await api.list_team_positions("701")
        call_path = mock_client.get_all.call_args.args[0]
        assert "701" in call_path
        assert "team_positions" in call_path


class TestRemoveTeamMember:
    async def test_calls_delete(self, mock_client: AsyncMock) -> None:
        mock_client.delete.return_value = None
        api = ServicesAPI(mock_client)
        await api.remove_team_member("201", "301", "503")
        mock_client.delete.assert_called_once()
        call_path = mock_client.delete.call_args.args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "503" in call_path


class TestGetSongScheduleHistory:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_song_schedule_history.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.get_song_schedule_history("1001")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        assert result["items"][0]["service_type_name"] == "Sunday Morning"
        assert result["items"][0]["key_name"] == "G"
        assert result["items"][1]["key_name"] == "A"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_song_schedule_history.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        await api.get_song_schedule_history("1001")
        call_path = mock_client.get_all.call_args.args[0]
        assert "1001" in call_path
        assert "song_schedules" in call_path

    async def test_record_has_expected_fields(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_song_schedule_history.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.get_song_schedule_history("1001")
        record = result["items"][0]
        assert "plan_dates" in record
        assert "plan_sort_date" in record
        assert "arrangement_name" in record


class TestListSongArrangements:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_song_arrangements.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.list_song_arrangements("1001")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        assert result["items"][0]["name"] == "Standard"
        assert result["items"][0]["bpm"] == 74
        assert result["items"][1]["name"] == "Acoustic"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_song_arrangements.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        await api.list_song_arrangements("1001")
        call_path = mock_client.get_all.call_args.args[0]
        assert "1001" in call_path
        assert "arrangements" in call_path

    async def test_arrangement_has_expected_fields(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_song_arrangements.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.list_song_arrangements("1001")
        arr = result["items"][0]
        assert "id" in arr
        assert "meter" in arr
        assert "length" in arr
        assert "notes" in arr


class TestListPlanTemplates:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_plan_templates.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.list_plan_templates("201")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        assert result["items"][0]["name"] == "Standard Sunday"
        assert result["items"][0]["item_count"] == 8
        assert result["items"][1]["name"] == "Holiday Service"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_plan_templates.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        await api.list_plan_templates("201")
        call_path = mock_client.get_all.call_args.args[0]
        assert "201" in call_path
        assert "plan_templates" in call_path


class TestGetNeededPositions:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_needed_positions.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.get_needed_positions("201", "301")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        assert result["items"][0]["team_position_name"] == "Lead Vocalist"
        assert result["items"][0]["quantity"] == 1
        assert result["items"][1]["team_position_name"] == "Sound Tech"
        assert result["items"][1]["quantity"] == 2

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_needed_positions.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        await api.get_needed_positions("201", "301")
        call_path = mock_client.get_all.call_args.args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "needed_positions" in call_path

    async def test_position_has_scheduled_to_field(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("get_needed_positions.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.get_needed_positions("201", "301")
        assert "scheduled_to" in result["items"][0]

    async def test_team_position_id_flattened_from_relationship(self, mock_client: AsyncMock) -> None:
        """team_position_id must be present whenever the team_position ref exists."""
        from pco_mcp.pco.client import PagedResult
        raw = {
            "type": "NeededPosition",
            "id": "5",
            "attributes": {
                "team_position_name": "Vocalist",
                "quantity": 2,
                "scheduled_to": "anyone",
            },
            "relationships": {
                "team_position": {"data": {"type": "TeamPosition", "id": "77"}}
            },
        }
        mock_client.get_all.return_value = PagedResult(items=[raw], total_count=1, truncated=False)
        api = ServicesAPI(mock_client)
        result = await api.get_needed_positions("1", "2")
        np = result["items"][0]
        assert np["team_position_id"] == "77"
        assert np["team_position_name"] == "Vocalist"


class TestGetSong:
    async def test_returns_full_song_detail(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_song.json")
        api = ServicesAPI(mock_client)
        song = await api.get_song("4001")
        assert song["id"] == "4001"
        assert song["title"] == "Amazing Grace"
        assert song["copyright"] == "Public Domain"
        assert song["themes"] == "Grace, Redemption"
        assert song["admin"] == "Standard hymn"
        assert song["created_at"] == "2025-01-15T10:00:00Z"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_song.json")
        api = ServicesAPI(mock_client)
        await api.get_song("4001")
        call_path = mock_client.get.call_args.args[0]
        assert "4001" in call_path
        assert "/songs/" in call_path


class TestCreateSong:
    async def test_returns_created_song(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_song.json")
        api = ServicesAPI(mock_client)
        song = await api.create_song(title="New Song", author="Test Author", ccli_number=9999999)
        assert song["id"] == "4010"
        assert song["title"] == "New Song"

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_song.json")
        api = ServicesAPI(mock_client)
        await api.create_song(
            title="New Song", author="Test Author", song_copyright="2026 Test", ccli_number=9999999
        )
        data = mock_client.post.call_args.kwargs["data"]
        assert data["data"]["type"] == "Song"
        attrs = data["data"]["attributes"]
        assert attrs["title"] == "New Song"
        assert attrs["author"] == "Test Author"
        assert attrs["copyright"] == "2026 Test"
        assert attrs["ccli_number"] == 9999999

    async def test_only_required_fields(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_song.json")
        api = ServicesAPI(mock_client)
        await api.create_song(title="New Song")
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert attrs["title"] == "New Song"
        assert "author" not in attrs


class TestUpdateSong:
    async def test_returns_updated_song(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_song.json")
        api = ServicesAPI(mock_client)
        song = await api.update_song("4001", title="Amazing Grace (Updated)")
        assert song["title"] == "Amazing Grace (Updated)"

    async def test_sends_patch_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_song.json")
        api = ServicesAPI(mock_client)
        await api.update_song("4001", ccli_number=1234567)
        call_path = mock_client.patch.call_args.args[0]
        assert "4001" in call_path
        data = mock_client.patch.call_args.kwargs["data"]
        assert data["data"]["attributes"]["ccli_number"] == 1234567


class TestDeleteSong:
    async def test_calls_delete(self, mock_client: AsyncMock) -> None:
        mock_client.delete.return_value = None
        api = ServicesAPI(mock_client)
        await api.delete_song("4001")
        mock_client.delete.assert_called_once()
        call_path = mock_client.delete.call_args.args[0]
        assert "4001" in call_path


class TestCreateArrangement:
    async def test_returns_created_arrangement(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_arrangement.json")
        api = ServicesAPI(mock_client)
        arr = await api.create_arrangement(
            song_id="4001", name="Default Arrangement", chord_chart="[G]Amazing [C]grace"
        )
        assert arr["id"] == "1010"
        assert arr["name"] == "Default Arrangement"
        assert arr["chord_chart_key"] == "G"
        assert arr["chord_chart"] == "[G]Amazing [C]grace, how [G]sweet the sound"

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_arrangement.json")
        api = ServicesAPI(mock_client)
        await api.create_arrangement(
            song_id="4001",
            name="Default Arrangement",
            chord_chart="[G]Amazing",
            bpm=120.0,
            meter="4/4",
            chord_chart_key="G",
            sequence=["Verse 1", "Chorus"],
        )
        call_path = mock_client.post.call_args.args[0]
        assert "4001" in call_path
        assert "arrangements" in call_path
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert attrs["name"] == "Default Arrangement"
        assert attrs["bpm"] == 120.0
        assert attrs["sequence"] == ["Verse 1", "Chorus"]

    async def test_only_required_fields(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_arrangement.json")
        api = ServicesAPI(mock_client)
        await api.create_arrangement(song_id="4001", name="Default")
        data = mock_client.post.call_args.kwargs["data"]
        attrs = data["data"]["attributes"]
        assert attrs["name"] == "Default"
        assert "bpm" not in attrs


class TestUpdateArrangement:
    async def test_returns_updated_arrangement(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_arrangement.json")
        api = ServicesAPI(mock_client)
        arr = await api.update_arrangement("4001", "1001", bpm=80.0, chord_chart_key="A")
        assert arr["bpm"] == 80.0
        assert arr["chord_chart_key"] == "A"

    async def test_sends_patch_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_arrangement.json")
        api = ServicesAPI(mock_client)
        await api.update_arrangement("4001", "1001", bpm=80.0)
        call_path = mock_client.patch.call_args.args[0]
        assert "4001" in call_path
        assert "1001" in call_path
        assert "arrangements" in call_path


class TestDeleteArrangement:
    async def test_calls_delete(self, mock_client: AsyncMock) -> None:
        mock_client.delete.return_value = None
        api = ServicesAPI(mock_client)
        await api.delete_arrangement("4001", "1001")
        mock_client.delete.assert_called_once()
        call_path = mock_client.delete.call_args.args[0]
        assert "4001" in call_path
        assert "1001" in call_path


class TestUploadAttachment:
    async def test_three_step_upload_flow(self, mock_client: AsyncMock) -> None:
        """Verify the helper does POST -> fetch URL -> PUT bytes -> PATCH complete."""
        mock_client.post.return_value = load_fixture("create_attachment.json")
        mock_client.patch.return_value = load_fixture("create_attachment_upload.json")
        # Mock the HTTP client for fetching the source URL and S3 PUT
        mock_http = AsyncMock()
        mock_fetch_response = AsyncMock()
        mock_fetch_response.content = b"fake-pdf-bytes"
        mock_fetch_response.raise_for_status = lambda: None
        mock_http.get.return_value = mock_fetch_response
        mock_client._client = mock_http
        mock_client.put_raw = AsyncMock()

        api = ServicesAPI(mock_client)
        result = await api.upload_attachment(
            create_url="/services/v2/songs/4001/arrangements/1001/attachments",
            source_url="https://example.com/chord-chart.pdf",
            filename="chord-chart.pdf",
            content_type="application/pdf",
        )
        assert result["id"] == "5001"
        assert result["filename"] == "chord-chart.pdf"
        # Verify POST was called to create the record
        mock_client.post.assert_called_once()
        # Verify PUT was called to upload bytes to S3
        mock_client.put_raw.assert_called_once_with(
            "https://s3.amazonaws.com/presigned-upload-url",
            data=b"fake-pdf-bytes",
            content_type="application/pdf",
        )
        # Verify PATCH was called to mark upload complete
        mock_client.patch.assert_called_once()


class TestCreateAttachment:
    async def test_calls_upload_attachment(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_attachment.json")
        mock_client.patch.return_value = load_fixture("create_attachment_upload.json")
        mock_http = AsyncMock()
        mock_fetch_response = AsyncMock()
        mock_fetch_response.content = b"fake-pdf-bytes"
        mock_fetch_response.raise_for_status = lambda: None
        mock_http.get.return_value = mock_fetch_response
        mock_client._client = mock_http
        mock_client.put_raw = AsyncMock()

        api = ServicesAPI(mock_client)
        result = await api.create_attachment(
            song_id="4001",
            arrangement_id="1001",
            url="https://example.com/chord-chart.pdf",
            filename="chord-chart.pdf",
            content_type="application/pdf",
        )
        assert result["id"] == "5001"
        call_path = mock_client.post.call_args.args[0]
        assert "4001" in call_path
        assert "1001" in call_path
        assert "attachments" in call_path


class TestListAttachments:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_attachments.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.list_attachments("4001", "1001")
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        assert result["items"][0]["filename"] == "chord-chart.pdf"
        assert result["items"][1]["content_type"] == "audio/mpeg"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_attachments.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        await api.list_attachments("4001", "1001")
        call_path = mock_client.get_all.call_args.args[0]
        assert "4001" in call_path
        assert "1001" in call_path
        assert "attachments" in call_path


class TestCreateMedia:
    async def test_creates_media_with_upload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_media.json")
        mock_client.patch.return_value = load_fixture("create_media_upload.json")
        mock_http = AsyncMock()
        mock_fetch_response = AsyncMock()
        mock_fetch_response.content = b"fake-image-bytes"
        mock_fetch_response.raise_for_status = lambda: None
        mock_http.get.return_value = mock_fetch_response
        mock_client._client = mock_http
        mock_client.put_raw = AsyncMock()

        api = ServicesAPI(mock_client)
        result = await api.create_media(
            title="Worship Background",
            media_type="image",
            url="https://example.com/background.jpg",
            filename="background.jpg",
            content_type="image/jpeg",
        )
        assert result["id"] == "6001"
        assert result["title"] == "Worship Background"

    async def test_posts_media_then_uploads(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_media.json")
        mock_client.patch.return_value = load_fixture("create_media_upload.json")
        mock_http = AsyncMock()
        mock_fetch_response = AsyncMock()
        mock_fetch_response.content = b"fake-image-bytes"
        mock_fetch_response.raise_for_status = lambda: None
        mock_http.get.return_value = mock_fetch_response
        mock_client._client = mock_http
        mock_client.put_raw = AsyncMock()

        api = ServicesAPI(mock_client)
        await api.create_media(
            title="Worship Background",
            media_type="image",
            url="https://example.com/background.jpg",
            filename="background.jpg",
            content_type="image/jpeg",
        )
        first_post_path = mock_client.post.call_args_list[0].args[0]
        assert "/media" in first_post_path


class TestListMedia:
    async def test_returns_envelope(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_media.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.list_media()
        assert "items" in result
        assert "meta" in result
        assert result["meta"]["total_count"] == 2
        assert result["meta"]["filters_applied"] == {}
        assert result["items"][0]["title"] == "Worship Background"
        assert result["items"][1]["media_type"] == "countdown"

    async def test_filters_by_media_type(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=load_fixture("list_media.json")["data"],
            total_count=2, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.list_media(media_type="image")
        params = mock_client.get_all.call_args.kwargs.get("params", {})
        assert params.get("filter") == "image"
        assert result["meta"]["filters_applied"].get("filter") == "image"


class TestUpdateMedia:
    async def test_returns_updated_media(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_media.json")
        api = ServicesAPI(mock_client)
        media = await api.update_media("6001", title="Updated Background")
        assert media["title"] == "Updated Background"

    async def test_sends_patch_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = load_fixture("update_media.json")
        api = ServicesAPI(mock_client)
        await api.update_media("6001", title="Updated Background")
        call_path = mock_client.patch.call_args.args[0]
        assert "6001" in call_path
        assert "/media/" in call_path


class TestGetCCLIReporting:
    async def test_returns_ccli_data(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_ccli_reporting.json")
        api = ServicesAPI(mock_client)
        report = await api.get_ccli_reporting("201", "301", "501")
        assert report["print"] == 5
        assert report["digital"] == 12
        assert report["recording"] == 2
        assert report["translation"] == 0

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_ccli_reporting.json")
        api = ServicesAPI(mock_client)
        await api.get_ccli_reporting("201", "301", "501")
        call_path = mock_client.get.call_args.args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "501" in call_path
        assert "ccli_reporting" in call_path


class TestFlagMissingCCLI:
    async def test_returns_envelope_style_dict(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        combined = (
            load_fixture("list_songs_page1.json")["data"]
            + load_fixture("list_songs_page2.json")["data"]
        )
        mock_client.get_all.return_value = PagedResult(
            items=combined, total_count=4, truncated=False,
        )
        api = ServicesAPI(mock_client)
        result = await api.flag_missing_ccli()
        assert result["total_scanned"] == 4
        assert result["total_missing"] == 2
        missing_titles = [s["title"] for s in result["items"]]
        assert "How Great Is Our God" in missing_titles
        assert "Custom Song" in missing_titles
        assert "Amazing Grace" not in missing_titles
        assert result["meta"]["total_count"] == 4
        assert result["meta"]["truncated"] is False
        assert result["meta"]["filters_applied"] == {}

    async def test_truncated_flag_propagates(self, mock_client: AsyncMock) -> None:
        from pco_mcp.pco.client import PagedResult
        mock_client.get_all.return_value = PagedResult(
            items=[
                {"type": "Song", "id": "1", "attributes": {"title": "Missing", "ccli_number": None}},
            ],
            total_count=1, truncated=True,
        )
        api = ServicesAPI(mock_client)
        result = await api.flag_missing_ccli()
        assert result["meta"]["truncated"] is True



class TestCreateServiceType:
    async def test_returns_created_service_type(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_service_type.json")
        api = ServicesAPI(mock_client)
        st = await api.create_service_type("Wednesday Night", frequency="Every 1 week")
        assert st["id"] == "210"
        assert st["name"] == "Wednesday Night"
        assert st["frequency"] == "Every 1 week"

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_service_type.json")
        api = ServicesAPI(mock_client)
        await api.create_service_type("Wednesday Night", frequency="Every 1 week")
        call_path = mock_client.post.call_args.args[0]
        assert "service_types" in call_path
        data = mock_client.post.call_args.kwargs["data"]
        assert data["data"]["type"] == "ServiceType"
        assert data["data"]["attributes"]["name"] == "Wednesday Night"
        assert data["data"]["attributes"]["frequency"] == "Every 1 week"

    async def test_only_required_fields(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_service_type.json")
        api = ServicesAPI(mock_client)
        await api.create_service_type("Wednesday Night")
        data = mock_client.post.call_args.kwargs["data"]
        assert "frequency" not in data["data"]["attributes"]
