import asyncio

from fastmcp import FastMCP


def make_mcp_with_services_tools() -> FastMCP:
    from pco_mcp.tools.services import register_services_tools

    mcp = FastMCP("test")
    register_services_tools(mcp)
    return mcp


def _tool_names(mcp: FastMCP) -> list[str]:
    """Return registered tool names using FastMCP 3.x internal API."""
    tools = asyncio.run(mcp.list_tools())
    return [t.name for t in tools]


def _tool_map(mcp: FastMCP) -> dict:
    """Return {name: tool} for all registered tools."""
    tools = asyncio.run(mcp.list_tools())
    return {t.name: t for t in tools}


class TestServicesToolRegistration:
    def test_list_service_types_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "list_service_types" in _tool_names(mcp)

    def test_get_upcoming_plans_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "get_upcoming_plans" in _tool_names(mcp)

    def test_list_songs_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "list_songs" in _tool_names(mcp)

    def test_schedule_team_member_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "schedule_team_member" in _tool_names(mcp)

    def test_read_tools_have_readonly_annotation(self) -> None:
        mcp = make_mcp_with_services_tools()
        tool_map = _tool_map(mcp)
        read_tool_names = (
            "list_service_types",
            "get_upcoming_plans",
            "get_plan_details",
            "list_songs",
            "list_team_members",
        )
        for name in read_tool_names:
            if name in tool_map:
                tool = tool_map[name]
                assert tool.annotations is not None, f"{name} has no annotations"
                assert tool.annotations.readOnlyHint is True, (
                    f"{name} expected readOnlyHint=True"
                )

    def test_write_tools_have_confirmation_annotation(self) -> None:
        mcp = make_mcp_with_services_tools()
        tool_map = _tool_map(mcp)
        if "schedule_team_member" in tool_map:
            tool = tool_map["schedule_team_member"]
            assert tool.annotations is not None
            assert tool.annotations.readOnlyHint is False

    def test_list_plan_items_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "list_plan_items" in _tool_names(mcp)

    def test_list_teams_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "list_teams" in _tool_names(mcp)

    def test_list_team_positions_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "list_team_positions" in _tool_names(mcp)

    def test_get_song_schedule_history_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "get_song_schedule_history" in _tool_names(mcp)

    def test_list_song_arrangements_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "list_song_arrangements" in _tool_names(mcp)

    def test_list_plan_templates_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "list_plan_templates" in _tool_names(mcp)

    def test_get_needed_positions_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "get_needed_positions" in _tool_names(mcp)

    def test_create_plan_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "create_plan" in _tool_names(mcp)

    def test_create_plan_time_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "create_plan_time" in _tool_names(mcp)

    def test_add_item_to_plan_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "add_item_to_plan" in _tool_names(mcp)

    def test_remove_item_from_plan_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "remove_item_from_plan" in _tool_names(mcp)

    def test_remove_team_member_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        assert "remove_team_member" in _tool_names(mcp)

    def test_new_read_tools_have_readonly_annotation(self) -> None:
        mcp = make_mcp_with_services_tools()
        tool_map = _tool_map(mcp)
        new_read_tools = (
            "list_plan_items",
            "list_teams",
            "list_team_positions",
            "get_song_schedule_history",
            "list_song_arrangements",
            "list_plan_templates",
            "get_needed_positions",
        )
        for name in new_read_tools:
            if name in tool_map:
                tool = tool_map[name]
                assert tool.annotations is not None, f"{name} has no annotations"
                assert tool.annotations.readOnlyHint is True, (
                    f"{name} expected readOnlyHint=True"
                )

    def test_new_write_tools_have_write_annotation(self) -> None:
        mcp = make_mcp_with_services_tools()
        tool_map = _tool_map(mcp)
        new_write_tools = ("create_plan", "create_plan_time", "add_item_to_plan")
        for name in new_write_tools:
            if name in tool_map:
                tool = tool_map[name]
                assert tool.annotations is not None, f"{name} has no annotations"
                assert tool.annotations.readOnlyHint is False, (
                    f"{name} expected readOnlyHint=False"
                )

    def test_destructive_tools_have_destructive_annotation(self) -> None:
        mcp = make_mcp_with_services_tools()
        tool_map = _tool_map(mcp)
        destructive_tools = ("remove_item_from_plan", "remove_team_member")
        for name in destructive_tools:
            if name in tool_map:
                tool = tool_map[name]
                assert tool.annotations is not None, f"{name} has no annotations"
                assert tool.annotations.destructiveHint is True, (
                    f"{name} expected destructiveHint=True"
                )
