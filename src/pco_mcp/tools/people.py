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

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def add_email(
        person_id: str,
        address: str,
        location: str | None = None,
        is_primary: bool | None = None,
    ) -> dict[str, Any]:
        """Add an email address to a person.

        Location options: 'Home', 'Work', 'Other'.
        If the email is already linked to another PCO account, returns an error.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(
            api.add_email(person_id, address=address, location=location, is_primary=is_primary)
        )

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def update_email(
        person_id: str,
        email_id: str,
        address: str | None = None,
        location: str | None = None,
        is_primary: bool | None = None,
    ) -> dict[str, Any]:
        """Update an email address on a person."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(
            api.update_email(
                person_id, email_id, address=address, location=location, is_primary=is_primary
            )
        )

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def add_phone_number(person_id: str, number: str, location: str | None = None, is_primary: bool | None = None) -> dict[str, Any]:
        """Add a phone number to a person. Location options: 'Home', 'Work', 'Mobile', 'Other'."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call
        api = get_people_api()
        return await safe_tool_call(api.add_phone_number(person_id, number=number, location=location, is_primary=is_primary))

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def update_phone_number(person_id: str, phone_id: str, number: str | None = None, location: str | None = None, is_primary: bool | None = None) -> dict[str, Any]:
        """Update a phone number on a person."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call
        api = get_people_api()
        return await safe_tool_call(api.update_phone_number(person_id, phone_id, number=number, location=location, is_primary=is_primary))

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def add_address(person_id: str, street: str, city: str, state: str, zip: str, location: str | None = None, is_primary: bool | None = None) -> dict[str, Any]:
        """Add a mailing address to a person. Location options: 'Home', 'Work', 'Other'."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call
        api = get_people_api()
        return await safe_tool_call(api.add_address(person_id, street=street, city=city, state=state, zip=zip, location=location, is_primary=is_primary))

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def update_address(person_id: str, address_id: str, street: str | None = None, city: str | None = None, state: str | None = None, zip: str | None = None, location: str | None = None, is_primary: bool | None = None) -> dict[str, Any]:
        """Update an address on a person."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call
        api = get_people_api()
        return await safe_tool_call(api.update_address(person_id, address_id, street=street, city=city, state=state, zip=zip, location=location, is_primary=is_primary))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_person_details(person_id: str) -> dict[str, Any]:
        """Get all contact details for a person — emails, phone numbers,
        and addresses in a single call."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.get_person_details(person_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_person_blockouts(person_id: str) -> list[dict[str, Any]]:
        """Check a person's unavailability / blockout dates.

        Shows when they can't serve, including recurring blockouts.
        Use before scheduling to avoid conflicts.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.get_person_blockouts(person_id))

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def add_note(person_id: str, note: str, note_category_id: str | None = None) -> dict[str, Any]:
        """Add a pastoral or administrative note to a person's record.
        If note_category_id is omitted, the note uses the default category."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call
        api = get_people_api()
        return await safe_tool_call(api.add_note(person_id, note=note, note_category_id=note_category_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_notes(person_id: str) -> list[dict[str, Any]]:
        """List notes on a person's record, most recent first (up to 50)."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call
        api = get_people_api()
        return await safe_tool_call(api.get_notes(person_id))
