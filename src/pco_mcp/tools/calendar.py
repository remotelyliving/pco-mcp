from typing import Any

from fastmcp import FastMCP

from pco_mcp.tools import READ_ANNOTATIONS


def register_calendar_tools(mcp: FastMCP) -> None:
    """Register all Calendar module tools on the given FastMCP instance."""

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_calendar_events(
        featured_only: bool = False,
        include_past: bool = False,
    ) -> dict[str, Any]:
        """List calendar events. Returns `{items, meta: {total_count, truncated, filters_applied}}`.

        Defaults to future events. Pass `include_past=True` to include past
        events. Pass `featured_only=True` to restrict to featured events.

        NOTE: PCO does not support filtering this endpoint by start/end date —
        event date/time attributes live on EventInstance, not Event. To find
        events that occur on a specific date, list all events and call
        `get_event_details(event_id)` to inspect their instances.

        `meta.filters_applied` reports exactly what scoping was sent to PCO
        so you can tell an empty result from a narrow filter.
        """
        from pco_mcp.tools._context import get_calendar_api, safe_tool_call

        api = get_calendar_api()
        return await safe_tool_call(
            api.get_events(
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
