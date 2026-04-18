from typing import Any

from fastmcp import FastMCP

from pco_mcp.tools import READ_ANNOTATIONS


def register_checkins_tools(mcp: FastMCP) -> None:
    """Register all Check-ins module tools on the given FastMCP instance."""

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_checkin_events(
        include_archived: bool = False,
    ) -> dict[str, Any]:
        """List check-in events. Returns `{items, meta: {total_count, truncated, filters_applied}}`.

        Defaults to active (non-archived) events only by sending
        `filter=not_archived`. Pass `include_archived=True` to include
        archived events as well. Check `meta.filters_applied` to see exactly
        what scoping was sent to PCO so you can tell an empty result from a
        narrow filter.
        """
        from pco_mcp.tools._context import get_checkins_api, safe_tool_call

        api = get_checkins_api()
        return await safe_tool_call(
            api.get_events(include_archived=include_archived)
        )

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_event_attendance(
        event_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get check-in attendance records for an event. Returns `{items, meta}`.

        No default date filter. For high-volume events, pass `start_date`
        and/or `end_date` (ISO dates) to scope, or watch `meta.truncated`.
        Results are ordered newest-first and include person names, check-in
        times, and security codes.
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
    ) -> dict[str, Any]:
        """Get headcount data aggregated by event time. Returns `{items, meta}`.

        Each item is one event time with total attendance and a
        `by_location` breakdown (e.g., Main Sanctuary: 150, Kids: 45).
        Optionally filter by date range (ISO dates) against the event
        time's starts_at.
        """
        from pco_mcp.tools._context import get_checkins_api, safe_tool_call

        api = get_checkins_api()
        return await safe_tool_call(
            api.get_headcounts(
                event_id, start_date=start_date, end_date=end_date
            )
        )
