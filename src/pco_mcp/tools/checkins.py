from typing import Any

from fastmcp import FastMCP

from pco_mcp.tools import READ_ANNOTATIONS


def register_checkins_tools(mcp: FastMCP) -> None:
    """Register all Check-ins module tools on the given FastMCP instance."""

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_checkin_events() -> list[dict[str, Any]]:
        """List all check-in event definitions (e.g., 'Sunday Morning').

        Returns non-archived events with name, frequency, and creation date.
        """
        from pco_mcp.tools._context import get_checkins_api, safe_tool_call

        api = get_checkins_api()
        return await safe_tool_call(api.get_events())

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_event_attendance(
        event_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get check-in attendance records for an event.

        Optionally filter by date range (ISO dates).
        Returns person names, check-in times, and security codes.
        Capped at 500 records.
        """
        from pco_mcp.tools._context import get_checkins_api, safe_tool_call

        api = get_checkins_api()
        return await safe_tool_call(
            api.get_event_checkins(
                event_id, start_date=start_date, end_date=end_date
            )
        )

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_headcounts(
        event_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get attendance headcounts for an event, broken down by location.

        Returns per-date totals and per-location breakdowns
        (e.g., Main Sanctuary: 150, Kids: 45).
        Optionally filter by date range.
        """
        from pco_mcp.tools._context import get_checkins_api, safe_tool_call

        api = get_checkins_api()
        return await safe_tool_call(
            api.get_headcounts(
                event_id, start_date=start_date, end_date=end_date
            )
        )
