from typing import Any

from fastmcp import FastMCP

from pco_mcp.tools import DESTRUCTIVE_ANNOTATIONS, READ_ANNOTATIONS, WRITE_ANNOTATIONS


def register_services_tools(mcp: FastMCP) -> None:
    """Register all Services module tools on the given FastMCP instance."""

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_service_types() -> list[dict[str, Any]]:
        """List all service types in Planning Center Services.

        Returns service types like "Sunday Morning", "Wednesday Night", etc.
        Use the returned ID with get_upcoming_plans to see scheduled services.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_service_types())

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_upcoming_plans(service_type_id: str) -> list[dict[str, Any]]:
        """Get upcoming service plans for a specific service type.

        Returns future plans with dates, item counts, and needed positions.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.get_upcoming_plans(service_type_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_plan_details(service_type_id: str, plan_id: str) -> dict[str, Any]:
        """Get full details for a specific service plan.

        Returns the plan with songs, items, team assignments, and times.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.get_plan_details(service_type_id, plan_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_songs(query: str | None = None) -> list[dict[str, Any]]:
        """Search or list songs in the Planning Center song library.

        Optionally filter by title. Returns song title, author, CCLI number,
        and when it was last scheduled.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_songs(query=query))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_team_members(service_type_id: str, plan_id: str) -> list[dict[str, Any]]:
        """List team members and their positions for a service plan.

        Returns each team member's name, position, and status (confirmed/pending/declined).
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_team_members(service_type_id, plan_id))

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def schedule_team_member(
        service_type_id: str,
        plan_id: str,
        person_id: str,
        team_position_name: str,
    ) -> dict[str, Any]:
        """Schedule a person to a team position in a service plan.

        Provide the service type ID, plan ID, person ID, and the position name
        (e.g., "Vocalist", "Sound Tech"). The person will be notified via Planning Center.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(
            api.schedule_team_member(service_type_id, plan_id, person_id, team_position_name)
        )

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_plan_items(service_type_id: str, plan_id: str) -> list[dict[str, Any]]:
        """Get the ordered list of items (songs, elements) in a service plan.

        Returns each item's title, type, sequence, and song ID.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_plan_items(service_type_id, plan_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_teams(service_type_id: str) -> list[dict[str, Any]]:
        """List all teams for a service type.

        Returns team names, scheduling modes, and whether they're rehearsal teams.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_teams(service_type_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_team_positions(team_id: str) -> list[dict[str, Any]]:
        """List positions within a team (e.g., Lead Vocalist, Drums, Sound Tech).

        Use to see what roles need to be filled.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_team_positions(team_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_song_schedule_history(song_id: str) -> list[dict[str, Any]]:
        """See when a song was last scheduled.

        Returns dates, service types, keys, and arrangements for past uses.
        Useful for song rotation planning.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.get_song_schedule_history(song_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_song_arrangements(song_id: str) -> list[dict[str, Any]]:
        """List available arrangements (versions) of a song with BPM, meter, length, and notes."""
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_song_arrangements(song_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_plan_templates(service_type_id: str) -> list[dict[str, Any]]:
        """List saved plan templates for a service type.

        Templates define standard service order and team needs.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_plan_templates(service_type_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_needed_positions(service_type_id: str, plan_id: str) -> list[dict[str, Any]]:
        """See unfilled team positions for a plan.

        Shows which roles still need people assigned.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.get_needed_positions(service_type_id, plan_id))

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def create_plan(service_type_id: str, title: str, sort_date: str) -> dict[str, Any]:
        """Create a new service plan for a specific date.

        Provide the service type, a title (e.g., 'Sunday Morning'), and the date
        (YYYY-MM-DD format).
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.create_plan(service_type_id, title, sort_date))

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def create_plan_time(
        service_type_id: str,
        plan_id: str,
        starts_at: str,
        ends_at: str,
        name: str,
        time_type: str,
    ) -> dict[str, Any]:
        """Add a service or rehearsal time to a plan.

        Provide ISO datetime for start/end, a name, and type ('service' or 'rehearsal').
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(
            api.create_plan_time(service_type_id, plan_id, starts_at, ends_at, name, time_type)
        )

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def add_item_to_plan(
        service_type_id: str,
        plan_id: str,
        title: str,
        song_id: str | None = None,
        arrangement_id: str | None = None,
        key_id: str | None = None,
    ) -> dict[str, Any]:
        """Add a song or element to a service plan.

        For songs, provide song_id and optionally arrangement_id and key_id.
        For non-song items, provide just a title.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(
            api.add_item_to_plan(service_type_id, plan_id, title, song_id, arrangement_id, key_id)
        )

    @mcp.tool(annotations=DESTRUCTIVE_ANNOTATIONS)
    async def remove_item_from_plan(
        service_type_id: str, plan_id: str, item_id: str
    ) -> dict[str, Any]:
        """Remove a song or element from a service plan."""
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        await api.remove_item_from_plan(service_type_id, plan_id, item_id)
        return {"status": "removed"}

    @mcp.tool(annotations=DESTRUCTIVE_ANNOTATIONS)
    async def remove_team_member(
        service_type_id: str, plan_id: str, team_member_id: str
    ) -> dict[str, Any]:
        """Remove a person from a service plan's team schedule."""
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        await api.remove_team_member(service_type_id, plan_id, team_member_id)
        return {"status": "removed"}
