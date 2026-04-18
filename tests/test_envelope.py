"""Cross-cutting tests that hold every module to the envelope contract.

Goals:
1. Truncation propagation: every list-returning tool must surface
   ``meta.truncated`` and ``meta.total_count`` from the underlying
   ``PagedResult``.
2. Include wiring: the two tools that hard-code ``include=`` must
   actually send the param to PCO (catches regressions where a future
   "simplification" quietly drops the include).
3. Search docstring lint: tools whose job is search must document their
   match semantics (exact vs fuzzy) so the caller does not misuse them.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pco_mcp.pco.client import PCOClient, PagedResult


def _fake_access_token(token: str = "test-pco-token"):
    at = MagicMock()
    at.token = token
    return at


@pytest.fixture
def mock_client() -> PCOClient:
    return AsyncMock(spec=PCOClient)


@pytest.fixture(autouse=True)
def setup_context(mock_client: PCOClient) -> None:
    """Mock get_access_token + PCOClient so get_pco_client() returns our mock."""
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


def _make_all_mcp():
    """Build a FastMCP with every module's tools registered."""
    from fastmcp import FastMCP

    from pco_mcp.tools.calendar import register_calendar_tools
    from pco_mcp.tools.checkins import register_checkins_tools
    from pco_mcp.tools.people import register_people_tools
    from pco_mcp.tools.services import register_services_tools

    mcp = FastMCP("test")
    register_calendar_tools(mcp)
    register_checkins_tools(mcp)
    register_people_tools(mcp)
    register_services_tools(mcp)
    return mcp


# Every envelope-returning list tool registered across the four modules.
# (tool_name, kwargs_to_invoke_it). Args use placeholder IDs since the
# client is mocked.
ENVELOPE_TOOLS: list[tuple[str, dict]] = [
    # Calendar
    ("list_calendar_events", {}),
    # Check-ins
    ("list_checkin_events", {}),
    ("get_event_attendance", {"event_id": "1"}),
    ("get_headcounts", {"event_id": "1"}),
    # People
    ("search_people", {"name": "x"}),
    ("list_lists", {}),
    ("get_list_members", {"list_id": "1"}),
    ("get_person_blockouts", {"person_id": "1"}),
    ("list_notes", {"person_id": "1"}),
    ("list_workflows", {}),
    # Services
    ("list_service_types", {}),
    ("get_upcoming_plans", {"service_type_id": "1"}),
    ("list_songs", {}),
    ("list_team_members", {"service_type_id": "1", "plan_id": "1"}),
    ("list_plan_items", {"service_type_id": "1", "plan_id": "1"}),
    ("list_teams", {"service_type_id": "1"}),
    ("list_team_positions", {"team_id": "1"}),
    ("get_song_schedule_history", {"song_id": "1"}),
    ("list_song_arrangements", {"song_id": "1"}),
    ("list_plan_templates", {"service_type_id": "1"}),
    ("get_needed_positions", {"service_type_id": "1", "plan_id": "1"}),
    ("list_attachments", {"song_id": "1", "arrangement_id": "1"}),
    ("list_media", {}),
    ("flag_missing_ccli", {}),
    ("get_song_usage_report", {"song_id": "1"}),
]


class TestTruncationPropagation:
    """Every envelope-returning list tool must propagate truncation signals."""

    @pytest.mark.parametrize("tool_name,args", ENVELOPE_TOOLS)
    async def test_meta_truncated_surfaces_to_caller(
        self, mock_client: AsyncMock, tool_name: str, args: dict,
    ) -> None:
        mock_client.get_all.return_value = PagedResult(
            items=[], total_count=15000, truncated=True,
        )
        # get_headcounts issues per-period .get calls for headcount detail;
        # stub a benign response so aggregation doesn't crash on empty items.
        mock_client.get.return_value = {"data": []}
        mcp = _make_all_mcp()
        fn = _get_tool_fn(mcp, tool_name)
        result = await fn(**args)
        assert isinstance(result, dict), f"{tool_name} must return a dict"
        assert "meta" in result, f"{tool_name} missing meta envelope key"
        assert result["meta"]["truncated"] is True, (
            f"{tool_name} did not propagate meta.truncated"
        )
        assert result["meta"]["total_count"] == 15000, (
            f"{tool_name} did not propagate meta.total_count"
        )


class TestIncludeWiring:
    """Tools that hard-code include= must keep sending it to PCO."""

    async def test_calendar_list_events_sends_include(
        self, mock_client: AsyncMock,
    ) -> None:
        mock_client.get_all.return_value = PagedResult(
            items=[], total_count=0, truncated=False,
        )
        mcp = _make_all_mcp()
        fn = _get_tool_fn(mcp, "list_calendar_events")
        await fn()
        call_params = mock_client.get_all.call_args.kwargs["params"]
        # include=event_instances is NOT valid on this endpoint per PCO's
        # can_include — only owner is supported. Live probe confirmed:
        # invalid includes are silently ignored. Keep sending owner so the
        # simplified event carries owner_name.
        assert call_params.get("include") == "owner"

    async def test_services_list_team_members_sends_include(
        self, mock_client: AsyncMock,
    ) -> None:
        mock_client.get_all.return_value = PagedResult(
            items=[], total_count=0, truncated=False,
        )
        mcp = _make_all_mcp()
        fn = _get_tool_fn(mcp, "list_team_members")
        await fn(service_type_id="1", plan_id="1")
        call_params = mock_client.get_all.call_args.kwargs["params"]
        assert "include" in call_params, (
            "list_team_members must send include= so person_name / "
            "team_position_name are sourced authoritatively"
        )
        assert "person" in call_params["include"]
        assert "team_position" in call_params["include"]


class TestSearchDocstringLint:
    """Regression guard: search/query tools must flag their match semantics."""

    def test_list_songs_docstring_mentions_exact_match(self) -> None:
        mcp = _make_all_mcp()
        fn = _get_tool_fn(mcp, "list_songs")
        doc = fn.__doc__ or ""
        doc_lower = doc.lower()
        assert "exact" in doc_lower, (
            "list_songs docstring must tell the model the query is "
            "exact-match, not substring. Current docstring: "
            + repr(doc[:300])
        )

    def test_search_people_docstring_mentions_search_semantics(self) -> None:
        mcp = _make_all_mcp()
        fn = _get_tool_fn(mcp, "search_people")
        doc = fn.__doc__ or ""
        doc_lower = doc.lower()
        assert "pco" in doc_lower and (
            "search" in doc_lower or "fuzzy" in doc_lower
        ), (
            "search_people docstring must document PCO's search behavior. "
            "Current docstring: " + repr(doc[:300])
        )
