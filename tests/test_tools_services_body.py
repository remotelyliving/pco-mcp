"""Tests that invoke the actual tool function bodies for services tools.

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
    from pco_mcp.tools.services import register_services_tools

    mcp = FastMCP("test")
    register_services_tools(mcp)
    return mcp


class TestListServiceTypesToolBody:
    async def test_list_service_types(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [
                {
                    "type": "ServiceType",
                    "id": "201",
                    "attributes": {
                        "name": "Sunday Morning",
                        "frequency": "Every week",
                        "last_plan_from": "2026-03-30",
                    },
                }
            ]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_service_types")
        types = await fn()
        assert len(types) == 1
        assert types[0]["name"] == "Sunday Morning"


class TestGetUpcomingPlansToolBody:
    async def test_get_upcoming_plans(self, mock_client: AsyncMock) -> None:
        mock_client.get_all.return_value = [
            {
                "type": "Plan",
                "id": "301",
                "attributes": {
                    "title": "Easter Service",
                    "dates": "April 20, 2026",
                    "sort_date": "2026-04-20T09:00:00Z",
                    "items_count": 12,
                    "needed_positions_count": 3,
                },
            }
        ]
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "get_upcoming_plans")
        plans = await fn(service_type_id="201")
        assert len(plans) == 1
        assert plans[0]["title"] == "Easter Service"


class TestGetPlanDetailsToolBody:
    async def test_get_plan_details(self, mock_client: AsyncMock) -> None:
        plan_response = {
            "data": {
                "type": "Plan",
                "id": "301",
                "attributes": {
                    "title": "Easter Service",
                    "dates": "April 20, 2026",
                    "sort_date": "2026-04-20T09:00:00Z",
                    "items_count": 12,
                    "needed_positions_count": 3,
                },
            }
        }
        empty_list = {"data": []}
        mock_client.get.side_effect = [plan_response, empty_list, empty_list]
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "get_plan_details")
        plan = await fn(service_type_id="201", plan_id="301")
        assert plan["id"] == "301"
        assert plan["title"] == "Easter Service"
        assert "items" in plan
        assert "team_members" in plan


class TestListSongsToolBody:
    async def test_list_songs_no_query(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [
                {
                    "type": "Song",
                    "id": "401",
                    "attributes": {
                        "title": "Amazing Grace",
                        "author": "John Newton",
                        "ccli_number": "12345",
                        "last_scheduled_at": "2026-03-30",
                    },
                }
            ]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_songs")
        songs = await fn()
        assert len(songs) == 1
        assert songs[0]["title"] == "Amazing Grace"

    async def test_list_songs_with_query(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {"data": []}
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_songs")
        songs = await fn(query="Amazing")
        assert songs == []


class TestListTeamMembersToolBody:
    async def test_list_team_members(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [
                {
                    "type": "PlanPerson",
                    "id": "501",
                    "attributes": {
                        "name": "Alice Smith",
                        "team_position_name": "Vocalist",
                        "status": "C",
                        "notification_sent_at": None,
                    },
                }
            ]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_team_members")
        members = await fn(service_type_id="201", plan_id="301")
        assert len(members) == 1
        assert members[0]["person_name"] == "Alice Smith"


class TestScheduleTeamMemberToolBody:
    async def test_schedule_team_member(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "PlanPerson",
                "id": "503",
                "attributes": {
                    "name": "Carol Davis",
                    "team_position_name": "Pianist",
                    "status": "U",
                    "notification_sent_at": None,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "schedule_team_member")
        result = await fn(
            service_type_id="201",
            plan_id="301",
            person_id="1003",
            team_position_name="Pianist",
        )
        assert result["id"] == "503"
        assert result["team_position_name"] == "Pianist"


class TestGetSongToolBody:
    async def test_get_song(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": {
                "type": "Song",
                "id": "4001",
                "attributes": {
                    "title": "Amazing Grace",
                    "author": "John Newton",
                    "copyright": "Public Domain",
                    "ccli_number": 4669344,
                    "themes": "Grace",
                    "admin": "",
                    "created_at": "2025-01-15T10:00:00Z",
                    "last_scheduled_at": "2026-03-30T09:00:00Z",
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "get_song")
        song = await fn(song_id="4001")
        assert song["id"] == "4001"
        assert song["title"] == "Amazing Grace"


class TestCreateSongToolBody:
    async def test_create_song(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Song",
                "id": "4010",
                "attributes": {
                    "title": "New Song",
                    "author": "Test Author",
                    "copyright": "",
                    "ccli_number": None,
                    "themes": "",
                    "admin": "",
                    "created_at": "2026-04-13T10:00:00Z",
                    "last_scheduled_at": None,
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "create_song")
        song = await fn(title="New Song", author="Test Author")
        assert song["id"] == "4010"
        assert song["title"] == "New Song"


class TestUpdateSongToolBody:
    async def test_update_song(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "Song",
                "id": "4001",
                "attributes": {
                    "title": "Amazing Grace",
                    "author": "John Newton",
                    "copyright": "Public Domain",
                    "ccli_number": 1234567,
                    "themes": "",
                    "admin": "",
                    "created_at": "2025-01-15T10:00:00Z",
                    "last_scheduled_at": "2026-03-30T09:00:00Z",
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_song")
        song = await fn(song_id="4001", ccli_number=1234567)
        assert song["ccli_number"] == 1234567


class TestDeleteSongToolBody:
    async def test_delete_song(self, mock_client: AsyncMock) -> None:
        mock_client.delete.return_value = None
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "delete_song")
        result = await fn(song_id="4001")
        assert result["status"] == "deleted"


class TestCreateArrangementToolBody:
    async def test_create_arrangement(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Arrangement",
                "id": "1010",
                "attributes": {
                    "name": "Default",
                    "bpm": 120.0,
                    "length": 300,
                    "meter": "4/4",
                    "chord_chart": "[G]Amazing grace",
                    "chord_chart_key": "G",
                    "lyrics": "Amazing grace",
                    "sequence": ["Verse 1"],
                    "notes": "",
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "create_arrangement")
        arr = await fn(song_id="4001", name="Default", chord_chart="[G]Amazing grace")
        assert arr["id"] == "1010"
        assert arr["name"] == "Default"


class TestUpdateArrangementToolBody:
    async def test_update_arrangement(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "Arrangement",
                "id": "1001",
                "attributes": {
                    "name": "Standard",
                    "bpm": 80.0,
                    "length": 240,
                    "meter": "4/4",
                    "chord_chart": "[A]Amazing grace",
                    "chord_chart_key": "A",
                    "lyrics": "Amazing grace",
                    "sequence": [],
                    "notes": "",
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_arrangement")
        arr = await fn(song_id="4001", arrangement_id="1001", bpm=80.0)
        assert arr["bpm"] == 80.0


class TestDeleteArrangementToolBody:
    async def test_delete_arrangement(self, mock_client: AsyncMock) -> None:
        mock_client.delete.return_value = None
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "delete_arrangement")
        result = await fn(song_id="4001", arrangement_id="1001")
        assert result["status"] == "deleted"


class TestCreateAttachmentToolBody:
    async def test_create_attachment(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Attachment",
                "id": "5001",
                "attributes": {
                    "filename": "chart.pdf",
                    "content_type": "application/pdf",
                    "file_size": None,
                    "url": None,
                },
                "links": {"self": "https://api.planningcenteronline.com/services/v2/attachments/5001"},
            },
            "meta": {"upload": {"url": "https://s3.example.com/upload", "fields": {}}},
        }
        mock_client.patch.return_value = {
            "data": {
                "type": "Attachment",
                "id": "5001",
                "attributes": {
                    "filename": "chart.pdf",
                    "content_type": "application/pdf",
                    "file_size": 1234,
                    "url": "https://cdn.example.com/chart.pdf",
                },
            }
        }
        mock_http = AsyncMock()
        mock_fetch_response = AsyncMock()
        mock_fetch_response.content = b"pdf-bytes"
        mock_fetch_response.raise_for_status = lambda: None
        mock_http.get.return_value = mock_fetch_response
        mock_client._client = mock_http
        mock_client.put_raw = AsyncMock()

        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "create_attachment")
        result = await fn(
            song_id="4001",
            arrangement_id="1001",
            url="https://example.com/chart.pdf",
            filename="chart.pdf",
            content_type="application/pdf",
        )
        assert result["id"] == "5001"


class TestListAttachmentsToolBody:
    async def test_list_attachments(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [
                {
                    "type": "Attachment",
                    "id": "5001",
                    "attributes": {
                        "filename": "chart.pdf",
                        "content_type": "application/pdf",
                        "file_size": 1234,
                        "url": "https://cdn.example.com/chart.pdf",
                    },
                }
            ]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_attachments")
        attachments = await fn(song_id="4001", arrangement_id="1001")
        assert len(attachments) == 1
        assert attachments[0]["filename"] == "chart.pdf"


class TestCreateMediaToolBody:
    async def test_create_media(self, mock_client: AsyncMock) -> None:
        mock_client.post.return_value = {
            "data": {
                "type": "Media",
                "id": "6001",
                "attributes": {
                    "title": "Background",
                    "media_type": "image",
                    "thumbnail_url": None,
                    "creator_name": "Admin",
                },
            },
            "meta": {"upload": {"url": "https://s3.example.com/upload", "fields": {}}},
        }
        mock_client.patch.return_value = {
            "data": {
                "type": "Attachment",
                "id": "6010",
                "attributes": {
                    "filename": "bg.jpg",
                    "content_type": "image/jpeg",
                    "file_size": 5000,
                    "url": "https://cdn.example.com/bg.jpg",
                },
            }
        }
        mock_http = AsyncMock()
        mock_fetch_response = AsyncMock()
        mock_fetch_response.content = b"img-bytes"
        mock_fetch_response.raise_for_status = lambda: None
        mock_http.get.return_value = mock_fetch_response
        mock_client._client = mock_http
        mock_client.put_raw = AsyncMock()

        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "create_media")
        result = await fn(
            title="Background",
            media_type="image",
            url="https://example.com/bg.jpg",
            filename="bg.jpg",
            content_type="image/jpeg",
        )
        assert result["id"] == "6001"


class TestListMediaToolBody:
    async def test_list_media(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = {
            "data": [
                {
                    "type": "Media",
                    "id": "6001",
                    "attributes": {
                        "title": "Background",
                        "media_type": "image",
                        "thumbnail_url": None,
                        "creator_name": "Admin",
                    },
                }
            ]
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "list_media")
        media = await fn()
        assert len(media) == 1
        assert media[0]["title"] == "Background"


class TestUpdateMediaToolBody:
    async def test_update_media(self, mock_client: AsyncMock) -> None:
        mock_client.patch.return_value = {
            "data": {
                "type": "Media",
                "id": "6001",
                "attributes": {
                    "title": "New Title",
                    "media_type": "image",
                    "thumbnail_url": None,
                    "creator_name": "Admin",
                },
            }
        }
        mcp = make_mcp()
        fn = _get_tool_fn(mcp, "update_media")
        result = await fn(media_id="6001", title="New Title")
        assert result["title"] == "New Title"
