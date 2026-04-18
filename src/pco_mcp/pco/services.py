from typing import Any

from pco_mcp.pco._envelope import index_included, make_envelope, merge_filters
from pco_mcp.pco.client import PCOClient


class ServicesAPI:
    """Wrapper for PCO Services module API calls."""

    def __init__(self, client: PCOClient) -> None:
        self._client = client

    async def create_service_type(
        self, name: str, frequency: str | None = None
    ) -> dict[str, Any]:
        """Create a new service type."""
        attributes: dict[str, Any] = {"name": name}
        if frequency is not None:
            attributes["frequency"] = frequency
        payload: dict[str, Any] = {"data": {"type": "ServiceType", "attributes": attributes}}
        result = await self._client.post("/services/v2/service_types", data=payload)
        return self._simplify_service_type(result["data"])

    async def list_service_types(self) -> dict[str, Any]:
        """List all service types. Returns envelope ``{items, meta}``."""
        params: dict[str, Any] = {}
        result = await self._client.get_all("/services/v2/service_types", params=params)
        simplified = [self._simplify_service_type(st) for st in result.items]
        return make_envelope(result, simplified, params)

    async def get_upcoming_plans(
        self, service_type_id: str, include_past: bool = False,
    ) -> dict[str, Any]:
        """Get plans for a service type. Returns envelope ``{items, meta}``.

        Defaults to future plans ordered by sort_date. Pass
        ``include_past=True`` to drop the future filter and include history.
        ``meta.filters_applied`` reports the active scoping.
        """
        defaults: dict[str, Any] = {"filter": "future", "order": "sort_date"}
        overrides: dict[str, Any] = {}
        if include_past:
            overrides["filter"] = None
        params = merge_filters(defaults, overrides)
        result = await self._client.get_all(
            f"/services/v2/service_types/{service_type_id}/plans",
            params=params,
        )
        simplified = [self._simplify_plan(p) for p in result.items]
        return make_envelope(result, simplified, params)

    async def get_plan_details(self, service_type_id: str, plan_id: str) -> dict[str, Any]:
        """Get full details for a specific plan, including items and team members."""
        base = f"/services/v2/service_types/{service_type_id}/plans/{plan_id}"
        result = await self._client.get(base)
        plan = self._simplify_plan(result["data"])
        items = await self._client.get_all(f"{base}/items")
        plan["items"] = [self._simplify_item(i) for i in items]
        team = await self._client.get_all(f"{base}/team_members")
        plan["team_members"] = [self._simplify_team_member(tm) for tm in team]
        return plan

    async def list_songs(self, query: str | None = None) -> dict[str, Any]:
        """List/search songs. Returns envelope ``{items, meta}``.

        NOTE: PCO's ``where[title]`` filter is an EXACT-match comparison —
        "Amazing" will NOT find "Amazing Grace". Pass the full song title
        to filter, or omit the query to fetch the entire library.
        """
        defaults: dict[str, Any] = {}
        overrides: dict[str, Any] = {}
        if query:
            overrides["where[title]"] = query
        params = merge_filters(defaults, overrides)
        result = await self._client.get_all("/services/v2/songs", params=params)
        simplified = [self._simplify_song(s) for s in result.items]
        return make_envelope(result, simplified, params)

    async def list_team_members(
        self, service_type_id: str, plan_id: str,
    ) -> dict[str, Any]:
        """List team members for a plan. Returns envelope ``{items, meta}``.

        Hard-codes ``include=person,team_position`` so each member's curated
        record carries person_id, person_name, team_position_id, and
        team_position_name directly (no follow-up lookup needed).
        """
        params: dict[str, Any] = {"include": "person,team_position"}
        result = await self._client.get_all(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members",
            params=params,
        )
        included_idx = index_included(result.included)
        simplified = [
            self._simplify_team_member(tm, included_idx) for tm in result.items
        ]
        return make_envelope(result, simplified, params)

    async def schedule_team_member(
        self, service_type_id: str, plan_id: str, person_id: str, team_position_name: str
    ) -> dict[str, Any]:
        """Schedule a person to a team position in a plan."""
        payload: dict[str, Any] = {
            "data": {
                "type": "PlanPerson",
                "attributes": {
                    "person_id": int(person_id),
                    "team_position_name": team_position_name,
                },
            }
        }
        result = await self._client.post(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members",
            data=payload,
        )
        return self._simplify_team_member(result["data"])

    async def create_plan(
        self, service_type_id: str, title: str, sort_date: str
    ) -> dict[str, Any]:
        """Create a new plan for a service type."""
        payload: dict[str, Any] = {
            "data": {
                "type": "Plan",
                "attributes": {
                    "title": title,
                    "sort_date": sort_date,
                },
            }
        }
        result = await self._client.post(
            f"/services/v2/service_types/{service_type_id}/plans", data=payload
        )
        return self._simplify_plan(result["data"])

    async def create_plan_time(
        self,
        service_type_id: str,
        plan_id: str,
        starts_at: str,
        ends_at: str,
        name: str | None = None,
        time_type: str = "service",
    ) -> dict[str, Any]:
        """Create a time entry on a plan."""
        attributes: dict[str, Any] = {
            "starts_at": starts_at,
            "ends_at": ends_at,
            "time_type": time_type,
        }
        if name:
            attributes["name"] = name
        payload: dict[str, Any] = {
            "data": {
                "type": "PlanTime",
                "attributes": attributes,
            }
        }
        result = await self._client.post(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/plan_times",
            data=payload,
        )
        return self._simplify_plan_time(result["data"])

    async def list_plan_items(
        self, service_type_id: str, plan_id: str,
    ) -> dict[str, Any]:
        """List items (songs/elements) on a plan. Returns envelope ``{items, meta}``."""
        params: dict[str, Any] = {}
        result = await self._client.get_all(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/items",
            params=params,
        )
        simplified = [self._simplify_item(i) for i in result.items]
        return make_envelope(result, simplified, params)

    async def add_item_to_plan(
        self,
        service_type_id: str,
        plan_id: str,
        title: str | None = None,
        song_id: str | None = None,
        arrangement_id: str | None = None,
        key_id: str | None = None,
    ) -> dict[str, Any]:
        """Add an item (song or custom element) to a plan."""
        attributes: dict[str, Any] = {}
        if title:
            attributes["title"] = title
        if song_id:
            attributes["song_id"] = int(song_id)
        if arrangement_id:
            attributes["arrangement_id"] = int(arrangement_id)
        if key_id:
            attributes["key_id"] = int(key_id)
        payload: dict[str, Any] = {
            "data": {
                "type": "Item",
                "attributes": attributes,
            }
        }
        result = await self._client.post(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/items",
            data=payload,
        )
        return self._simplify_item(result["data"])

    async def remove_item_from_plan(
        self, service_type_id: str, plan_id: str, item_id: str
    ) -> None:
        """Remove an item from a plan."""
        await self._client.delete(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/items/{item_id}"
        )

    async def list_teams(self, service_type_id: str) -> dict[str, Any]:
        """List teams for a service type. Returns envelope ``{items, meta}``."""
        params: dict[str, Any] = {}
        result = await self._client.get_all(
            f"/services/v2/service_types/{service_type_id}/teams",
            params=params,
        )
        simplified = [self._simplify_team(t) for t in result.items]
        return make_envelope(result, simplified, params)

    async def list_team_positions(self, team_id: str) -> dict[str, Any]:
        """List positions for a team. Returns envelope ``{items, meta}``."""
        params: dict[str, Any] = {}
        result = await self._client.get_all(
            f"/services/v2/teams/{team_id}/team_positions",
            params=params,
        )
        simplified = [self._simplify_position(p) for p in result.items]
        return make_envelope(result, simplified, params)

    async def remove_team_member(
        self, service_type_id: str, plan_id: str, team_member_id: str
    ) -> None:
        """Remove a team member from a plan."""
        await self._client.delete(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members/{team_member_id}"
        )

    async def get_song(self, song_id: str) -> dict[str, Any]:
        """Get full details for a song."""
        result = await self._client.get(f"/services/v2/songs/{song_id}")
        return self._simplify_song_full(result["data"])

    async def create_song(
        self,
        title: str,
        author: str | None = None,
        song_copyright: str | None = None,
        ccli_number: int | None = None,
        themes: str | None = None,
        admin: str | None = None,
    ) -> dict[str, Any]:
        """Create a new song in the library."""
        attributes: dict[str, Any] = {"title": title}
        if author is not None:
            attributes["author"] = author
        if song_copyright is not None:
            attributes["copyright"] = song_copyright
        if ccli_number is not None:
            attributes["ccli_number"] = ccli_number
        if themes is not None:
            attributes["themes"] = themes
        if admin is not None:
            attributes["admin"] = admin
        payload: dict[str, Any] = {"data": {"type": "Song", "attributes": attributes}}
        result = await self._client.post("/services/v2/songs", data=payload)
        return self._simplify_song_full(result["data"])

    async def update_song(
        self,
        song_id: str,
        title: str | None = None,
        author: str | None = None,
        song_copyright: str | None = None,
        ccli_number: int | None = None,
        themes: str | None = None,
        admin: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing song."""
        attributes: dict[str, Any] = {}
        if title is not None:
            attributes["title"] = title
        if author is not None:
            attributes["author"] = author
        if song_copyright is not None:
            attributes["copyright"] = song_copyright
        if ccli_number is not None:
            attributes["ccli_number"] = ccli_number
        if themes is not None:
            attributes["themes"] = themes
        if admin is not None:
            attributes["admin"] = admin
        payload: dict[str, Any] = {"data": {"type": "Song", "attributes": attributes}}
        result = await self._client.patch(f"/services/v2/songs/{song_id}", data=payload)
        return self._simplify_song_full(result["data"])

    async def delete_song(self, song_id: str) -> None:
        """Delete a song and all its arrangements/attachments."""
        await self._client.delete(f"/services/v2/songs/{song_id}")

    async def get_song_schedule_history(self, song_id: str) -> list[dict[str, Any]]:
        """Get schedule history for a song."""
        data = await self._client.get_all(
            f"/services/v2/songs/{song_id}/song_schedules"
        )
        return [self._simplify_song_schedule(s) for s in data]

    async def list_song_arrangements(self, song_id: str) -> list[dict[str, Any]]:
        """List arrangements for a song."""
        data = await self._client.get_all(
            f"/services/v2/songs/{song_id}/arrangements"
        )
        return [self._simplify_arrangement(a) for a in data]

    async def create_arrangement(
        self,
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
        """Create an arrangement for a song."""
        attributes: dict[str, Any] = {"name": name}
        if chord_chart is not None:
            attributes["chord_chart"] = chord_chart
        if bpm is not None:
            attributes["bpm"] = bpm
        if meter is not None:
            attributes["meter"] = meter
        if length is not None:
            attributes["length"] = length
        if chord_chart_key is not None:
            attributes["chord_chart_key"] = chord_chart_key
        if sequence is not None:
            attributes["sequence"] = sequence
        if notes is not None:
            attributes["notes"] = notes
        payload: dict[str, Any] = {"data": {"type": "Arrangement", "attributes": attributes}}
        result = await self._client.post(
            f"/services/v2/songs/{song_id}/arrangements", data=payload
        )
        return self._simplify_arrangement_full(result["data"])

    async def update_arrangement(
        self,
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
        """Update an arrangement."""
        attributes: dict[str, Any] = {}
        if name is not None:
            attributes["name"] = name
        if chord_chart is not None:
            attributes["chord_chart"] = chord_chart
        if bpm is not None:
            attributes["bpm"] = bpm
        if meter is not None:
            attributes["meter"] = meter
        if length is not None:
            attributes["length"] = length
        if chord_chart_key is not None:
            attributes["chord_chart_key"] = chord_chart_key
        if sequence is not None:
            attributes["sequence"] = sequence
        if notes is not None:
            attributes["notes"] = notes
        payload: dict[str, Any] = {"data": {"type": "Arrangement", "attributes": attributes}}
        result = await self._client.patch(
            f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}", data=payload
        )
        return self._simplify_arrangement_full(result["data"])

    async def delete_arrangement(self, song_id: str, arrangement_id: str) -> None:
        """Delete an arrangement from a song."""
        await self._client.delete(
            f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}"
        )

    async def list_plan_templates(self, service_type_id: str) -> list[dict[str, Any]]:
        """List plan templates for a service type."""
        data = await self._client.get_all(
            f"/services/v2/service_types/{service_type_id}/plan_templates"
        )
        return [self._simplify_template(t) for t in data]

    async def get_needed_positions(
        self, service_type_id: str, plan_id: str
    ) -> list[dict[str, Any]]:
        """Get needed (unfilled) positions for a plan."""
        data = await self._client.get_all(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/needed_positions"
        )
        return [self._simplify_needed_position(np) for np in data]

    async def upload_attachment(
        self,
        create_url: str,
        source_url: str,
        filename: str,
        content_type: str,
    ) -> dict[str, Any]:
        """Shared 3-step S3 upload flow.

        1. POST to create_url to create attachment record and get presigned URL
        2. Fetch file from source_url, PUT bytes to presigned URL
        3. PATCH attachment to mark upload complete
        """
        # Step 1: Create attachment record
        payload: dict[str, Any] = {
            "data": {
                "type": "Attachment",
                "attributes": {
                    "filename": filename,
                    "content_type": content_type,
                },
            }
        }
        create_result = await self._client.post(create_url, data=payload)
        attachment_id = create_result["data"]["id"]
        upload_url = create_result["meta"]["upload"]["url"]

        # Step 2: Fetch file from source URL and upload to S3
        response = await self._client._client.get(source_url)
        response.raise_for_status()
        file_bytes = response.content
        await self._client.put_raw(upload_url, data=file_bytes, content_type=content_type)

        # Step 3: Mark upload complete
        complete_payload: dict[str, Any] = {
            "data": {
                "type": "Attachment",
                "attributes": {"remote_link": None},
            }
        }
        result = await self._client.patch(
            f"/services/v2/attachments/{attachment_id}", data=complete_payload
        )
        return self._simplify_attachment(result["data"])

    async def create_attachment(
        self,
        song_id: str,
        arrangement_id: str,
        url: str,
        filename: str,
        content_type: str,
    ) -> dict[str, Any]:
        """Create a file attachment on an arrangement (PDF, MP3, etc.)."""
        create_url = (
            f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}/attachments"
        )
        return await self.upload_attachment(create_url, url, filename, content_type)

    async def list_attachments(
        self, song_id: str, arrangement_id: str
    ) -> list[dict[str, Any]]:
        """List attachments for an arrangement."""
        data = await self._client.get_all(
            f"/services/v2/songs/{song_id}/arrangements/{arrangement_id}/attachments"
        )
        return [self._simplify_attachment(a) for a in data]

    async def create_media(
        self,
        title: str,
        media_type: str,
        url: str,
        filename: str,
        content_type: str,
        creator_name: str | None = None,
    ) -> dict[str, Any]:
        """Create an org-level media item (background, countdown, etc.) with file upload."""
        attributes: dict[str, Any] = {"title": title, "media_type": media_type}
        if creator_name is not None:
            attributes["creator_name"] = creator_name
        payload: dict[str, Any] = {"data": {"type": "Media", "attributes": attributes}}
        create_result = await self._client.post("/services/v2/media", data=payload)
        media_id = create_result["data"]["id"]
        media_record = self._simplify_media(create_result["data"])

        upload_url = create_result["meta"]["upload"]["url"]
        response = await self._client._client.get(url)
        response.raise_for_status()
        file_bytes = response.content
        await self._client.put_raw(upload_url, data=file_bytes, content_type=content_type)

        complete_payload: dict[str, Any] = {
            "data": {
                "type": "Attachment",
                "attributes": {"filename": filename, "content_type": content_type},
            }
        }
        await self._client.patch(
            f"/services/v2/media/{media_id}/attachments", data=complete_payload
        )
        return media_record

    async def get_ccli_reporting(
        self, service_type_id: str, plan_id: str, item_id: str
    ) -> dict[str, Any]:
        """Get CCLI reporting data for a plan item."""
        result = await self._client.get(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}"
            f"/items/{item_id}/ccli_reporting"
        )
        return self._simplify_ccli_reporting(result["data"])

    async def flag_missing_ccli(self) -> dict[str, Any]:
        """Scan the song library and return songs missing CCLI numbers."""
        all_songs = await self._client.get_all("/services/v2/songs")
        missing = []
        for raw in all_songs:
            attrs = raw.get("attributes", {})
            if not attrs.get("ccli_number"):
                missing.append(self._simplify_song(raw))
        return {
            "total_scanned": len(all_songs),
            "total_missing": len(missing),
            "songs": missing,
        }

    async def list_media(self, media_type: str | None = None) -> list[dict[str, Any]]:
        """List org-level media items, optionally filtered by type."""
        params: dict[str, Any] = {}
        if media_type:
            params["where[media_type]"] = media_type
        data = await self._client.get_all("/services/v2/media", params=params)
        return [self._simplify_media(m) for m in data]

    async def update_media(
        self,
        media_id: str,
        title: str | None = None,
        themes: str | None = None,
        creator_name: str | None = None,
    ) -> dict[str, Any]:
        """Update a media item's metadata."""
        attributes: dict[str, Any] = {}
        if title is not None:
            attributes["title"] = title
        if themes is not None:
            attributes["themes"] = themes
        if creator_name is not None:
            attributes["creator_name"] = creator_name
        payload: dict[str, Any] = {"data": {"type": "Media", "attributes": attributes}}
        result = await self._client.patch(f"/services/v2/media/{media_id}", data=payload)
        return self._simplify_media(result["data"])

    def _simplify_media(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "title": attrs.get("title", ""),
            "media_type": attrs.get("media_type"),
            "thumbnail_url": attrs.get("thumbnail_url"),
            "creator_name": attrs.get("creator_name"),
        }

    def _simplify_attachment(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "filename": attrs.get("filename", ""),
            "content_type": attrs.get("content_type"),
            "file_size": attrs.get("file_size"),
            "url": attrs.get("url"),
        }

    def _simplify_service_type(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "frequency": attrs.get("frequency"),
            "last_plan_from": attrs.get("last_plan_from"),
        }

    def _simplify_plan(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "title": attrs.get("title", ""),
            "dates": attrs.get("dates", ""),
            "sort_date": attrs.get("sort_date"),
            "items_count": attrs.get("items_count", 0),
            "needed_positions_count": attrs.get("needed_positions_count", 0),
        }

    def _simplify_song_full(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "title": attrs.get("title", ""),
            "author": attrs.get("author"),
            "copyright": attrs.get("copyright"),
            "ccli_number": attrs.get("ccli_number"),
            "themes": attrs.get("themes"),
            "admin": attrs.get("admin"),
            "created_at": attrs.get("created_at"),
            "last_scheduled_at": attrs.get("last_scheduled_at"),
        }

    def _simplify_song(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "title": attrs.get("title", ""),
            "author": attrs.get("author"),
            "ccli_number": attrs.get("ccli_number"),
            "last_scheduled_at": attrs.get("last_scheduled_at"),
        }

    def _simplify_team_member(
        self,
        raw: dict[str, Any],
        included_index: dict[tuple[str, str], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Curated team_member record.

        Kept: id, status, notification_sent_at, person_name, person_id,
        team_position_name, team_position_id.
        When ``included_index`` is supplied (list path with
        include=person,team_position), person_name and team_position_name are
        authoritative from the included records. When not (write path — e.g.
        ``schedule_team_member`` response), they come from ``attributes.name``
        and ``attributes.team_position_name``; person_id/team_position_id come
        from the relationships refs when present.
        """
        attrs = raw.get("attributes", {})
        rels = raw.get("relationships", {})
        simplified: dict[str, Any] = {
            "id": raw["id"],
            "person_name": attrs.get("name", ""),
            "team_position_name": attrs.get("team_position_name"),
            "status": attrs.get("status"),
            "notification_sent_at": attrs.get("notification_sent_at"),
        }
        person_ref = rels.get("person", {}).get("data")
        if person_ref:
            simplified["person_id"] = person_ref.get("id")
            if included_index:
                person = included_index.get((person_ref["type"], person_ref["id"]))
                if person:
                    pattrs = person.get("attributes", {})
                    simplified["person_name"] = (
                        f"{pattrs.get('first_name', '')} {pattrs.get('last_name', '')}".strip()
                    )
        position_ref = rels.get("team_position", {}).get("data")
        if position_ref:
            simplified["team_position_id"] = position_ref.get("id")
            if included_index:
                position = included_index.get(
                    (position_ref["type"], position_ref["id"])
                )
                if position:
                    simplified["team_position_name"] = position.get("attributes", {}).get("name")
        return simplified

    def _simplify_item(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "title": attrs.get("title", ""),
            "sequence": attrs.get("sequence"),
            "item_type": attrs.get("item_type"),
            "length": attrs.get("length"),
            "song_id": attrs.get("song_id"),
            "description": attrs.get("description"),
            "service_position": attrs.get("service_position"),
        }

    def _simplify_plan_time(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "time_type": attrs.get("time_type"),
            "starts_at": attrs.get("starts_at"),
            "ends_at": attrs.get("ends_at"),
        }

    def _simplify_team(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "schedule_to": attrs.get("schedule_to"),
            "rehearsal_team": attrs.get("rehearsal_team", False),
        }

    def _simplify_position(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "tags": attrs.get("tags", []),
        }

    def _simplify_song_schedule(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "plan_dates": attrs.get("plan_dates"),
            "plan_sort_date": attrs.get("plan_sort_date"),
            "service_type_name": attrs.get("service_type_name"),
            "arrangement_name": attrs.get("arrangement_name"),
            "key_name": attrs.get("key_name"),
        }

    def _simplify_arrangement(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "bpm": attrs.get("bpm"),
            "length": attrs.get("length"),
            "meter": attrs.get("meter"),
            "notes": attrs.get("notes"),
        }

    def _simplify_arrangement_full(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "bpm": attrs.get("bpm"),
            "length": attrs.get("length"),
            "meter": attrs.get("meter"),
            "chord_chart": attrs.get("chord_chart"),
            "chord_chart_key": attrs.get("chord_chart_key"),
            "lyrics": attrs.get("lyrics"),
            "sequence": attrs.get("sequence"),
            "notes": attrs.get("notes"),
        }

    def _simplify_template(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "item_count": attrs.get("item_count", 0),
            "team_count": attrs.get("team_count", 0),
        }

    def _simplify_needed_position(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "team_position_name": attrs.get("team_position_name", ""),
            "quantity": attrs.get("quantity", 0),
            "scheduled_to": attrs.get("scheduled_to"),
        }

    def _simplify_ccli_reporting(self, raw: dict[str, Any]) -> dict[str, Any]:
        attrs = raw.get("attributes", {})
        return {
            "print_count": attrs.get("print_count", 0),
            "digital_count": attrs.get("digital_count", 0),
            "recording_count": attrs.get("recording_count", 0),
            "translation_count": attrs.get("translation_count", 0),
        }
