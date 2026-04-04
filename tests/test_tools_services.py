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
