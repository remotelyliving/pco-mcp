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
    ) -> dict[str, Any]:
        """Search for people in Planning Center by name, email, or phone number.

        Returns an envelope ``{items, meta}``. Each person record includes
        ``emails[]`` and ``phone_numbers[]`` as arrays (all addresses /
        numbers — no silent drop of secondary contacts), plus membership,
        status, birthdate, gender, and other core fields.

        Search semantics (each param routes to a different PCO filter):

        - ``name`` and ``email`` -> PCO's fuzzy-ish ``search_name_or_email``
          filter (NOT a pure substring match, but reasonably forgiving).
        - ``phone`` -> a real phone-search filter. Inputs matching E.164
          format (starts with ``+`` and has 8-15 digits, e.g. ``+15551234567``)
          are routed to ``search_phone_number_e164`` for exact matching;
          other formats (e.g. ``555-1234``, ``(555) 123-4567``) go to
          ``search_phone_number`` for partial matching.

        If multiple params are supplied, the first non-None among
        ``email, phone, name`` wins. When both ``email`` and ``phone`` are
        supplied, ``email`` takes priority and a warning is emitted.

        ``meta.total_count`` reflects server-reported total; ``meta.truncated``
        indicates pagination was capped. ``meta.filters_applied`` echoes the
        actual scoping filters sent to PCO.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.search_people(name=name, email=email, phone=phone))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_person(person_id: str) -> dict[str, Any]:
        """Get full details for a specific person by their Planning Center ID.

        Returns a single-resource dict (not an envelope) with name, all
        ``emails[]``, all ``phone_numbers[]``, membership, status, birthdate,
        gender, created_at, avatar, and site_administrator.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.get_person(person_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_lists() -> dict[str, Any]:
        """Get all lists (smart groups, tags) from Planning Center People.

        Returns an envelope ``{items, meta}`` — each list's name, description,
        and member count. ``meta.truncated`` indicates pagination was capped.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.list_lists())

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_list_members(list_id: str) -> dict[str, Any]:
        """Get all people in a specific Planning Center list.

        Provide the list ID (from list_lists). Returns an envelope
        ``{items, meta}`` — each item has all ``emails[]`` and
        ``phone_numbers[]``. Large lists may trigger ``meta.truncated``.
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
    async def add_phone_number(
        person_id: str, number: str, location: str | None = None, is_primary: bool | None = None
    ) -> dict[str, Any]:
        """Add a phone number to a person. Location options: 'Home', 'Work', 'Mobile', 'Other'."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(
            api.add_phone_number(person_id, number=number, location=location, is_primary=is_primary)
        )

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def update_phone_number(
        person_id: str,
        phone_id: str,
        number: str | None = None,
        location: str | None = None,
        is_primary: bool | None = None,
    ) -> dict[str, Any]:
        """Update a phone number on a person."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(
            api.update_phone_number(
                person_id, phone_id, number=number, location=location, is_primary=is_primary
            )
        )

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def add_address(
        person_id: str,
        street: str,
        city: str,
        state: str,
        zip_code: str,
        location: str | None = None,
        is_primary: bool | None = None,
    ) -> dict[str, Any]:
        """Add a mailing address to a person. Location options: 'Home', 'Work', 'Other'."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(
            api.add_address(
                person_id,
                street=street,
                city=city,
                state=state,
                zip_code=zip_code,
                location=location,
                is_primary=is_primary,
            )
        )

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def update_address(
        person_id: str,
        address_id: str,
        street: str | None = None,
        city: str | None = None,
        state: str | None = None,
        zip_code: str | None = None,
        location: str | None = None,
        is_primary: bool | None = None,
    ) -> dict[str, Any]:
        """Update an address on a person."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(
            api.update_address(
                person_id,
                address_id,
                street=street,
                city=city,
                state=state,
                zip_code=zip_code,
                location=location,
                is_primary=is_primary,
            )
        )

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_person_details(person_id: str) -> dict[str, Any]:
        """Get all contact details for a person — emails, phone numbers,
        and addresses in a single call.

        Returns a single-resource dict with ``emails[]``, ``phone_numbers[]``,
        and ``addresses[]`` as bare arrays (part of the person's curated
        schema — NOT a list envelope).
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.get_person_details(person_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_person_blockouts(person_id: str) -> dict[str, Any]:
        """Check a person's unavailability / blockout dates.

        Returns an envelope ``{items, meta}``. Shows when they can't serve,
        including recurring blockouts. Use before scheduling to avoid
        conflicts.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.get_person_blockouts(person_id))

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def add_blockout(
        person_id: str,
        description: str,
        starts_at: str,
        ends_at: str,
        repeat_frequency: str | None = None,
        repeat_until: str | None = None,
    ) -> dict[str, Any]:
        """Add a blockout (unavailability) date for a person.
        Provide ISO datetimes for starts_at/ends_at.
        Repeat options: 'no_repeat', 'every_1_week', 'every_2_weeks', 'every_1_month'.
        Use repeat_until (ISO date) to set an end date."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(
            api.add_blockout(
                person_id,
                description=description,
                starts_at=starts_at,
                ends_at=ends_at,
                repeat_frequency=repeat_frequency,
                repeat_until=repeat_until,
            )
        )

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def add_note(
        person_id: str, note: str, note_category_id: str | None = None
    ) -> dict[str, Any]:
        """Add a pastoral or administrative note to a person's record.
        If note_category_id is omitted, the note uses the default category."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(
            api.add_note(person_id, note=note, note_category_id=note_category_id)
        )

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_notes(person_id: str) -> dict[str, Any]:
        """List notes on a person's record, most recent first.

        Returns an envelope ``{items, meta}``. Paginates through all notes —
        ``meta.truncated`` fires only if the person has more notes than the
        internal pagination cap.
        """
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.get_notes(person_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_workflows() -> dict[str, Any]:
        """List all workflows in the org (e.g., 'New Member Follow-up',
        'Baptism Prep'). Returns an envelope ``{items, meta}`` — each item
        includes card counts for the workflow."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.get_workflows())

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def add_person_to_workflow(workflow_id: str, person_id: str) -> dict[str, Any]:
        """Add a person to a workflow. Creates a new card at the first step."""
        from pco_mcp.tools._context import get_people_api, safe_tool_call

        api = get_people_api()
        return await safe_tool_call(api.add_person_to_workflow(workflow_id, person_id))
