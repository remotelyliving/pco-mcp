from typing import Any

from fastmcp import FastMCP

from pco_mcp.tools import DESTRUCTIVE_ANNOTATIONS, READ_ANNOTATIONS, WRITE_ANNOTATIONS


def register_services_tools(mcp: FastMCP) -> None:
    """Register all Services module tools on the given FastMCP instance."""

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def create_service_type(
        name: str, frequency: str | None = None
    ) -> dict[str, Any]:
        """Create a new service type (e.g., 'Sunday Morning', 'Wednesday Night').

        A blank org needs service types before plans can be created.
        Frequency examples: 'Every 1 week', 'Every 2 weeks'.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.create_service_type(name, frequency=frequency))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_service_types() -> dict[str, Any]:
        """List all service types in Planning Center Services.

        Returns an envelope ``{items, meta}``. Items are service types like
        "Sunday Morning", "Wednesday Night", etc. Use an item's ``id`` with
        ``get_upcoming_plans`` to see scheduled services. ``meta.total_count``
        reflects the server total; ``meta.truncated`` signals pagination caps.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_service_types())

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_upcoming_plans(
        service_type_id: str, include_past: bool = False,
    ) -> dict[str, Any]:
        """Get service plans for a specific service type.

        Returns an envelope ``{items, meta}`` with each plan's dates, item
        counts, and needed positions. Defaults to FUTURE plans ordered by
        sort_date. Pass ``include_past=True`` to drop the future filter and
        include historical plans too. ``meta.filters_applied`` reports the
        active scoping (e.g. ``{"filter": "future"}`` by default).
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(
            api.get_upcoming_plans(service_type_id, include_past=include_past)
        )

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_plan_details(service_type_id: str, plan_id: str) -> dict[str, Any]:
        """Get full details for a specific service plan.

        Returns a single-resource dict (NOT an envelope). Nested ``items``
        and ``team_members`` are bare arrays embedded in the plan. Team
        members come pre-flattened with ``person_id``, ``person_name``,
        ``team_position_id``, and ``team_position_name``
        (``include=person,team_position`` is hard-coded server-side). If
        either internal paginated fetch hits the page cap, a warning is
        logged but the call still succeeds.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.get_plan_details(service_type_id, plan_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_songs(query: str | None = None) -> dict[str, Any]:
        """List songs in the Planning Center song library.

        Returns an envelope ``{items, meta}`` — each item has title, author,
        CCLI number, and when the song was last scheduled.

        IMPORTANT: the ``query`` param is an EXACT-match title filter (PCO's
        ``where[title]``). "Amazing" will NOT find "Amazing Grace". Pass the
        complete song title to filter, or omit ``query`` entirely to fetch
        the full library. For partial matching, omit ``query`` and filter
        client-side on the returned items.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_songs(query=query))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_team_members(
        service_type_id: str, plan_id: str,
    ) -> dict[str, Any]:
        """List team members and positions for a service plan.

        Returns an envelope ``{items, meta}``. Each item carries the
        PlanPerson id, status (C/U/D = confirmed/unconfirmed/declined),
        notification_sent_at, plus ``person_id`` + ``person_name`` and
        ``team_position_id`` + ``team_position_name`` — no follow-up lookup
        needed. Names are sourced authoritatively from the included
        Person/TeamPosition records (``include=person,team_position`` is
        hard-coded server-side).
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
    async def list_plan_items(
        service_type_id: str, plan_id: str,
    ) -> dict[str, Any]:
        """Get the ordered list of items (songs, elements) in a service plan.

        Returns an envelope ``{items, meta}``. Each item carries title, type,
        sequence, length, and song_id (when applicable).
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_plan_items(service_type_id, plan_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_teams(service_type_id: str) -> dict[str, Any]:
        """List all teams for a service type.

        Returns an envelope ``{items, meta}`` — each item has the team name,
        scheduling mode, and whether it's a rehearsal team.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_teams(service_type_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_team_positions(team_id: str) -> dict[str, Any]:
        """List positions within a team (e.g., Lead Vocalist, Drums, Sound Tech).

        Returns an envelope ``{items, meta}``. Use to see which roles exist
        on a team so they can be filled via ``schedule_team_member``.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_team_positions(team_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_song_schedule_history(song_id: str) -> dict[str, Any]:
        """See when a song was last scheduled.

        Returns an envelope ``{items, meta: {total_count, truncated,
        filters_applied}}``. Each item has dates, service type, key, and
        arrangement name for a past use. Useful for song rotation planning.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.get_song_schedule_history(song_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_song_arrangements(song_id: str) -> dict[str, Any]:
        """List available arrangements (versions) of a song.

        Returns an envelope ``{items, meta}`` — each item has id, name, BPM,
        meter, length, and notes. ``meta.total_count`` and ``meta.truncated``
        reflect pagination state.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_song_arrangements(song_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_plan_templates(service_type_id: str) -> dict[str, Any]:
        """List saved plan templates for a service type.

        Returns an envelope ``{items, meta}``. Templates define standard
        service order and team needs.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_plan_templates(service_type_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_needed_positions(service_type_id: str, plan_id: str) -> dict[str, Any]:
        """See unfilled team positions for a plan.

        Returns an envelope ``{items, meta}``. Each item carries
        ``team_position_name``, ``quantity`` still needed, and
        ``scheduled_to``.
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

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_song(song_id: str) -> dict[str, Any]:
        """Get full details for a song including title, author, copyright,
        CCLI number, themes, and admin notes."""
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.get_song(song_id))

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def create_song(
        title: str,
        author: str | None = None,
        song_copyright: str | None = None,
        ccli_number: int | None = None,
        themes: str | None = None,
        admin: str | None = None,
    ) -> dict[str, Any]:
        """Create a new song in the Planning Center song library.

        After creation, use create_arrangement to add lyrics, chord charts, and keys.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(
            api.create_song(
                title=title,
                author=author,
                song_copyright=song_copyright,
                ccli_number=ccli_number,
                themes=themes,
                admin=admin,
            )
        )

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def update_song(
        song_id: str,
        title: str | None = None,
        author: str | None = None,
        song_copyright: str | None = None,
        ccli_number: int | None = None,
        themes: str | None = None,
        admin: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing song's metadata. Useful for populating missing CCLI numbers."""
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(
            api.update_song(
                song_id,
                title=title,
                author=author,
                song_copyright=song_copyright,
                ccli_number=ccli_number,
                themes=themes,
                admin=admin,
            )
        )

    @mcp.tool(annotations=DESTRUCTIVE_ANNOTATIONS)
    async def delete_song(song_id: str) -> dict[str, Any]:
        """Delete a song and all its arrangements and attachments. This cannot be undone."""
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        await api.delete_song(song_id)
        return {"status": "deleted"}

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def create_arrangement(
        song_id: str,
        name: str,
        chord_chart: str | None = None,
        bpm: float | None = None,
        meter: str | None = None,
        length: int | None = None,
        chord_chart_key: str | None = None,
        sequence: list[str] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Create an arrangement for a song with lyrics, chord charts, and key.

        Use ChordPro format for chord_chart to embed chords inline:
        '[G]Amazing [C]grace'. Plain text is lyrics-only.
        The sequence field takes section labels like ['Verse 1', 'Chorus'].
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(
            api.create_arrangement(
                song_id=song_id,
                name=name,
                chord_chart=chord_chart,
                bpm=bpm,
                meter=meter,
                length=length,
                chord_chart_key=chord_chart_key,
                sequence=sequence,
                notes=notes,
            )
        )

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def update_arrangement(
        song_id: str,
        arrangement_id: str,
        name: str | None = None,
        chord_chart: str | None = None,
        bpm: float | None = None,
        meter: str | None = None,
        length: int | None = None,
        chord_chart_key: str | None = None,
        sequence: list[str] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Update an arrangement's metadata, lyrics, chord chart, or key."""
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(
            api.update_arrangement(
                song_id=song_id,
                arrangement_id=arrangement_id,
                name=name,
                chord_chart=chord_chart,
                bpm=bpm,
                meter=meter,
                length=length,
                chord_chart_key=chord_chart_key,
                sequence=sequence,
                notes=notes,
            )
        )

    @mcp.tool(annotations=DESTRUCTIVE_ANNOTATIONS)
    async def delete_arrangement(song_id: str, arrangement_id: str) -> dict[str, Any]:
        """Delete an arrangement from a song. This cannot be undone."""
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        await api.delete_arrangement(song_id, arrangement_id)
        return {"status": "deleted"}

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def create_attachment(
        song_id: str,
        arrangement_id: str,
        url: str,
        filename: str,
        content_type: str,
    ) -> dict[str, Any]:
        """Upload a file attachment to an arrangement (PDF chord chart, MP3 reference track, etc.).

        Provide a publicly accessible URL — the server fetches the file and uploads it to PCO.
        Supported content types: application/pdf, audio/mpeg, image/png, image/jpeg, etc.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(
            api.create_attachment(song_id, arrangement_id, url, filename, content_type)
        )

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_attachments(song_id: str, arrangement_id: str) -> dict[str, Any]:
        """List file attachments on an arrangement (PDFs, audio files, etc.).

        Returns an envelope ``{items, meta}``. Each item has filename,
        content_type, file_size, and download url.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_attachments(song_id, arrangement_id))

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def create_media(
        title: str,
        media_type: str,
        url: str,
        filename: str,
        content_type: str,
        creator_name: str | None = None,
    ) -> dict[str, Any]:
        """Upload an org-level media item (background image, countdown video, bumper video).

        media_type must be one of: 'image', 'video', 'countdown', 'document'.
        Provide a publicly accessible URL — the server fetches and uploads to PCO.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(
            api.create_media(title, media_type, url, filename, content_type, creator_name)
        )

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_media(media_type: str | None = None) -> dict[str, Any]:
        """List org-level media items (backgrounds, countdowns, videos).

        Returns an envelope ``{items, meta: {total_count, truncated,
        filters_applied}}``. Pass ``media_type='background'`` (or
        ``'countdown'``, ``'image'``, ``'video'``, ``'document'``) to filter;
        the filter shows up in ``meta.filters_applied`` when applied.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.list_media(media_type=media_type))

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def update_media(
        media_id: str,
        title: str | None = None,
        themes: str | None = None,
        creator_name: str | None = None,
    ) -> dict[str, Any]:
        """Update a media item's title, themes, or creator."""
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(
            api.update_media(media_id, title=title, themes=themes, creator_name=creator_name)
        )

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_ccli_reporting(
        service_type_id: str, plan_id: str, item_id: str
    ) -> dict[str, Any]:
        """Get CCLI reporting data for a plan item (print, digital, recording, translation counts).

        CCLI reporting is tracked automatically by PCO when songs are added to plans.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.get_ccli_reporting(service_type_id, plan_id, item_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_song_usage_report(song_id: str) -> dict[str, Any]:
        """Get all dates a song was scheduled, with service type, key, and arrangement.

        Returns an envelope ``{items, meta}`` (same shape as
        ``get_song_schedule_history``). Useful for CCLI annual reporting —
        shows how many times a song was used.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.get_song_schedule_history(song_id))

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def flag_missing_ccli() -> dict[str, Any]:
        """Scan the song library for songs missing CCLI numbers.

        Returns a composite dict::

            {
                "total_scanned": int,
                "total_missing": int,
                "items": [<song>, ...],              # only songs missing CCLI
                "meta": {"total_count", "truncated", "filters_applied"}
            }

        The top-level ``items`` + ``meta`` follow the envelope convention so
        truncation of the underlying song scan is surfaced consistently. Use
        ``update_song`` to fill in missing CCLI numbers.
        """
        from pco_mcp.tools._context import get_services_api, safe_tool_call

        api = get_services_api()
        return await safe_tool_call(api.flag_missing_ccli())
