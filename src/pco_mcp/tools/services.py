from typing import Any

from fastmcp import FastMCP

READ_ANNOTATIONS = {"readOnlyHint": True, "openWorldHint": True}
WRITE_ANNOTATIONS = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}


def register_services_tools(mcp: FastMCP) -> None:
    """Register all Services module tools on the given FastMCP instance."""

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_service_types() -> list[dict[str, Any]]:
        """List all service types in Planning Center Services.

        Returns service types like "Sunday Morning", "Wednesday Night", etc.
        Use the returned ID with get_upcoming_plans to see scheduled services.
        """
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        return await api.list_service_types()

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_upcoming_plans(service_type_id: str) -> list[dict[str, Any]]:
        """Get upcoming service plans for a specific service type.

        Returns future plans with dates, item counts, and needed positions.
        """
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        return await api.get_upcoming_plans(service_type_id)

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_plan_details(service_type_id: str, plan_id: str) -> dict[str, Any]:
        """Get full details for a specific service plan.

        Returns the plan with songs, items, team assignments, and times.
        """
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        return await api.get_plan_details(service_type_id, plan_id)

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_songs(query: str | None = None) -> list[dict[str, Any]]:
        """Search or list songs in the Planning Center song library.

        Optionally filter by title. Returns song title, author, CCLI number,
        and when it was last scheduled.
        """
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        return await api.list_songs(query=query)

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_team_members(service_type_id: str, plan_id: str) -> list[dict[str, Any]]:
        """List team members and their positions for a service plan.

        Returns each team member's name, position, and status (confirmed/pending/declined).
        """
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        return await api.list_team_members(service_type_id, plan_id)

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
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        return await api.schedule_team_member(
            service_type_id, plan_id, person_id, team_position_name
        )
