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
        include_past: bool = False,
    ) -> dict[str, Any]:
        """List calendar events. Returns `{items, meta: {total_count, truncated, filters_applied}}`.

        By default returns ONLY future non-featured events ordered by start
        date. Pass `include_past=True` to include past events. Pass
        `start_date`/`end_date` (ISO date strings) to scope the window.
        `start_date`/`end_date` do NOT remove the future-only default on
        their own — pair them with `include_past=True` to search history.

        `meta.filters_applied` reports exactly what scoping was sent to PCO
        so you can tell an empty result from a narrow filter.
        """
        from pco_mcp.tools._context import get_calendar_api, safe_tool_call

        api = get_calendar_api()
        return await safe_tool_call(
            api.get_events(
                start_date=start_date,
                end_date=end_date,
                featured_only=featured_only,
                include_past=include_past,
            )
        )

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_event_details(event_id: str) -> dict[str, Any]:
        """Get full details for a calendar event including occurrences
        and resource/room bookings.

        Single-resource call — returns a curated dict (not an envelope).
        Includes all event instances and all resource requests for the event.
        """
        from pco_mcp.tools._context import get_calendar_api, safe_tool_call

        api = get_calendar_api()
        return await safe_tool_call(api.get_event_detail(event_id))
