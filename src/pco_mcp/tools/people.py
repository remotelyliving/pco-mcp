from fastmcp import FastMCP

READ_ANNOTATIONS = {"readOnlyHint": True, "openWorldHint": True}
WRITE_ANNOTATIONS = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}


def register_people_tools(mcp: FastMCP) -> None:
    """Register all People module tools on the given FastMCP instance."""

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def search_people(
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> list[dict]:
        """Search for people in Planning Center by name, email, or phone number.

        Returns a list of matching people with their basic info (name, email, phone,
        membership status). Use get_person with a specific ID for full details.
        """
        from pco_mcp.tools._context import get_people_api

        api = get_people_api()
        return await api.search_people(name=name, email=email, phone=phone)

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_person(person_id: str) -> dict:
        """Get full details for a specific person by their Planning Center ID.

        Returns detailed info including name, email, phone, membership, status,
        birthdate, and gender.
        """
        from pco_mcp.tools._context import get_people_api

        api = get_people_api()
        return await api.get_person(person_id)

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_lists() -> list[dict]:
        """Get all lists (smart groups, tags) from Planning Center People.

        Returns each list's name, description, and member count.
        """
        from pco_mcp.tools._context import get_people_api

        api = get_people_api()
        return await api.list_lists()

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_list_members(list_id: str) -> list[dict]:
        """Get all people in a specific Planning Center list.

        Provide the list ID (from list_lists). Returns people with basic info.
        """
        from pco_mcp.tools._context import get_people_api

        api = get_people_api()
        return await api.get_list_members(list_id)

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def create_person(
        first_name: str,
        last_name: str,
        email: str | None = None,
    ) -> dict:
        """Create a new person in Planning Center.

        Requires first and last name. Email is optional. Returns the created person record.
        """
        from pco_mcp.tools._context import get_people_api

        api = get_people_api()
        return await api.create_person(first_name=first_name, last_name=last_name, email=email)

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def update_person(
        person_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> dict:
        """Update an existing person's information in Planning Center.

        Provide the person ID and any fields to change. Only provided fields are updated.
        """
        from pco_mcp.tools._context import get_people_api

        api = get_people_api()
        fields = {}
        if first_name is not None:
            fields["first_name"] = first_name
        if last_name is not None:
            fields["last_name"] = last_name
        return await api.update_person(person_id, **fields)
