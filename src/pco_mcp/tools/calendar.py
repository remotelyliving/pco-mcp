from typing import Any

from fastmcp import FastMCP

from pco_mcp.tools import READ_ANNOTATIONS


def register_calendar_tools(mcp: FastMCP) -> None:
    """Register all Calendar module tools on the given FastMCP instance."""

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_calendar_events(
        start_date: str | None = None,
        end_date: str | None = None,
        featured_only: bool = False,
    ) -> list[dict[str, Any]]:
        """List upcoming calendar events within a date range.

        Defaults to future events. Optionally filter to featured events only.
        Returns event name, dates, recurrence, and visibility.
        """
        from pco_mcp.tools._context import get_calendar_api, safe_tool_call

        api = get_calendar_api()
        return await safe_tool_call(
            api.get_events(
                start_date=start_date,
                end_date=end_date,
                featured_only=featured_only,
            )
        )

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_event_details(event_id: str) -> dict[str, Any]:
        """Get full details for a calendar event including occurrences
        and resource/room bookings.

        Shows what rooms and equipment are booked for the event.
        """
        from pco_mcp.tools._context import get_calendar_api, safe_tool_call

        api = get_calendar_api()
        return await safe_tool_call(api.get_event_detail(event_id))
