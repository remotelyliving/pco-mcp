from typing import Any

from fastmcp import FastMCP

from pco_mcp.tools import READ_ANNOTATIONS, WRITE_ANNOTATIONS


def register_people_tools(mcp: FastMCP) -> None:
    """Register all People module tools on the given FastMCP instance."""

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def search_people(
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search for people in Planning Center by name, email, or phone number.

        Returns a list of matching people with their basic info (name, email, phone,
        membership status). Use get_person with a specific ID for full details.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.search_people(name=name, email=email, phone=phone))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_person(person_id: str) -> dict[str, Any]:
        """Get full details for a specific person by their Planning Center ID.

        Returns detailed info including name, email, phone, membership, status,
        birthdate, and gender.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.get_person(person_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_lists() -> list[dict[str, Any]]:
        """Get all lists (smart groups, tags) from Planning Center People.

        Returns each list's name, description, and member count.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.list_lists())

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_list_members(list_id: str) -> list[dict[str, Any]]:
        """Get all people in a specific Planning Center list.

        Provide the list ID (from list_lists). Returns people with basic info.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.get_list_members(list_id))

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def create_person(
        first_name: str,
        last_name: str,
        email: str | None = None,
    ) -> dict[str, Any]:
        """Create a new person in Planning Center.

        Requires first and last name. Email is optional. Returns the created person record.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(
            api.create_person(first_name=first_name, last_name=last_name, email=email)
        )

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def update_person(
        person_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing person's information in Planning Center.

        Provide the person ID and any fields to change. Only provided fields are updated.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        fields = {}
        if first_name is not None:
            fields["first_name"] = first_name
        if last_name is not None:
            fields["last_name"] = last_name
        if email is not None:
            fields["email"] = email
        return await safe_tool_call(api.update_person(person_id, **fields))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_person_blockouts(person_id: str) -> list[dict[str, Any]]:
        """Check a person's unavailability / blockout dates.

        Shows when they can't serve, including recurring blockouts.
        Use before scheduling to avoid conflicts.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.get_person_blockouts(person_id))
