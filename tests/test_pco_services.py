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
    async def test_returns_simplified_types(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_service_types.json")
        api = ServicesAPI(mock_client)
        types = await api.list_service_types()
        assert len(types) == 2
        assert types[0]["name"] == "Sunday Morning"
        assert types[0]["id"] == "201"


class TestGetUpcomingPlans:
    async def test_returns_plans(self, mock_client: AsyncMock) -> None:
        fixture = load_fixture("get_upcoming_plans.json")
        mock_client.get_all.return_value = fixture["data"]
        api = ServicesAPI(mock_client)
        plans = await api.get_upcoming_plans("201")
        assert len(plans) == 1
        assert plans[0]["title"] == "Easter Service"
        mock_client.get_all.assert_called_once()
        call_path = mock_client.get_all.call_args.args[0]
        assert "201" in call_path


class TestListSongs:
    async def test_returns_songs(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_songs.json")
        api = ServicesAPI(mock_client)
        songs = await api.list_songs()
        assert len(songs) == 1
        assert songs[0]["title"] == "Amazing Grace"
        assert songs[0]["author"] == "John Newton"


class TestListPlanItems:
    async def test_returns_items(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_plan_items.json")
        api = ServicesAPI(mock_client)
        items = await api.list_plan_items("201", "301")
        assert len(items) == 3
        assert items[0]["title"] == "Amazing Grace"
        assert items[0]["item_type"] == "song"
        assert items[1]["item_type"] == "regular"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_plan_items.json")
        api = ServicesAPI(mock_client)
        await api.list_plan_items("201", "301")
        call_path = mock_client.get.call_args.args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "items" in call_path

    async def test_item_has_expected_fields(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_plan_items.json")
        api = ServicesAPI(mock_client)
        items = await api.list_plan_items("201", "301")
        item = items[0]
        assert "id" in item
        assert "title" in item
        assert "sequence" in item
        assert "song_id" in item


class TestCreatePlan:
    async def test_returns_simplified_plan(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_plan.json")
        api = ServicesAPI(mock_client)
        plan = await api.create_plan("201", "Sunday Morning", "2026-04-13")
        assert plan["id"] == "401"
        assert plan["title"] == "Sunday Morning"

    async def test_posts_to_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_plan.json")
        api = ServicesAPI(mock_client)
        await api.create_plan("201", "Sunday Morning", "2026-04-13")
        call_path = mock_client.post.call_args.args[0]
        assert "201" in call_path
        assert "plans" in call_path

    async def test_sends_correct_payload(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = load_fixture("create_plan.json")
        api = ServicesAPI(mock_client)
        await api.create_plan("201", "Sunday Morning", "2026-04-13")
        data = mock_client.post.call_args.kwargs["data"]
        assert data["data"]["type"] == "Plan"
        attrs = data["data"]["attributes"]
        assert attrs["title"] == "Sunday Morning"
        assert attrs["sort_date"] == "2026-04-13"


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
        assert item["song_id"] == 1003

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
    async def test_returns_teams(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_teams.json")
        api = ServicesAPI(mock_client)
        teams = await api.list_teams("201")
        assert len(teams) == 2
        assert teams[0]["name"] == "Worship Team"
        assert teams[1]["name"] == "Tech Team"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_teams.json")
        api = ServicesAPI(mock_client)
        await api.list_teams("201")
        call_path = mock_client.get.call_args.args[0]
        assert "201" in call_path
        assert "teams" in call_path

    async def test_team_has_expected_fields(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_teams.json")
        api = ServicesAPI(mock_client)
        teams = await api.list_teams("201")
        team = teams[0]
        assert "id" in team
        assert "name" in team
        assert "rehearsal_team" in team


class TestListTeamPositions:
    async def test_returns_positions(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_team_positions.json")
        api = ServicesAPI(mock_client)
        positions = await api.list_team_positions("701")
        assert len(positions) == 3
        assert positions[0]["name"] == "Lead Vocalist"
        assert positions[1]["name"] == "Electric Guitar"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_team_positions.json")
        api = ServicesAPI(mock_client)
        await api.list_team_positions("701")
        call_path = mock_client.get.call_args.args[0]
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
    async def test_returns_schedule_records(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_song_schedule_history.json")
        api = ServicesAPI(mock_client)
        history = await api.get_song_schedule_history("1001")
        assert len(history) == 2
        assert history[0]["service_type_name"] == "Sunday Morning"
        assert history[0]["key_name"] == "G"
        assert history[1]["key_name"] == "A"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_song_schedule_history.json")
        api = ServicesAPI(mock_client)
        await api.get_song_schedule_history("1001")
        call_path = mock_client.get.call_args.args[0]
        assert "1001" in call_path
        assert "song_schedules" in call_path

    async def test_record_has_expected_fields(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_song_schedule_history.json")
        api = ServicesAPI(mock_client)
        history = await api.get_song_schedule_history("1001")
        record = history[0]
        assert "plan_dates" in record
        assert "plan_sort_date" in record
        assert "arrangement_name" in record


class TestListSongArrangements:
    async def test_returns_arrangements(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_song_arrangements.json")
        api = ServicesAPI(mock_client)
        arrangements = await api.list_song_arrangements("1001")
        assert len(arrangements) == 2
        assert arrangements[0]["name"] == "Standard"
        assert arrangements[0]["bpm"] == 74
        assert arrangements[1]["name"] == "Acoustic"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_song_arrangements.json")
        api = ServicesAPI(mock_client)
        await api.list_song_arrangements("1001")
        call_path = mock_client.get.call_args.args[0]
        assert "1001" in call_path
        assert "arrangements" in call_path

    async def test_arrangement_has_expected_fields(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_song_arrangements.json")
        api = ServicesAPI(mock_client)
        arrangements = await api.list_song_arrangements("1001")
        arr = arrangements[0]
        assert "id" in arr
        assert "meter" in arr
        assert "length" in arr
        assert "notes" in arr


class TestListPlanTemplates:
    async def test_returns_templates(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_plan_templates.json")
        api = ServicesAPI(mock_client)
        templates = await api.list_plan_templates("201")
        assert len(templates) == 2
        assert templates[0]["name"] == "Standard Sunday"
        assert templates[0]["item_count"] == 8
        assert templates[1]["name"] == "Holiday Service"

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_plan_templates.json")
        api = ServicesAPI(mock_client)
        await api.list_plan_templates("201")
        call_path = mock_client.get.call_args.args[0]
        assert "201" in call_path
        assert "plan_templates" in call_path


class TestGetNeededPositions:
    async def test_returns_needed_positions(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_needed_positions.json")
        api = ServicesAPI(mock_client)
        positions = await api.get_needed_positions("201", "301")
        assert len(positions) == 2
        assert positions[0]["team_position_name"] == "Lead Vocalist"
        assert positions[0]["quantity"] == 1
        assert positions[1]["team_position_name"] == "Sound Tech"
        assert positions[1]["quantity"] == 2

    async def test_calls_correct_endpoint(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_needed_positions.json")
        api = ServicesAPI(mock_client)
        await api.get_needed_positions("201", "301")
        call_path = mock_client.get.call_args.args[0]
        assert "201" in call_path
        assert "301" in call_path
        assert "needed_positions" in call_path

    async def test_position_has_scheduled_to_field(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_needed_positions.json")
        api = ServicesAPI(mock_client)
        positions = await api.get_needed_positions("201", "301")
        assert "scheduled_to" in positions[0]


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
            title="New Song", author="Test Author", copyright="2026 Test", ccli_number=9999999
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
