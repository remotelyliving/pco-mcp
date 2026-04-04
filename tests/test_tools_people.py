from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP


def make_mcp_with_people_tools() -> FastMCP:
    """Create a FastMCP instance with people tools registered."""
    from pco_mcp.tools.people import register_people_tools

    mcp = FastMCP("test")
    register_people_tools(mcp)
    return mcp


def _get_tools(mcp: FastMCP) -> list:
    """Return all registered tool objects from a FastMCP instance."""
    # FastMCP 3.x stores tools in _local_provider._components keyed as "tool:<name>@"
    return [
        v
        for k, v in mcp._local_provider._components.items()
        if k.startswith("tool:")
    ]


class TestPeopleToolRegistration:
    def test_search_people_tool_registered(self) -> None:
        mcp = make_mcp_with_people_tools()
        tool_names = [t.name for t in _get_tools(mcp)]
        assert "search_people" in tool_names

    def test_get_person_tool_registered(self) -> None:
        mcp = make_mcp_with_people_tools()
        tool_names = [t.name for t in _get_tools(mcp)]
        assert "get_person" in tool_names

    def test_list_lists_tool_registered(self) -> None:
        mcp = make_mcp_with_people_tools()
        tool_names = [t.name for t in _get_tools(mcp)]
        assert "list_lists" in tool_names

    def test_create_person_tool_registered(self) -> None:
        mcp = make_mcp_with_people_tools()
        tool_names = [t.name for t in _get_tools(mcp)]
        assert "create_person" in tool_names

    def test_update_person_tool_registered(self) -> None:
        mcp = make_mcp_with_people_tools()
        tool_names = [t.name for t in _get_tools(mcp)]
        assert "update_person" in tool_names

    def test_read_tools_have_readonly_annotation(self) -> None:
        mcp = make_mcp_with_people_tools()
        for tool in _get_tools(mcp):
            if tool.name in ("search_people", "get_person", "list_lists", "get_list_members"):
                assert tool.annotations is not None
                assert tool.annotations.readOnlyHint is True

    def test_write_tools_have_confirmation_annotation(self) -> None:
        mcp = make_mcp_with_people_tools()
        for tool in _get_tools(mcp):
            if tool.name in ("create_person", "update_person"):
                assert tool.annotations is not None
                assert tool.annotations.readOnlyHint is False
